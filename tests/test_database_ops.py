from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modmanager_cli.database_ops import (
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
from modmanager_cli.steam_scanner import GameInfo, SteamLibraryInfo


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

    def test_game_crud_updates_membership_and_dommod(self) -> None:
        db = {
            "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "windows"},
            "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": []}],
            "game": [],
            "dommod": [],
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
        self.assertEqual(db["dommod"][0]["mixed_id"], "270150:2606099273")

        ok, _ = update_manual_game(db, appid="270150", updates={"mods_found": ["3428584891"]})
        self.assertTrue(ok)
        self.assertEqual(db["dommod"][0]["mixed_id"], "270150:3428584891")

        removed, _ = remove_manual_game(db, appid="270150")
        self.assertTrue(removed)
        self.assertEqual(db["game"], [])
        self.assertEqual(db["dommod"], [])

    def test_discover_with_fallback_uses_manual_when_auto_fails(self) -> None:
        manual = [{"path": "/mnt/d/Games", "contains_libraryfolders_vdf": False}]

        with patch("modmanager_cli.database_ops.SteamScanner.discover_steam_libraries", return_value=[]):
            with patch("modmanager_cli.database_ops.SteamScanner.discover_games_in_library") as mock_games:
                with patch("modmanager_cli.database_ops.SteamScanner.discover_mods_for_game") as mock_mods:
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
        with patch("modmanager_cli.database_ops.SteamScanner.discover_steam_libraries", return_value=[]):
            with self.assertRaises(ValueError):
                discover_with_fallback(working_pathstyle="linux", manual_override_steamlibs=[])

    def test_liveupdate_reports_changes_and_rebuilds_dommod(self) -> None:
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
            "dommod": [
                {
                    "mixed_id": "270150:2606099273",
                    "localdate": 0,
                    "path": "/mnt/d/Games/steamapps/workshop/content/270150/2606099273",
                }
            ],
        }

        with patch("modmanager_cli.database_ops.SteamScanner.discover_games_in_library") as mock_games:
            with patch("modmanager_cli.database_ops.SteamScanner.discover_mods_for_game") as mock_mods:
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
        self.assertEqual(len(updated["dommod"]), 2)

    def test_regen_rebuilds_game_and_dommod(self) -> None:
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
            "dommod": [{"mixed_id": "old:old", "path": "/x", "localdate": 0}],
        }

        with patch("modmanager_cli.database_ops.SteamScanner.discover_games_in_library") as mock_games:
            with patch("modmanager_cli.database_ops.SteamScanner.discover_mods_for_game") as mock_mods:
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
        self.assertEqual(rebuilt["dommod"][0]["mixed_id"], "270150:2606099273")

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
            "dommod": [],
        }
        issues = verify_database_integrity(bad)
        self.assertTrue(any("missing dommod" in issue for issue in issues))

    def test_list_games_filtered_by_steamlib(self) -> None:
        db = {
            "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": []}],
            "game": [
                {"appid": "1", "modpath": "/mnt/d/Games/steamapps/workshop/content/1"},
                {"appid": "2", "modpath": "/mnt/e/Games/steamapps/workshop/content/2"},
            ],
            "dommod": [],
        }
        filtered = list_games(db, steamlib_path="/mnt/d/Games")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["appid"], "1")


if __name__ == "__main__":
    unittest.main()
