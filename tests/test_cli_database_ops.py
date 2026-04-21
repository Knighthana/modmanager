from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modmanager_cli.cli import main
from modmanager_cli.iojson import load_json_file, write_json_file


class CliDatabaseOpsTests(unittest.TestCase):
    def test_steamlib_add_command_updates_database_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "database.json"
            write_json_file(db_path, {"steamlib": [], "game": [], "dommod": []})

            with patch(
                "sys.argv",
                [
                    "modmanger-cli",
                    "steamlib",
                    "add",
                    "--database",
                    str(db_path),
                    "--path",
                    "/mnt/d/Games",
                ],
            ):
                code = main()

            self.assertEqual(code, 0)
            db = load_json_file(db_path)
            self.assertEqual(db["steamlib"][0]["path"], "/mnt/d/Games/steamapps")

    def test_steamlib_remove_missing_returns_error_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "database.json"
            write_json_file(db_path, {"steamlib": [], "game": [], "dommod": []})

            with patch(
                "sys.argv",
                [
                    "modmanger-cli",
                    "steamlib",
                    "remove",
                    "--database",
                    str(db_path),
                    "--path",
                    "/mnt/d/Games",
                ],
            ):
                code = main()

            self.assertEqual(code, 2)

    def test_steamlib_list_missing_database_returns_error(self) -> None:
        missing_path = "/tmp/not_exists_database_for_cli_test.json"

        with patch(
            "sys.argv",
            [
                "modmanger-cli",
                "steamlib",
                "list",
                "--database",
                missing_path,
            ],
        ):
            with patch("sys.stderr", new_callable=io.StringIO) as err:
                code = main()

        self.assertEqual(code, 2)
        self.assertIn("failed to load database", err.getvalue())

    def test_liveupdate_command_persists_updated_database(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "database.json"
            write_json_file(
                db_path,
                {
                    "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": []}],
                    "game": [],
                    "dommod": [],
                },
            )

            mocked_result = {
                "updated_database": {
                    "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": ["270150"]}],
                    "game": [{"appid": "270150", "modpath": "/mnt/d/Games/steamapps/workshop/content/270150", "mods_found": []}],
                    "dommod": [],
                },
                "changes": {"games_added": ["270150"], "games_removed": [], "games_updated": [], "mods_added": {}, "mods_removed": {}},
                "warnings": [],
                "errors": [],
            }

            with patch("modmanager_cli.cli.liveupdate_database", return_value=mocked_result):
                with patch(
                    "sys.argv",
                    [
                        "modmanger-cli",
                        "liveupdate",
                        "--database",
                        str(db_path),
                    ],
                ):
                    code = main()

            self.assertEqual(code, 0)
            db = load_json_file(db_path)
            self.assertEqual(db["game"][0]["appid"], "270150")

    def test_liveupdate_empty_steamlib_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "database.json"
            write_json_file(
                db_path,
                {
                    "steamlib": [],
                    "game": [],
                    "dommod": [],
                },
            )

            with patch(
                "sys.argv",
                [
                    "modmanger-cli",
                    "liveupdate",
                    "--database",
                    str(db_path),
                ],
            ):
                with patch("sys.stderr", new_callable=io.StringIO) as err:
                    code = main()

            self.assertEqual(code, 2)
            self.assertIn("liveupdate failed", err.getvalue())

    def test_regen_command_persists_rebuilt_database(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "database.json"
            write_json_file(
                db_path,
                {
                    "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": ["270150"]}],
                    "game": [{"appid": "old"}],
                    "dommod": [{"mixed_id": "old:old", "path": "/x", "localdate": 0}],
                },
            )

            mocked_result = {
                "database": {
                    "steamlib": [{"path": "/mnt/d/Games/steamapps", "contains_libraryfolders_vdf": False, "game": ["270150"]}],
                    "game": [{"appid": "270150", "modpath": "/mnt/d/Games/steamapps/workshop/content/270150", "mods_found": ["2606099273"]}],
                    "dommod": [{"mixed_id": "270150:2606099273", "path": "/mnt/d/Games/steamapps/workshop/content/270150/2606099273", "localdate": 0}],
                },
                "stats": {"libraries_count": 1, "games_count": 1, "mods_count": 1},
                "errors": [],
            }

            with patch("modmanager_cli.cli.regen_database", return_value=mocked_result):
                with patch(
                    "sys.argv",
                    [
                        "modmanger-cli",
                        "regen",
                        "--database",
                        str(db_path),
                    ],
                ):
                    code = main()

            self.assertEqual(code, 0)
            db = load_json_file(db_path)
            self.assertEqual(db["dommod"][0]["mixed_id"], "270150:2606099273")

    def test_regen_empty_steamlib_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "database.json"
            write_json_file(
                db_path,
                {
                    "steamlib": [],
                    "game": [],
                    "dommod": [],
                },
            )

            with patch(
                "sys.argv",
                [
                    "modmanger-cli",
                    "regen",
                    "--database",
                    str(db_path),
                ],
            ):
                with patch("sys.stderr", new_callable=io.StringIO) as err:
                    code = main()

            self.assertEqual(code, 2)
            self.assertIn("regen failed", err.getvalue())

    def test_legacy_mode_missing_errors_key_defaults_to_success(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "config.json"
            db_path = Path(td) / "database.json"
            write_json_file(config_path, {"mod": []})
            write_json_file(db_path, {"game": []})

            with patch("modmanager_cli.cli.compute_mapping", return_value={"forest": [], "final_mapping": []}):
                with patch(
                    "sys.argv",
                    [
                        "modmanger-cli",
                        "--config",
                        str(config_path),
                        "--database",
                        str(db_path),
                    ],
                ):
                    code = main()

            self.assertEqual(code, 0)

    def test_legacy_mode_invalid_json_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            config_path = Path(td) / "config.json"
            db_path = Path(td) / "database.json"
            config_path.write_text("{bad-json", encoding="utf-8")
            write_json_file(db_path, {"game": []})

            with patch(
                "sys.argv",
                [
                    "modmanger-cli",
                    "--config",
                    str(config_path),
                    "--database",
                    str(db_path),
                ],
            ):
                with patch("sys.stderr", new_callable=io.StringIO) as err:
                    code = main()

            self.assertEqual(code, 2)
            self.assertIn("failed to load inputs", err.getvalue())


if __name__ == "__main__":
    unittest.main()
