"""Focused test: dump backup_dir assignment for each file to detect cross-contamination."""

import json
import tempfile
from pathlib import Path

import pytest

from modmgr.rule_aggregator import aggregate
from modmgr.engine import compute_mapping
from modmgr.backup_dir_builder import build_backup_dirs


# Same fixture but with UNIQUE markers in every file
MOD_A = "2606099273"
MOD_B = "3425312540"
APPID = "270150"


def _build_fixture(root: Path) -> tuple[Path, Path, Path]:
    steamapps = root / "steamapps"
    common = steamapps / "common" / "RunningWithRifles"
    common.mkdir(parents=True)

    mod_a = steamapps / "workshop" / "content" / APPID / MOD_A
    mod_b = steamapps / "workshop" / "content" / APPID / MOD_B

    # Mod A content
    ship = mod_a / "shiplander v1.9"
    (ship / "map_altered" / "sub").mkdir(parents=True)
    (ship / "map_altered" / "sub" / "terrain.xml").write_text(f"FROM_MOD_{MOD_A}_map_altered_terrain")
    (ship / "1使用方法和图例" / "消除地图红点（可选）").mkdir(parents=True)
    (ship / "1使用方法和图例" / "消除地图红点（可选）" / "marker.dds").write_text(f"FROM_MOD_{MOD_A}_marker")
    (ship / "map105_3" / "地形美化包微调版").mkdir(parents=True)
    for fn in ["asphalt.png", "dirt.png", "road.png", "sand.png"]:
        (ship / "map105_3" / "地形美化包微调版" / fn).write_text(f"FROM_MOD_{MOD_A}_{fn}")

    # Mod A target dirs with placeholder files
    tmaps = mod_a / "media" / "packages" / "GFL_Castling" / "maps"
    tmaps.mkdir(parents=True)
    (tmaps / "1使用方法和图例" / "old_guide.png").parent.mkdir(parents=True, exist_ok=True)
    (tmaps / "1使用方法和图例" / "old_guide.png").write_text(f"OLD_MOD_{MOD_A}_guide")
    (tmaps / "map105_3").mkdir(exist_ok=True)
    for fn in ["asphalt.png", "dirt.png", "road.png", "sand.png"]:
        (tmaps / "map105_3" / fn).write_text(f"OLD_MOD_{MOD_A}_{fn}")
    (mod_a / "media" / "packages" / "GFL_Castling" / "textures").mkdir(parents=True)

    # Mod B placeholder
    mod_b.mkdir(parents=True)
    (mod_b / f"marker_MOD_{MOD_B}.txt").write_text(f"BELONGS_TO_MOD_{MOD_B}")

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


RULE = {
    "schema_namespace": "KMM_Rule", "schema_version": "knighthana@0.1.0",
    "rule_meta_tag": {"rulenamespace": "test", "rulename": "shiplander"},
    "game": [{"appid": APPID, "modid": [MOD_A]}],
    "mod": [{
        "mixed_id": f"{APPID}:{MOD_A}",
        "def_destin": f"{APPID}:{MOD_A}",
        "def_action": "replace",
        "sub": [f"{APPID}:{MOD_A}"],
        "actionlist": [
            {"from": ["shiplander v1.9/*/"], "from_type": "dir",
             "into": ["media/packages/GFL_Castling/maps/"], "into_type": "dir"},
            {"action": "delete",
             "into": ["media/packages/GFL_Castling/maps/1使用方法和图例/"], "into_type": "dir"},
            {"action": "replace",
             "from": ["shiplander v1.9/1使用方法和图例/消除地图红点（可选）/*"],
             "from_type": "file",
             "into": ["media/packages/GFL_Castling/textures/"], "into_type": "dir"},
            {"action": "delete",
             "into": [f"media/packages/GFL_Castling/maps/map105_3/{f}" for f in
                      ["asphalt.png", "dirt.png", "road.png", "sand.png"]],
             "into_type": "file"},
            {"action": "replace",
             "from": [f"shiplander v1.9/map105_3/地形美化包微调版/{f}" for f in
                      ["asphalt.png", "dirt.png", "road.png", "sand.png"]],
             "from_type": "file",
             "into": ["media/packages/GFL_Castling/maps/map105_3/"], "into_type": "dir"},
        ],
    }],
}


class TestDumpBackupAssignment:
    """Dump every file's backup_dir assignment — look for cross-contamination."""

    def test_no_file_leaks_to_wrong_mod_backup_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            steamapps, mod_a, mod_b = _build_fixture(root)

            database = {
                "schema_namespace": "KMM_Database", "schema_version": "knighthana@0.1.0",
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

            # Aggregate + compute
            rule_file = root / "rule.kmmrule.json"
            rule_file.write_text(json.dumps(RULE, ensure_ascii=False), encoding="utf-8")
            agg, _w, _e = aggregate([str(rule_file)])
            assert agg is not None, f"Aggregation failed: {_e}"

            result = compute_mapping(database=database, aggregated_rule_set=agg)
            final_mapping = result.get("final_mapping", [])
            assert len(final_mapping) > 0, "No mapping entries"

            user_config = {"baksuffix": "kmmbackup"}
            backup_dirs, _w = build_backup_dirs(final_mapping, database, user_config)

            # ── DUMP every assignment ────────────────────────────────
            violations = []
            for bd, files in backup_dirs.items():
                for f in files:
                    # Which mod does this file belong to?
                    belongs_to = None
                    if str(mod_a) in f:
                        belongs_to = MOD_A
                    elif str(mod_b) in f:
                        belongs_to = MOD_B

                    # Which mod is this backup_dir for?
                    bd_is = MOD_A if MOD_A in bd else MOD_B if MOD_B in bd else "unknown"

                    if belongs_to and belongs_to != bd_is:
                        violations.append(
                            f"  CROSS-CONTAMINATION: file from mod {belongs_to}\n"
                            f"    file: {f}\n"
                            f"    assigned to backup_dir: {bd}\n"
                        )

            assert not violations, (
                f"build_backup_dirs assigned files to wrong backup_dir:\n"
                + "\n".join(violations)
            )
