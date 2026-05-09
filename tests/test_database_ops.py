from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modmanager.database_ops import (
    add_manual_game,
    add_manual_steamlib,
    discover_with_fallback,
    list_games,
    list_steamlibs,
    liveupdate_database,
    regen_database,
    remove_manual_game,
    remove_manual_steamlib,
    update_manual_game,
    update_manual_steamlib,
    verify_database_integrity,
)
from modmanager.steam_scanner import GameInfo, SteamLibraryInfo


class DatabaseOpsTests(unittest.TestCase):
    def test_steamlib_crud_roundtrip(self) -> None:
        db: dict = {"OS": {"workingpathstyle": "linux", "steamlibpathstyle": "windows"}}

        created, _ = add_manual_steamlib(db, path="/mnt/d/Games", contains_libraryfolders_vdf=False)
        self.assertTrue(created)
        self.assertEqual(len(list_steamlibs(db)), 1)

        updated, _ = update_manual_steamlib(db, old_path="/mnt/d/Games", new_path="/mnt/e/Games")
        self.assertTrue(updated)
        self.assertEqual(db["steamlib"][0]["path"], "/mnt/e/Games/steamapps")

        removed, _ = remove_manual_steamlib(db, path="/mnt/e/Games")
        self.assertTrue(removed)
        self.assertEqual(db["steamlib"], [])

    def test_game_crud_updates_membership_and_mod(self) -> None:
        db = {
            "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "windows"},
            "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": []}],
            "game": [],
            "mod": [],
        }

        created, _ = add_manual_game(
            db,
            appid="270150",
            name="RWR",
            basepath="/mnt/d/Games/steamapps/common/RunningWithRifles",
            modpath="/mnt/d/Games/steamapps/workshop/content/270150",
            mods_found=["2606099273"],
        )
        self.assertTrue(created)
        self.assertIn("270150", db["steamlib"][0]["game"])
        self.assertEqual(db["mod"][0]["mixed_id"], "270150:2606099273")

        ok, _ = update_manual_game(db, appid="270150", updates={"mods_found": ["3428584891"]})
        self.assertTrue(ok)
        self.assertEqual(db["mod"][0]["mixed_id"], "270150:3428584891")

        removed, _ = remove_manual_game(db, appid="270150")
        self.assertTrue(removed)
        self.assertEqual(db["game"], [])
        self.assertEqual(db["mod"], [])

    def test_discover_with_fallback_uses_manual_when_auto_fails(self) -> None:
        manual = [{"path": "/mnt/d/Games", "contains_libraryfolders_vdf": False}]

        with patch("modmanager.database_ops.SteamScanner.discover_steam_libraries", return_value=[]):
            with patch("modmanager.database_ops.SteamScanner.discover_games_in_library") as mock_games:
                with patch("modmanager.database_ops.SteamScanner.discover_mods_for_game") as mock_mods:
                    mock_games.return_value = {
                        "270150": GameInfo(
                            appid="270150",
                            name="Running with Rifles",
                            basepath="/mnt/d/Games/steamapps/common/RunningWithRifles",
                            modpath="/mnt/d/Games/steamapps/workshop/content/270150",
                        )
                    }
                    mock_mods.return_value = ["2606099273"]

                    database = discover_with_fallback(
                        working_pathstyle="linux",
                        manual_override_steamlibs=manual,
                        greedy_parsing=True,
                    )

        self.assertEqual(len(database["steamlib"]), 1)
        self.assertEqual(database["steamlib"][0]["path"], "/mnt/d/Games/steamapps")
        self.assertEqual(database["game"][0]["appid"], "270150")
        self.assertEqual(database["game"][0]["mods_found"], ["2606099273"])

    def test_discover_with_fallback_requires_working_directory(self) -> None:
        with patch("modmanager.database_ops.SteamScanner.discover_steam_libraries", return_value=[]):
            with self.assertRaises(ValueError):
                discover_with_fallback(working_pathstyle="linux", manual_override_steamlibs=[])

    def test_liveupdate_reports_changes_and_rebuilds_mod(self) -> None:
        db = {
            "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "windows"},
            "steamlib": [
                {
                    "path": "/mnt/d/Games/steamapps",
                    "contains_libraryfolders_vdf": False,
                    "game": ["270150"],
                }
            ],
            "game": [
                {
                    "appid": "270150",
                    "name": "Running with Rifles",
                    "localdate": 0,
                    "basepath": "/mnt/d/Games/steamapps/common/RunningWithRifles",
                    "modpath": "/mnt/d/Games/steamapps/workshop/content/270150",
                    "mods_found": ["2606099273"],
                }
            ],
            "mod": [
                {
                    "mixed_id": "270150:2606099273",
                    "localdate": 0,
                    "path": "/mnt/d/Games/steamapps/workshop/content/270150/2606099273",
                }
            ],
        }

        with patch("modmanager.database_ops.SteamScanner.discover_games_in_library") as mock_games:
            with patch("modmanager.database_ops.SteamScanner.discover_mods_for_game") as mock_mods:
                mock_games.return_value = {
                    "270150": GameInfo(
                        appid="270150",
                        name="Running with Rifles",
                        basepath="/mnt/d/Games/steamapps/common/RunningWithRifles",
                        modpath="/mnt/d/Games/steamapps/workshop/content/270150",
                    ),
                    "107410": GameInfo(
                        appid="107410",
                        name="Arma 3",
                        basepath="/mnt/d/Games/steamapps/common/Arma 3",
                        modpath="/mnt/d/Games/steamapps/workshop/content/107410",
                    ),
                }
                mock_mods.side_effect = [["2606099273", "3428584891"], ["2043567839"]]

                result = liveupdate_database(db)

        self.assertEqual(result["errors"], [])
        self.assertEqual(result["changes"]["games_added"], ["107410"])
        self.assertIn("3428584891", result["changes"]["mods_added"]["270150"])
        updated = result["updated_database"]
        self.assertEqual(len(updated["mod"]), 2)

    def test_regen_rebuilds_game_and_mod(self) -> None:
        db = {
            "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "windows"},
            "steamlib": [
                {
                    "path": "/mnt/d/Games/steamapps",
                    "contains_libraryfolders_vdf": False,
                    "game": ["270150"],
                }
            ],
            "game": [{"appid": "old", "mods_found": ["old"]}],
            "mod": [{"mixed_id": "old:old", "path": "/x", "localdate": 0}],
        }

        with patch("modmanager.database_ops.SteamScanner.discover_games_in_library") as mock_games:
            with patch("modmanager.database_ops.SteamScanner.discover_mods_for_game") as mock_mods:
                mock_games.return_value = {
                    "270150": GameInfo(
                        appid="270150",
                        name="Running with Rifles",
                        basepath="/mnt/d/Games/steamapps/common/RunningWithRifles",
                        modpath="/mnt/d/Games/steamapps/workshop/content/270150",
                    )
                }
                mock_mods.return_value = ["2606099273"]

                result = regen_database(db)

        rebuilt = result["database"]
        self.assertEqual(result["stats"]["games_count"], 1)
        self.assertEqual(rebuilt["game"][0]["appid"], "270150")
        self.assertEqual(rebuilt["mod"][0]["mixed_id"], "270150:2606099273")

    def test_verify_database_integrity_detects_mismatch(self) -> None:
        bad = {
            "steamlib": [],
            "game": [
                {
                    "appid": "270150",
                    "modpath": "/mnt/d/Games/steamapps/workshop/content/270150",
                    "mods_found": ["2606099273"],
                }
            ],
            "mod": [],
        }
        issues = verify_database_integrity(bad)
        self.assertTrue(any("missing mod" in issue for issue in issues))

    def test_discover_with_fallback_manual_only_skips_auto(self) -> None:
        """manual_only=True → auto_libraries is empty (no auto discover)."""
        manual = [{"path": "/mnt/d/Games", "contains_libraryfolders_vdf": False}]

        with patch("modmanager.database_ops.SteamScanner.discover_steam_libraries") as mock_auto:
            with patch("modmanager.database_ops.SteamScanner.discover_games_in_library") as mock_games:
                with patch("modmanager.database_ops.SteamScanner.discover_mods_for_game") as mock_mods:
                    mock_auto.return_value = [SteamLibraryInfo(
                        path="/auto/steamapps",
                        contains_libraryfolders_vdf=True,
                        games_found=["99999"],
                    )]
                    mock_games.return_value = {
                        "270150": GameInfo(
                            appid="270150",
                            name="Running with Rifles",
                            basepath="/mnt/d/Games/steamapps/common/RunningWithRifles",
                            modpath="/mnt/d/Games/steamapps/workshop/content/270150",
                        )
                    }
                    mock_mods.return_value = ["2606099273"]

                    database = discover_with_fallback(
                        working_pathstyle="linux",
                        manual_override_steamlibs=manual,
                        greedy_parsing=True,
                        manual_only=True,
                    )

        # auto should NOT have been called (manual_only bypasses it)
        mock_auto.assert_not_called()
        # Only manual library should appear
        self.assertEqual(len(database["steamlib"]), 1)
        self.assertEqual(database["steamlib"][0]["path"], "/mnt/d/Games/steamapps")

    def test_scan_from_libraries_detects_duplicate_appid(self) -> None:
        """Same appid in two different libraries → warning, first wins."""
        from modmanager.database_ops import _scan_from_libraries
        from modmanager.steam_scanner import SteamScanner

        scanner = SteamScanner(working_pathstyle="linux")
        lib1 = SteamLibraryInfo(
            path="/lib1/steamapps",
            contains_libraryfolders_vdf=False,
            games_found=["270150"],
        )
        lib2 = SteamLibraryInfo(
            path="/lib2/steamapps",
            contains_libraryfolders_vdf=False,
            games_found=["270150"],
        )

        with patch.object(scanner, "discover_games_in_library") as mock_games:
            mock_games.side_effect = [
                {
                    "270150": GameInfo(
                        appid="270150",
                        name="RWR",
                        basepath="/lib1/steamapps/common/RWR",
                        modpath="/lib1/steamapps/workshop/content/270150",
                    ),
                },
                {
                    "270150": GameInfo(
                        appid="270150",
                        name="RWR",
                        basepath="/lib2/steamapps/common/RWR",
                        modpath="/lib2/steamapps/workshop/content/270150",
                    ),
                },
            ]
            with patch.object(scanner, "discover_mods_for_game", return_value=["mod1"]):
                result = _scan_from_libraries(scanner, [lib1, lib2], greedy_parsing=True)

        # Errors should contain E_DUPLICATE_APPID
        self.assertIn("errors", result)
        self.assertTrue(
            any("E_DUPLICATE_APPID" in w for w in result["errors"]),
            msg=f"Expected E_DUPLICATE_APPID in errors, got {result['errors']}",
        )
        # First library's game should be kept (not overwritten)
        self.assertEqual(result["game"][0]["basepath"], "/lib1/steamapps/common/RWR")

    def test_list_games_filtered_by_steamlib(self) -> None:
        db = {
            "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": []}],
            "game": [
                {"appid": "1", "modpath": "/mnt/d/Games/steamapps/workshop/content/1"},
                {"appid": "2", "modpath": "/mnt/e/Games/steamapps/workshop/content/2"},
            ],
            "mod": [],
        }
        filtered = list_games(db, steamlib_path="/mnt/d/Games")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["appid"], "1")


if __name__ == "__main__":
    unittest.main()
