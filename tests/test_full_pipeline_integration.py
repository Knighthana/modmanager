"""Integration test: full pipeline with two mods and a real kmm_rule.

Reproduces the user's fixture: two mods under same appid, one rule that
copies/deletes files within the source mod.  Verifies no files from mod A
ever appear under mod B's directory or backup.
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from hana_modmgr.engine import compute_mapping
from hana_modmgr.orchestrator.ignore_rules import IgnoreRuleSet
from hana_modmgr.prep import prep_backup_dir
from hana_modmgr.backup_ops import run_differential_backup, load_backup_info
from hana_modmgr.restore_ops import restore_entries
from hana_modmgr.apply_ops import apply_entries


# ── Fixture: two mods under same appid ────────────────────────────────

MOD_A = "2606099273"
MOD_B = "3425312540"
APPID = "270150"


def _build_fixture(root: Path) -> tuple[Path, Path, Path]:
    """Create two mods with distinctive content.  Returns (steamapps, mod_a, mod_b)."""
    steamapps = root / "steamapps"
    common = steamapps / "common" / "RunningWithRifles"
    common.mkdir(parents=True)

    mod_a = steamapps / "workshop" / "content" / APPID / MOD_A
    mod_b = steamapps / "workshop" / "content" / APPID / MOD_B
    mod_a.mkdir(parents=True)
    mod_b.mkdir(parents=True)

    # Mod A: has "shiplander v1.9" source directory with subdirs
    ship = mod_a / "shiplander v1.9"
    (ship / "map_altered" / "sub").mkdir(parents=True)
    (ship / "map_altered" / "sub" / "terrain.xml").write_text("<mod_a_terrain/>")
    (ship / "map_altered" / "overview.png").write_text("mod_a_overview")

    (ship / "1使用方法和图例").mkdir()
    (ship / "1使用方法和图例" / "消除地图红点（可选）").mkdir()
    (ship / "1使用方法和图例" / "消除地图红点（可选）" / "marker.dds").write_text("mod_a_red_dot")

    (ship / "map105_3" / "地形美化包微调版").mkdir(parents=True)
    for f in ["asphalt.png", "dirt.png", "road.png", "sand.png"]:
        (ship / "map105_3" / "地形美化包微调版" / f).write_text(f"mod_a_{f}")

    # Mod A: target directories (initially empty or with placeholder)
    target_maps = mod_a / "media" / "packages" / "GFL_Castling" / "maps"
    target_maps.mkdir(parents=True)
    # Create delete-target directory with placeholder (engine expands
    # directory deletes only if the directory exists at compute time)
    (target_maps / "1使用方法和图例").mkdir(exist_ok=True)
    (target_maps / "1使用方法和图例" / "old_guide.png").write_text("old")
    (target_maps / "map105_3").mkdir(exist_ok=True)
    for f in ["asphalt.png", "dirt.png", "road.png", "sand.png"]:
        (target_maps / "map105_3" / f).write_text("old")

    target_textures = mod_a / "media" / "packages" / "GFL_Castling" / "textures"
    target_textures.mkdir(parents=True)

    # Mod B: just a marker file to detect cross-contamination
    (mod_b / "mod_b_marker.txt").write_text("mod_b_original")

    # ACF files
    (steamapps / f"appmanifest_{APPID}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{APPID}"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"123"\n}}'
    )
    ws = steamapps / "workshop"
    ws.mkdir(exist_ok=True)
    (ws / f"appworkshop_{APPID}.acf").write_text(
        f'"AppWorkshop"\n'
        f'{{\n\t"WorkshopItemsInstalled"\n\t{{\n'
        f'\t\t"{MOD_A}"\n\t\t{{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t\t"{MOD_B}"\n\t\t{{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t}}\n'
        f'\t"WorkshopItemDetails"\n\t{{\n'
        f'\t\t"{MOD_A}"\n\t\t{{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t\t"{MOD_B}"\n\t\t{{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t}}\n'
        f'}}'
    )

    return steamapps, mod_a, mod_b


# ── The kmm_rule (user's actual rule, adapted to fixture) ────────────

RULE = {
    "schema_namespace": "KMM_Rule",
    "schema_version": "knighthana@0.1.0",
    "rule_meta_tag": {"rulenamespace": "test", "rulename": "shiplander"},
    "game": [{"appid": APPID, "modid": [MOD_A]}],
    "mod": [{
        "mixed_id": f"{APPID}:{MOD_A}",
        "def_destin": f"{APPID}:{MOD_A}",
        "def_action": "replace",
        "sub": [f"{APPID}:{MOD_A}"],
        "actionlist": [
            {
                "from": ["shiplander v1.9/*/"],
                "from_type": "dir",
                "into": ["media/packages/GFL_Castling/maps/"],
                "into_type": "dir",
            },
            {
                "action": "delete",
                "into": ["media/packages/GFL_Castling/maps/1使用方法和图例/"],
                "into_type": "dir",
            },
            {
                "action": "replace",
                "from": [
                    "shiplander v1.9/1使用方法和图例/消除地图红点（可选）/*",
                ],
                "from_type": "file",
                "into": ["media/packages/GFL_Castling/textures/"],
                "into_type": "dir",
            },
            {
                "action": "delete",
                "into": [
                    "media/packages/GFL_Castling/maps/map105_3/asphalt.png",
                    "media/packages/GFL_Castling/maps/map105_3/dirt.png",
                    "media/packages/GFL_Castling/maps/map105_3/road.png",
                    "media/packages/GFL_Castling/maps/map105_3/sand.png",
                ],
                "into_type": "file",
            },
            {
                "action": "replace",
                "from": [
                    "shiplander v1.9/map105_3/地形美化包微调版/asphalt.png",
                    "shiplander v1.9/map105_3/地形美化包微调版/dirt.png",
                    "shiplander v1.9/map105_3/地形美化包微调版/road.png",
                    "shiplander v1.9/map105_3/地形美化包微调版/sand.png",
                ],
                "from_type": "file",
                "into": ["media/packages/GFL_Castling/maps/map105_3/"],
                "into_type": "dir",
            },
        ],
    }],
}


# ── Tests ─────────────────────────────────────────────────────────────


class TestFullPipelineNoCrossContamination:
    """Apply → Backup → Restore must not cross-contaminate between mods."""

    def test_apply_does_not_create_files_in_mod_b(self):
        """After apply, mod B must have exactly its original files — no extra."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            steamapps, mod_a, mod_b = _build_fixture(root)

            database = {
                "schema_namespace": "KMM_Database",
                "schema_version": "knighthana@0.1.0",
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [{"path": str(root) + "/", "contains_libraryfolders_vdf": False}],
                "game": [{
                    "appid": APPID, "name": "TestGame",
                    "basepath": str(steamapps / "common" / "RunningWithRifles") + "/",
                    "modpath": str(steamapps / "workshop" / "content" / APPID) + "/",
                    "mods_found": [MOD_A, MOD_B],
                }],
                "mod": [
                    {"mixed_id": f"{APPID}:{MOD_A}", "path": str(mod_a) + "/"},
                    {"mixed_id": f"{APPID}:{MOD_B}", "path": str(mod_b) + "/"},
                ],
                "history": [],
            }

            # ── Step 1: Compute mapping ──────────────────────────────
            # Write rule to temp file (aggregate expects file paths)
            rule_file = root / "rule.kmmrule.json"
            rule_file.write_text(json.dumps(RULE, ensure_ascii=False), encoding="utf-8")
            from hana_modmgr.rule_aggregator import aggregate as _agg
            agg_dict, _warns, _errs = _agg([str(rule_file)])
            assert agg_dict is not None, f"Aggregation failed: {_errs}"

            mapping_result = compute_mapping(database=database, aggregated_rule_set=agg_dict)
            final_mapping = mapping_result.get("final_mapping", [])
            assert len(final_mapping) > 0, "Rule produced no mapping entries"

            # ── Step 2: Apply ────────────────────────────────────────
            user_config = {"baksuffix": "kmmbackup", "bakignore": []}
            from hana_modmgr.backup_dir_builder import build_backup_dirs
            backup_dirs, _w = build_backup_dirs(final_mapping, database, user_config)

            entries_by_dir: dict = {}
            for entry in final_mapping:
                tgt = entry["path"]
                for bd, files in backup_dirs.items():
                    if tgt in files:
                        entries_by_dir.setdefault(bd, []).append(entry)
                        break

            apply_result = apply_entries(entries_by_dir)
            assert apply_result["ok"], apply_result["errors"]

            # ── CHECK: no files from mod A created under mod B ───────
            mod_b_files_after = set()
            for p in mod_b.rglob("*"):
                if p.is_file():
                    mod_b_files_after.add(str(p.relative_to(mod_b)))
            unexpected = mod_b_files_after - {"mod_b_marker.txt"}
            assert not unexpected, (
                f"Apply cross-contaminated mod B:\n"
                f"Unexpected files under mod B: {sorted(unexpected)}"
            )

            # EXPECTED: mod B stays clean (no files from mod A leaked)

    def test_backup_then_restore_no_cross_contamination(self):
        """Full backup → restore cycle: mod B must stay clean."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            steamapps, mod_a, mod_b = _build_fixture(root)

            database = {
                "schema_namespace": "KMM_Database",
                "schema_version": "knighthana@0.1.0",
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [{"path": str(root) + "/", "contains_libraryfolders_vdf": False}],
                "game": [{
                    "appid": APPID, "name": "TestGame",
                    "basepath": str(steamapps / "common" / "RunningWithRifles") + "/",
                    "modpath": str(steamapps / "workshop" / "content" / APPID) + "/",
                    "mods_found": [MOD_A, MOD_B],
                }],
                "mod": [
                    {"mixed_id": f"{APPID}:{MOD_A}", "path": str(mod_a) + "/"},
                    {"mixed_id": f"{APPID}:{MOD_B}", "path": str(mod_b) + "/"},
                ],
                "history": [],
            }

            rule_file = root / "rule.kmmrule.json"
            rule_file.write_text(json.dumps(RULE, ensure_ascii=False), encoding="utf-8")
            from hana_modmgr.rule_aggregator import aggregate as _agg2
            agg_dict, _warns, _errs = _agg2([str(rule_file)])
            assert agg_dict is not None, f"Aggregation failed: {_errs}"

            mapping_result = compute_mapping(database=database, aggregated_rule_set=agg_dict)
            final_mapping = mapping_result.get("final_mapping", [])

            user_config = {"baksuffix": "kmmbackup", "bakignore": []}
            from hana_modmgr.backup_dir_builder import build_backup_dirs
            backup_dirs, _w = build_backup_dirs(final_mapping, database, user_config)

            entries_by_dir: dict = {}
            for entry in final_mapping:
                tgt = entry["path"]
                for bd, files in backup_dirs.items():
                    if tgt in files:
                        entries_by_dir.setdefault(bd, []).append(entry)
                        break

            # Apply first
            apply_result = apply_entries(entries_by_dir)
            assert apply_result["ok"], apply_result["errors"]

            # Backup
            for bd, files in backup_dirs.items():
                rules = IgnoreRuleSet()
                prep_backup_dir(bd, rules)
                run_differential_backup(bd, files, tree=None)

            # Restore
            restore_entries_dict: dict = {}
            backupinfos: dict = {}
            for bd, files in backup_dirs.items():
                restore_entries_dict[bd] = [
                    {"path": f, "request": {"path": "!", "action": "replace",
                     "mixed_id": "0:0", "hashtype": "sha256", "hashvalue": ""}}
                    for f in files
                ]
                info = load_backup_info(bd)
                if info:
                    backupinfos[bd] = info

            restore_result = restore_entries(restore_entries_dict, backupinfos)
            assert restore_result["ok"], restore_result["errors"]

            # CHECK: mod B untouched
            mod_b_files = set()
            for p in mod_b.rglob("*"):
                if p.is_file():
                    mod_b_files.add(str(p.relative_to(mod_b)))
            unexpected = mod_b_files - {"mod_b_marker.txt"}
            assert not unexpected, (
                f"Backup→Restore cross-contaminated mod B:\n"
                f"Unexpected files: {sorted(unexpected)}"
            )
