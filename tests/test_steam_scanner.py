"""Test cases for M1.1 system scanner (TDD - tests first).

Test structure:
- Basic parsing tests (VDF/ACF formats)
- Discovery tests (finding libraries, games, mods)
- Integration tests (full database generation)
- Edge cases and error handling
"""

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from modmgr.steam_scanner import (
    SteamScanner,
    SteamLibraryInfo,
    GameInfo,
    DatabaseInfo,
    scan_and_generate_database,
)
from modmgr.vdf_parser import parse_libraryfolders_vdf
from modmgr.acf_parser import parse_appmanifest_acf, parse_appworkshop_acf


class TestVDFParser(unittest.TestCase):
    """Test VDF (libraryfolders.vdf) parsing."""

    def test_parse_valid_libraryfolders_vdf(self):
        """Parse valid libraryfolders.vdf with multiple libraries."""
        # Create sample VDF file
        vdf_content = '''"LibraryFolders"
{
    "0"
    {
        "path"        "C:\\\\Program Files (x86)\\\\Steam\\\\steamapps"
        "label"        ""
        "contentid"    "1234567890"
    }
    "1"
    {
        "path"        "D:\\\\Games\\\\steamapps"
        "label"        ""
        "contentid"    "9876543210"
    }
}'''
        with tempfile.TemporaryDirectory() as tmpdir:
            vdf_path = Path(tmpdir) / "libraryfolders.vdf"
            vdf_path.write_text(vdf_content)

            result = parse_libraryfolders_vdf(str(vdf_path))

            # Assertions
            self.assertIn("libraries", result)
            self.assertEqual(len(result["libraries"]), 2)
            self.assertEqual(result["libraries"][0]["path"], 
                           "C:\\Program Files (x86)\\Steam\\steamapps")
            self.assertEqual(result["libraries"][1]["path"], 
                           "D:\\Games\\steamapps")

    def test_parse_vdf_with_games_section(self):
        """Parse VDF containing game app IDs."""
        vdf_content = '''"LibraryFolders"
{
    "0"
    {
        "path"        "C:\\\\Steam\\\\steamapps"
        "games"
        {
            "270150"    "1"
            "228980"    "1"
        }
    }
}'''
        with tempfile.TemporaryDirectory() as tmpdir:
            vdf_path = Path(tmpdir) / "libraryfolders.vdf"
            vdf_path.write_text(vdf_content)

            result = parse_libraryfolders_vdf(str(vdf_path))

            self.assertIn("libraries", result)
            self.assertIn("games", result["libraries"][0])
            self.assertIn("270150", result["libraries"][0]["games"])

    def test_parse_vdf_missing_file(self):
        """Raise FileNotFoundError when VDF file missing."""
        with self.assertRaises(FileNotFoundError):
            parse_libraryfolders_vdf("/nonexistent/libraryfolders.vdf")

    def test_parse_vdf_with_apps_section(self):
        """Real Steam VDF uses 'apps' key instead of 'games'."""
        vdf_content = '''"libraryfolders"
{
    "0"
    {
        "path"        "C:\\\\Program Files (x86)\\\\Steam"
        "apps"
        {
            "228980"    "1265534266"
        }
    }
    "1"
    {
        "path"        "D:\\\\Games"
        "apps"
        {
            "270150"    "2560340591"
            "292030"    "65870939181"
        }
    }
}'''
        with tempfile.TemporaryDirectory() as tmpdir:
            vdf_path = Path(tmpdir) / "libraryfolders.vdf"
            vdf_path.write_text(vdf_content)

            result = parse_libraryfolders_vdf(str(vdf_path))

            self.assertEqual(len(result["libraries"]), 2)
            self.assertIn("228980", result["libraries"][0]["games"])
            self.assertIn("270150", result["libraries"][1]["games"])
            self.assertIn("292030", result["libraries"][1]["games"])


