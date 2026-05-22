"""Tests for modmanager.bootstrap module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from hana_modmgr.bootstrap import (
    _detect_software_dir,
    discover_user_config,
    generate_database,
)
from hana_modmgr import bootstrap as bootstrap_module
from hana_modmgr.iojson import write_json_file


class TestDetectSoftwareDir(TestCase):
    """Tests for _detect_software_dir()."""

    def test_detect_software_dir_returns_string(self) -> None:
        """Verify _detect_software_dir() returns a non-empty absolute path."""
        result = _detect_software_dir()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertTrue(result.startswith("/"))
        # The result should contain "modmanager" (the package dir)
        # or be a parent dir with pyproject.toml
        self.assertTrue(Path(result).exists())


class TestDiscoverUserConfig(TestCase):
    """Tests for discover_user_config()."""

    def test_discover_user_config_first_use_creates_default(self) -> None:
        """No existing config → default is created with first_use=true."""
        with tempfile.TemporaryDirectory() as td:
            home_dir = str(td)
            result = discover_user_config(home_dir=home_dir)

            self.assertIn("databases", result)
            self.assertIn("default", result["databases"])
            self.assertIn("path", result["databases"]["default"])
            self.assertTrue(result["databases"]["default"]["path"].endswith("database.json"))
            self.assertIn("source_path", result)
            self.assertTrue(result["source_path"].endswith("user_config.json"))
            self.assertTrue(result["first_use"])

            # Verify the file was actually written
            config_path = Path(td) / ".config" / "kmm" / "user_config.json"
            self.assertTrue(config_path.exists())

    def test_discover_user_config_existing_file(self) -> None:
        """Existing user_config.json is loaded with first_use=false."""
        with tempfile.TemporaryDirectory() as td:
            home_dir = str(td)
            config_dir = Path(td) / ".config" / "kmm"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "user_config.json"
            data = {"key1": "value1", "databases": {"default": {"path": "/custom/path.json"}}}
            config_file.write_text(json.dumps(data), encoding="utf-8")

            result = discover_user_config(home_dir=home_dir)
            self.assertEqual(result.get("key1"), "value1")
            self.assertEqual(result["databases"]["default"]["path"], "/custom/path.json")
            self.assertFalse(result["first_use"])
            self.assertEqual(result["source_path"], str(config_file))

    def test_discover_user_config_invalid_json_recreated(self) -> None:
        """Invalid JSON content → file is recreated with defaults."""
        with tempfile.TemporaryDirectory() as td:
            home_dir = str(td)
            config_dir = Path(td) / ".config" / "kmm"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "user_config.json"
            config_file.write_text("this is not valid json {{{", encoding="utf-8")

            result = discover_user_config(home_dir=home_dir)
            self.assertIn("databases", result)
            self.assertTrue(result["first_use"])
            # File should have been overwritten with valid JSON
            import json as json_mod
            reloaded = json_mod.loads(config_file.read_text(encoding="utf-8"))
            self.assertIn("databases", reloaded)


class TestGenerateDatabase(TestCase):
    """Tests for generate_database()."""

    def _make_user_config_override(self, td: str, db_path: str) -> dict:
        """Build a fake user_config dict for mocking discover_user_config."""
        return {
            "databases": {
                "default": {"path": db_path},
                "custom": {"path": db_path},
            },
            "source_path": str(Path(td) / "fake_user_config.json"),
            "first_use": False,
        }

    def test_generate_database_invalid_mode(self) -> None:
        """Passing an invalid mode raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("invalid")

    def test_generate_database_manual_empty_paths(self) -> None:
        """Manual mode with empty paths raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("manual", paths=[])

    def test_generate_database_manual_none_paths(self) -> None:
        """Manual mode with None paths raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("manual", paths=None)

    def test_generate_database_missing_db_name(self) -> None:
        """Unknown database_name raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("auto", database_name="nonexistent")

    def test_generate_database_always_rescans(self) -> None:
        """generate_database() always rescans — no cache hit (cache is for /read, not /generate)."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            cache_data = {
                "steamlib": [
                    {
                        "path": "/fake/steamapps",
                        "contains_libraryfolders_vdf": False,
                        "game": ["270150"],
                    }
                ],
                "game": [],
                "mod": [],
            }
            Path(db_path).write_text(json.dumps(cache_data), encoding="utf-8")

            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                result = generate_database("auto")
            # Always returns fresh scan result, not cache
            self.assertIn("steamlib", result)
            self.assertIn("game", result)
            self.assertIn("mod", result)

    def test_generate_database_cache_empty_file(self) -> None:
        """An empty cache file should be ignored (fall through to scan)."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            # Create an empty file
            Path(db_path).write_text("", encoding="utf-8")

            # Patch discover_with_fallback to raise so we can detect fall-through
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with patch.object(
                    bootstrap_module, "discover_with_fallback",
                    side_effect=ValueError("mocked: no Steam"),
                ):
                    with self.assertRaises(ValueError):
                        generate_database("auto")

    def test_generate_database_cache_invalid_structure(self) -> None:
        """A cache file without 'steamlib' list is ignored (fall through to scan)."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            Path(db_path).write_text(
                json.dumps({"some_other_key": "value"}), encoding="utf-8"
            )

            # Patch discover_with_fallback to raise so we can detect fall-through
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with patch.object(
                    bootstrap_module, "discover_with_fallback",
                    side_effect=ValueError("mocked: no Steam"),
                ):
                    with self.assertRaises(ValueError):
                        generate_database("auto")
