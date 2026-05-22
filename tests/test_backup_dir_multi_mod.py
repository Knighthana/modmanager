"""Test backup_dir assignment for multiple mods under same appid."""

import tempfile
from pathlib import Path

from hana_modmgr.backup_dir_builder import build_backup_dirs


def _make_acf_files(steamapps: Path) -> None:
    """Create minimal Steam ACF files so backup_dir builder can compute hex IDs."""
    (steamapps / "appmanifest_270150.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"270150"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"123"\n}'
    )
    ws = steamapps / "workshop"
    ws.mkdir(exist_ok=True)
    (ws / "appworkshop_270150.acf").write_text(
        '"AppWorkshop"\n'
        '{\n\t"WorkshopItemsInstalled"\n\t{\n'
        '\t\t"2606099273"\n\t\t{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t\t"3425312546"\n\t\t{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t}\n'
        '\t"WorkshopItemDetails"\n\t{\n'
        '\t\t"2606099273"\n\t\t{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t\t"3425312546"\n\t\t{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t}\n'
        '}'
    )


class TestBackupDirMultiMod:
    """Verify files from different mods map to correct backup directories."""

    def test_two_mods_same_appid_separate_dirs(self):
        """Mod A files must not appear in mod B's backup_dir."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            steamapps = root / "steamapps"
            mod_a = steamapps / "workshop" / "content" / "270150" / "2606099273"
            mod_b = steamapps / "workshop" / "content" / "270150" / "3425312546"
            mod_a_media = mod_a / "media" / "packages" / "GFL_Castling" / "maps"
            mod_b_root = mod_b
            mod_a_media.mkdir(parents=True)
            mod_b_root.mkdir(parents=True)

            _make_acf_files(steamapps)

            file_a = mod_a_media / "file_a.txt"
            file_b = mod_b_root / "file_b.txt"
            file_a.write_text("a")
            file_b.write_text("b")

            database = {
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [{"path": str(root) + "/", "contains_libraryfolders_vdf": False}],
                "game": [{
                    "appid": "270150",
                    "name": "TestGame",
                    "basepath": str(steamapps / "common" / "TestGame") + "/",
                    "modpath": str(steamapps / "workshop" / "content" / "270150") + "/",
                    "mods_found": ["2606099273", "3425312546"],
                }],
                "mod": [
                    {"mixed_id": "270150:2606099273", "path": str(mod_a) + "/"},
                    {"mixed_id": "270150:3425312546", "path": str(mod_b) + "/"},
                ],
                "history": [],
            }

            final_mapping = [
                {"path": str(file_a), "request": {"action": "replace", "path": str(file_a)}},
                {"path": str(file_b), "request": {"action": "replace", "path": str(file_b)}},
            ]

            backup_dirs, _warnings = build_backup_dirs(
                final_mapping, database, {"baksuffix": "kmmbackup"}
            )

            # Each file should be in exactly ONE backup_dir
            a_dirs = [d for d, files in backup_dirs.items() if str(file_a) in files]
            b_dirs = [d for d, files in backup_dirs.items() if str(file_b) in files]

            assert len(a_dirs) == 1, f"file_a in {len(a_dirs)} dirs: {a_dirs}"
            assert len(b_dirs) == 1, f"file_b in {len(b_dirs)} dirs: {b_dirs}"

            # The two backup_dirs must be different
            assert a_dirs[0] != b_dirs[0], (
                f"Both files mapped to same backup_dir: {a_dirs[0]}\n"
                f"file_a (2606099273) and file_b (3425312546) should be separate"
            )

            # Check that the backup_dir names contain the correct contentid
            assert "2606099273" in a_dirs[0], f"Wrong contentid in {a_dirs[0]}"
            assert "3425312546" in b_dirs[0], f"Wrong contentid in {b_dirs[0]}"

    def test_backup_then_restore_does_not_cross_contaminate(self):
        """Backup mod A files → restore must not create files under mod B."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            steamapps = root / "steamapps"
            mod_a = steamapps / "workshop" / "content" / "270150" / "2606099273"
            mod_b = steamapps / "workshop" / "content" / "270150" / "3425312546"
            mod_a_media = mod_a / "media" / "packages" / "GFL_Castling" / "maps"
            mod_a_media.mkdir(parents=True)
            mod_b.mkdir(parents=True)

            _make_acf_files(steamapps)

            file_a = mod_a_media / "map.txt"
            file_a.write_text("mod_a_content")

            database = {
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [{"path": str(root) + "/", "contains_libraryfolders_vdf": False}],
                "game": [{
                    "appid": "270150", "name": "TestGame",
                    "basepath": str(steamapps / "common" / "TestGame") + "/",
                    "modpath": str(steamapps / "workshop" / "content" / "270150") + "/",
                    "mods_found": ["2606099273", "3425312546"],
                }],
                "mod": [
                    {"mixed_id": "270150:2606099273", "path": str(mod_a) + "/"},
                    {"mixed_id": "270150:3425312546", "path": str(mod_b) + "/"},
                ],
                "history": [],
            }
            user_config = {"baksuffix": "kmmbackup", "bakignore": []}

            final_mapping = [
                {"path": str(file_a), "request": {"action": "replace", "path": str(file_a)}},
            ]

            backup_dirs, _warnings = build_backup_dirs(final_mapping, database, user_config)

            # Backup file_a
            from hana_modmgr.backup_ops import run_differential_backup
            from hana_modmgr.prep import prep_backup_dir
            from hana_modmgr.orchestrator.ignore_rules import IgnoreRuleSet

            for backup_dir, files in backup_dirs.items():
                rules = IgnoreRuleSet()
                prep_backup_dir(backup_dir, rules)
                run_differential_backup(backup_dir, files, tree=None)

            # Now restore and check that mod_b directory stays clean
            from hana_modmgr.restore_ops import restore_entries
            from hana_modmgr.backup_ops import load_backup_info

            entries_by_dir: dict = {}
            backupinfos: dict = {}
            for backup_dir, files in backup_dirs.items():
                entries_by_dir[backup_dir] = [
                    {"path": f, "request": {"path": "!", "action": "replace",
                     "mixed_id": "0:0", "hashtype": "sha256", "hashvalue": ""}}
                    for f in files
                ]
                info = load_backup_info(backup_dir)
                if info:
                    backupinfos[backup_dir] = info

            result = restore_entries(entries_by_dir, backupinfos)
            assert result["ok"], result["errors"]

            # CRITICAL: mod_b should NOT have any media/ files
            mod_b_media = mod_b / "media"
            assert not mod_b_media.exists(), (
                f"Cross-contamination: restore created {mod_b_media}\n"
                f"mod A's media/ files should never appear under mod B's directory"
            )