class TestACFParser(unittest.TestCase):
    """Test ACF (appmanifest/appworkshop) parsing."""

    def test_parse_appmanifest_acf(self):
        """Parse appmanifest_*.acf to get game info."""
        acf_content = '''"AppState"
{
    "appid"        "270150"
    "name"        "Running with Rifles"
    "installdir"    "Running with Rifles"
    "StateFlags"    "4"
}'''
        with tempfile.TemporaryDirectory() as tmpdir:
            acf_path = Path(tmpdir) / "appmanifest_270150.acf"
            acf_path.write_text(acf_content)

            result = parse_appmanifest_acf(str(acf_path))

            self.assertEqual(result["appid"], "270150")
            self.assertEqual(result["name"], "Running with Rifles")
            self.assertEqual(result["installdir"], "Running with Rifles")

    def test_parse_appworkshop_acf(self):
        """Parse appworkshop_*.acf to get workshop mod IDs."""
        acf_content = '''"WorkshopItemDetails"
{
    "0"
    {
        "publishedfileid"    "2606099273"
        "installed"        "1"
    }
    "1"
    {
        "publishedfileid"    "3428584891"
        "installed"        "1"
    }
}'''
        with tempfile.TemporaryDirectory() as tmpdir:
            acf_path = Path(tmpdir) / "appworkshop_270150.acf"
            acf_path.write_text(acf_content)

            result = parse_appworkshop_acf(str(acf_path))

            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["publishedfileid"], "2606099273")
            self.assertEqual(result[1]["publishedfileid"], "3428584891")


class TestSteamScannerDiscovery(unittest.TestCase):
    """Test Steam library and game discovery."""

    def test_discover_steam_libraries_finds_paths(self):
        """Discover Steam library paths on system."""
        scanner = SteamScanner()

        # Mock the file system to return known paths
        with patch("modmgr.steam_scanner.Path.exists") as mock_exists:
            mock_exists.return_value = True
            libraries = scanner.discover_steam_libraries()

            # Should find at least one library (mocked)
            self.assertIsInstance(libraries, list)
            # In real run, would check for actual libraries

    def test_discover_games_in_library(self):
        """Discover installed games in a Steam library."""
        scanner = SteamScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir)
            steamapps = lib_path / "steamapps"
            steamapps.mkdir()

            # Create mock appmanifest file
            manifest = steamapps / "appmanifest_270150.acf"
            manifest.write_text('''"AppState"
{
    "appid"        "270150"
    "name"        "Running with Rifles"
    "installdir"    "Running with Rifles"
}''')

            # Mock ACF parser
            with patch("modmgr.steam_scanner.parse_appmanifest_acf") as mock_parse:
                mock_parse.return_value = {
                    "appid": "270150",
                    "name": "Running with Rifles",
                    "installdir": "Running with Rifles",
                }

                games = scanner.discover_games_in_library(str(steamapps))

                # Should find the game
                self.assertIn("270150", games)
                self.assertEqual(games["270150"].appid, "270150")

    def test_discover_mods_for_game(self):
        """Discover installed mods for a game."""
        scanner = SteamScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            mod_root = Path(tmpdir)

            # Create mock mod directories
            (mod_root / "2606099273").mkdir()
            (mod_root / "3428584891").mkdir()

            mods = scanner.discover_mods_for_game("270150", str(mod_root))

            self.assertEqual(len(mods), 2)
            self.assertIn("2606099273", mods)
            self.assertIn("3428584891", mods)

    def test_discover_steam_libraries_expands_from_main_vdf(self):
        """Discover additional libraries listed in the main libraryfolders.vdf."""
        scanner = SteamScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            main_lib = fake_home / ".steam" / "root" / "steamapps"
            extra_lib = fake_home / "Games" / "steamapps"
            main_lib.mkdir(parents=True)
            extra_lib.mkdir(parents=True)

            vdf_content = f'''"LibraryFolders"
{{
    "0"
    {{
        "path"        "{str(main_lib).replace('\\', '\\\\')}"
        "games"
        {{
            "228980"    "1"
        }}
    }}
    "1"
    {{
        "path"        "{str(extra_lib).replace('\\', '\\\\')}"
        "games"
        {{
            "270150"    "1"
        }}
    }}
}}'''
            (main_lib / "libraryfolders.vdf").write_text(vdf_content)

            with patch("modmgr.steam_scanner.Path.home") as mock_home:
                mock_home.return_value = fake_home
                libraries = scanner.discover_steam_libraries()

            discovered_paths = {lib.path for lib in libraries}
            self.assertIn(str(main_lib), discovered_paths)
            self.assertIn(str(extra_lib), discovered_paths)

    def test_discover_steam_libraries_appends_steamapps_to_root_path(self):
        """VDF 'path' is Steam root (no steamapps suffix); scanner must append it."""
        scanner = SteamScanner(working_pathstyle="linux")

        with tempfile.TemporaryDirectory() as tmpdir:
            fake_home = Path(tmpdir)
            # Main lib: path already ends in steamapps (as placed in common_paths)
            main_steamapps = fake_home / ".steam" / "root" / "steamapps"
            main_steamapps.mkdir(parents=True)
            # Extra lib: VDF path is the Steam root dir (WITHOUT steamapps)
            extra_root = fake_home / "Games"
            extra_steamapps = extra_root / "steamapps"
            extra_steamapps.mkdir(parents=True)

            # VDF uses 'apps' key and root path without steamapps suffix
            vdf_content = f'''"libraryfolders"
{{
    "0"
    {{
        "path"        "{str(main_steamapps).replace(chr(92), chr(92)*2)}"
        "apps"
        {{
            "228980"    "1"
        }}
    }}
    "1"
    {{
        "path"        "{str(extra_root).replace(chr(92), chr(92)*2)}"
        "apps"
        {{
            "270150"    "1"
        }}
    }}
}}'''
            (main_steamapps / "libraryfolders.vdf").write_text(vdf_content)

            with patch("modmgr.steam_scanner.Path.home") as mock_home:
                mock_home.return_value = fake_home
                libraries = scanner.discover_steam_libraries()

            discovered_paths = {lib.path for lib in libraries}
            # The extra library path must end with 'steamapps'
            self.assertTrue(
                any(p.endswith("steamapps") and "Games" in p for p in discovered_paths),
                f"Expected a path ending in steamapps under Games, got: {discovered_paths}"
            )
            # games_found must contain the appid from VDF
            extra = next(lib for lib in libraries if "Games" in lib.path)
            self.assertIn("270150", extra.games_found or [])


