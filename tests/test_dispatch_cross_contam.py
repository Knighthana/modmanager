"""Test plan_fileops entries grouping + dispatch pipeline for cross-contamination."""

import json
import tempfile
from pathlib import Path

import pytest

from modmgr.orchestrator import dispatch
from modmgr.orchestrator.entry import Intent, TaskRequest


MOD_A = "2606099273"
MOD_B = "3425312540"
APPID = "270150"


def _build_fixture(root: Path) -> tuple[Path, Path, Path]:
    steamapps = root / "steamapps"
    (steamapps / "common" / "RunningWithRifles").mkdir(parents=True)
    mod_a = steamapps / "workshop" / "content" / APPID / MOD_A
    mod_b = steamapps / "workshop" / "content" / APPID / MOD_B

    # Mod A
    ship = mod_a / "shiplander v1.9"
    (ship / "map_altered" / "sub").mkdir(parents=True)
    (ship / "map_altered" / "sub" / "terrain.xml").write_text(f"A")
    (ship / "map105_3" / "地形美化包微调版").mkdir(parents=True)
    (ship / "map105_3" / "地形美化包微调版" / "asphalt.png").write_text(f"A")
    tmaps = mod_a / "media" / "packages" / "GFL_Castling" / "maps"
    tmaps.mkdir(parents=True)
    (tmaps / "map105_3").mkdir(exist_ok=True)
    (tmaps / "map105_3" / "asphalt.png").write_text(f"old")
    (mod_a / "media" / "packages" / "GFL_Castling" / "textures").mkdir(parents=True)

    # Mod B
    mod_b.mkdir(parents=True)
    (mod_b / "marker.txt").write_text(f"B")

    # ACF
    (steamapps / f"appmanifest_{APPID}.acf").write_text(
        f'"AppState"\n{{\n\t"appid"\t\t"{APPID}"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"123"\n}}'
    )
    ws = steamapps / "workshop"
    ws.mkdir(exist_ok=True)
    (ws / f"appworkshop_{APPID}.acf").write_text(
        f'"AppWorkshop"\n{{\n\t"WorkshopItemsInstalled"\n\t{{\n'
        f'\t\t"{MOD_A}"\n\t\t{{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t\t"{MOD_B}"\n\t\t{{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t}}\n\t"WorkshopItemDetails"\n\t{{\n'
        f'\t\t"{MOD_A}"\n\t\t{{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t\t"{MOD_B}"\n\t\t{{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}}\n'
        f'\t}}\n}}'
    )

    return steamapps, mod_a, mod_b


RULE = {
    "schema_namespace": "KMM_Rule", "schema_version": "knighthana@0.1.0",
    "rule_meta_tag": {"rulenamespace": "test", "rulename": "ship"},
    "game": [{"appid": APPID, "modid": [MOD_A]}],
    "mod": [{
        "mixed_id": f"{APPID}:{MOD_A}",
        "def_destin": f"{APPID}:{MOD_A}",
        "def_action": "replace",
        "sub": [f"{APPID}:{MOD_A}"],
        "actionlist": [
            {"from": ["shiplander v1.9/map105_3/地形美化包微调版/asphalt.png"],
             "from_type": "file",
             "into": ["media/packages/GFL_Castling/maps/map105_3/"], "into_type": "dir"},
        ],
    }],
}


class TestDispatchPipelineCrossContam:
    """Full dispatch() pipeline — check mod B stays clean."""

    def test_backup_via_dispatch_no_cross_contam(self):
        """Dispatch(BACKUP) must not create files under mod B."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            steamapps, mod_a, mod_b = _build_fixture(root)

            database = {
                "schema_namespace": "KMM_Database", "schema_version": "knighthana@0.1.0",
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [{"path": str(root) + "/", "contains_libraryfolders_vdf": False}],
                "game": [{
                    "appid": APPID, "name": "Test",
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

            user_config = {
                "schema_namespace": "KMM_UserConfig",
                "schema_version": "knighthana@0.1.0",
                "baksuffix": "kmmbackup", "bakignore": [],
            }

            # Aggregate + compute
            rule_file = root / "rule.kmmrule.json"
            rule_file.write_text(json.dumps(RULE, ensure_ascii=False), encoding="utf-8")
            from modmgr.rule_aggregator import aggregate
            agg, _w, _e = aggregate([str(rule_file)])
            assert agg is not None, f"Agg failed: {_e}"

            from modmgr.engine import compute_mapping
            mapping_result = compute_mapping(database=database, aggregated_rule_set=agg)
            final_mapping = mapping_result.get("final_mapping", [])

            # ── Backup via dispatch ─────────────────────────────────
            request = TaskRequest(
                identity="cli",
                intent=Intent.BACKUP,
                resolver_type="raw_dict",
                resolver_args={
                    "final_mapping": final_mapping,
                    "database": database,
                    "user_config": user_config,
                },
            )
            result = dispatch(request)
            assert result.ok, result.errors

            # ── CHECK: mod B untouched ──────────────────────────────
            mod_b_files = []
            if mod_b.exists():
                for p in mod_b.rglob("*"):
                    if p.is_file() and "kmmbackup" not in str(p):
                        mod_b_files.append(str(p.relative_to(mod_b)))
            unexpected = [f for f in mod_b_files if f != "marker.txt"]
            assert not unexpected, (
                f"dispatch(BACKUP) cross-contaminated mod B:\n"
                f"Unexpected: {unexpected}\n"
                f"All mod B files: {mod_b_files}"
            )

            # ── Also dump backup_dirs to verify assignment ──────────
            from modmgr.backup_dir_builder import build_backup_dirs
            backup_dirs, _ = build_backup_dirs(final_mapping, database, user_config)
            for bd, files in backup_dirs.items():
                assert MOD_B not in bd or all(
                    str(mod_a) not in f for f in files
                ), f"mod A files in mod B backup_dir {bd}: {files}"