class TestSteamScannerDatabaseGeneration(unittest.TestCase):
    """Test complete database generation."""

    def test_generate_database_structure(self):
        """Generate database.json with correct structure."""
        scanner = SteamScanner(working_pathstyle="linux")

        # Mock all discovery methods
        with patch.object(scanner, "discover_steam_libraries") as mock_libs:
            with patch.object(scanner, "discover_games_in_library") as mock_games:
                mock_libs.return_value = [
                    SteamLibraryInfo(
                        path="/mnt/c/Program Files/Steam/steamapps/",
                        contains_libraryfolders_vdf=True
                    )
                ]
                mock_games.return_value = {
                    "270150": GameInfo(
                        appid="270150",
                        name="Running with Rifles",
                        basepath="/mnt/c/Program Files/Steam/steamapps/common/RunningWithRifles",
                        modpath="/mnt/c/Program Files/Steam/steamapps/workshop/content/270150/",
                        mods_found=["2606099273", "3428584891"]
                    )
                }

                database = scanner.generate_database()

                # Check structure
                self.assertIsInstance(database, DatabaseInfo)
                self.assertIn("workingpathstyle", database.OS)
                self.assertEqual(database.OS["workingpathstyle"], "linux")
                self.assertGreater(len(database.steamlib), 0)
                self.assertGreater(len(database.game), 0)
                self.assertIn("game", database.steamlib[0])

    def test_save_database_to_file(self):
        """Save generated database to file."""
        scanner = SteamScanner()
        database = DatabaseInfo(
            OS={"workingpathstyle": "linux", "steamlibpathstyle": "windows"},
            steamlib=[],
            game=[]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "database.json"

            result = scanner.save_database(database, str(output_path))

            self.assertTrue(result)
            self.assertTrue(output_path.exists())
            # Verify it's valid JSON
            import json
            with open(output_path) as f:
                loaded = json.load(f)
                self.assertIn("OS", loaded)
                self.assertIn("game", loaded)

    def test_non_greedy_skips_mod_parse_outside_vdf_scope(self):
        """Default mode should skip mod parsing for appids outside VDF game list."""
        scanner = SteamScanner(working_pathstyle="linux")
        lib = SteamLibraryInfo(
            path="/fake/steamapps",
            contains_libraryfolders_vdf=True,
            games_found=["111111"],
        )

        with patch.object(scanner, "discover_steam_libraries", return_value=[lib]):
            with patch.object(scanner, "discover_games_in_library") as mock_games:
                with patch.object(scanner, "discover_mods_for_game") as mock_mods:
                    mock_games.return_value = {
                        "222222": GameInfo(
                            appid="222222",
                            name="Out Of Scope Game",
                            basepath="/fake/steamapps/common/game",
                            modpath="/fake/steamapps/workshop/content/222222",
                        )
                    }
                    mock_mods.return_value = ["999"]

                    database = scanner.generate_database(greedy_parsing=False)

                    mock_mods.assert_not_called()
                    self.assertEqual(database.game[0]["mods_found"], [])

    def test_greedy_parses_mods_outside_vdf_scope(self):
        """Greedy mode should allow mod parsing for appids outside VDF game list."""
        scanner = SteamScanner(working_pathstyle="linux")
        lib = SteamLibraryInfo(
            path="/fake/steamapps",
            contains_libraryfolders_vdf=True,
            games_found=["111111"],
        )

        with patch.object(scanner, "discover_steam_libraries", return_value=[lib]):
            with patch.object(scanner, "discover_games_in_library") as mock_games:
                with patch.object(scanner, "discover_mods_for_game") as mock_mods:
                    mock_games.return_value = {
                        "222222": GameInfo(
                            appid="222222",
                            name="Out Of Scope Game",
                            basepath="/fake/steamapps/common/game",
                            modpath="/fake/steamapps/workshop/content/222222",
                        )
                    }
                    mock_mods.return_value = ["999"]

                    database = scanner.generate_database(greedy_parsing=True)

                    mock_mods.assert_called_once_with("222222", "/fake/steamapps/workshop/content/222222")
                    self.assertEqual(database.game[0]["mods_found"], ["999"])


class TestSteamScannerEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_no_steam_libraries_found(self):
        """Handle case when no Steam libraries found."""
        scanner = SteamScanner()

        with patch.object(scanner, "discover_steam_libraries") as mock:
            mock.return_value = []

            with self.assertRaises(Exception):
                # Should raise error if no libraries found
                scanner.generate_database()

    def test_game_with_no_mods(self):
        """Handle game with no installed mods."""
        scanner = SteamScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            mod_root = Path(tmpdir)
            # Create empty directory (no mods)

            mods = scanner.discover_mods_for_game("270150", str(mod_root))

            self.assertEqual(len(mods), 0)

    def test_pathstyle_detection_windows(self):
        """Detect Windows path style (backslashes)."""
        # This would be tested in vdf_parser
        pass

    def test_pathstyle_detection_linux(self):
        """Detect Linux path style (forward slashes)."""
        # This would be tested in vdf_parser
        pass

    def test_wsl_path_conversion(self):
        """Convert WSL paths (/mnt/c/...) to Linux style."""
        # This would be tested in pathstyle module
        pass


class TestIntegration(unittest.TestCase):
    """Integration tests - full scanning workflow."""

    def test_end_to_end_database_generation(self):
        """Full end-to-end: scan system → generate database.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "database.json"

            # This would do the full scan in real scenario
            # result = scan_and_generate_database(str(output_path))
            # self.assertTrue(output_path.exists())

            # For now, just verify the function exists
            self.assertTrue(callable(scan_and_generate_database))


if __name__ == "__main__":
    unittest.main()
