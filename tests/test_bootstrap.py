"""Tests for modmanager.bootstrap module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from modmgr.bootstrap import (
    _detect_software_dir,
    discover_user_config,
    generate_database,
)
from modmgr import bootstrap as bootstrap_module
from modmgr.iojson import write_json_file


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
        """No existing config at config_index → default is created."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            config, returned_index = discover_user_config(config_index=config_index)

            self.assertIn("databases", config)
            self.assertIn("default", config["databases"])
            self.assertIn("path", config["databases"]["default"])
            self.assertTrue(config["databases"]["default"]["path"].endswith("database.json"))
            self.assertNotIn("source_path", config)
            self.assertNotIn("first_use", config)
            self.assertEqual(returned_index, config_index)

            # Verify the file was actually written
            self.assertTrue(Path(config_index).exists())

    def test_discover_user_config_existing_file(self) -> None:
        """Existing user_config.json is loaded."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            data = {
                "schema_namespace": "KMM_UserConfig",
                "schema_version": "knighthana@0.1.0",
                "baksuffix": "kmmbackup",
                "bakignore": [],
                "rule_sources": {},
                "path_alias": [],
                "workspace_dir": "/tmp/ws",
                "databases": {"default": {"path": "/custom/path.json"}},
            }
            Path(config_index).write_text(json.dumps(data), encoding="utf-8")

            config, returned_index = discover_user_config(config_index=config_index)
            self.assertEqual(config.get("key1"), None)
            self.assertEqual(config["databases"]["default"]["path"], "/custom/path.json")
            self.assertNotIn("first_use", config)
            self.assertNotIn("source_path", config)
            self.assertEqual(returned_index, config_index)

    def test_discover_user_config_invalid_json_raises(self) -> None:
        """Invalid JSON content → ValueError."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            Path(config_index).write_text("this is not valid json {{{", encoding="utf-8")

            with self.assertRaises(ValueError):
                discover_user_config(config_index=config_index)

    def test_discover_user_config_empty_config_index_raises(self) -> None:
        """Empty config_index → ValueError."""
        with self.assertRaises(ValueError):
            discover_user_config(config_index="")

    def test_discover_user_config_none_config_index_raises(self) -> None:
        """None config_index → ValueError."""
        with self.assertRaises(ValueError):
            discover_user_config(config_index=None)  # type: ignore[arg-type]


class TestGenerateDatabase(TestCase):
    """Tests for generate_database()."""

    def _make_user_config_override(self, td: str, db_path: str) -> tuple[dict, str]:
        """Build a fake (user_config, config_index) for mocking discover_user_config."""
        config = {
            "databases": {
                "default": {"path": db_path},
                "custom": {"path": db_path},
            },
        }
        config_index = str(Path(td) / "fake_user_config.json")
        return (config, config_index)

    def test_generate_database_invalid_mode(self) -> None:
        """Passing an invalid mode raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("invalid", config_index=fake_config[1])

    def test_generate_database_manual_empty_paths(self) -> None:
        """Manual mode with empty paths raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("manual", config_index=fake_config[1], paths=[])

    def test_generate_database_manual_none_paths(self) -> None:
        """Manual mode with None paths raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("manual", config_index=fake_config[1], paths=None)

    def test_generate_database_missing_db_name(self) -> None:
        """Unknown database_name raises ValueError."""
        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            fake_config = self._make_user_config_override(td, db_path)
            with patch.object(bootstrap_module, "discover_user_config", return_value=fake_config):
                with self.assertRaises(ValueError):
                    generate_database("auto", config_index=fake_config[1], database_name="nonexistent")

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
                result = generate_database("auto", config_index=fake_config[1])
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
                        generate_database("auto", config_index=fake_config[1])

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
                        generate_database("auto", config_index=fake_config[1])

    def _complete_config(
        self,
        overrides: dict | None = None,
    ) -> dict:
        """Return a config dict with all REQUIRED_KEYS."""
        cfg = {
            "schema_namespace": "KMM_UserConfig",
            "schema_version": "knighthana@0.1.0",
            "baksuffix": "kmmbackup",
            "bakignore": [],
            "rule_sources": [],
            "path_alias": [],
            "workspace_dir": "/tmp/ws",
            "databases": {"default": {"path": "/tmp/db.json"}},
        }
        if overrides:
            cfg.update(overrides)
        return cfg

    def test_explicit_path_used(self) -> None:
        """Explicit config_index loads the correct file."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "custom_config.json")
            Path(config_index).parent.mkdir(parents=True, exist_ok=True)
            Path(config_index).write_text(json.dumps(self._complete_config({
                "databases": {"custom_db": {"path": "/custom/db.json"}},
            })), encoding="utf-8")
            config, returned_index = discover_user_config(config_index=config_index)
            assert returned_index == config_index

    def test_first_use_creates_default(self) -> None:
        """config_index with no existing config creates one."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "my_config.json")
            config, returned_index = discover_user_config(config_index=config_index)
            assert "source_path" not in config
            assert "first_use" not in config
            assert "schema_namespace" in config
            assert returned_index == config_index
            assert Path(config_index).exists()

    def test_default_config_contains_required_fields(self) -> None:
        """First-use default config contains all required fields per DESIGN_BOOTSTRAP §1.2."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            config, _ = discover_user_config(config_index=config_index)
            assert "schema_namespace" in config
            assert "schema_version" in config
            assert "baksuffix" in config
            assert "bakignore" in config
            assert "rule_sources" in config
            assert "path_alias" in config
            assert "workspace_dir" in config
            assert "databases" in config
            assert "source_path" not in config
            assert "first_use" not in config
            assert isinstance(config["databases"], dict)
            assert "default" in config["databases"]
            assert "path" in config["databases"]["default"]

    def test_databases_preserved_as_configured(self) -> None:
        """User-configured databases paths are preserved, not overwritten."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            Path(config_index).parent.mkdir(parents=True, exist_ok=True)
            Path(config_index).write_text(json.dumps(self._complete_config({
                "databases": {
                    "default": {"path": "/custom/db.json"},
                    "secondary": {"path": "/other/db.json"},
                },
            })), encoding="utf-8")
            config, _ = discover_user_config(config_index=config_index)
            assert config["databases"]["default"]["path"] == "/custom/db.json"
            assert config["databases"]["secondary"]["path"] == "/other/db.json"

    def test_rule_sources_preserved(self) -> None:
        """rule_sources from config are preserved."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            Path(config_index).parent.mkdir(parents=True, exist_ok=True)
            Path(config_index).write_text(json.dumps(self._complete_config({
                "rule_sources": ["/rules/", "/extra/mods.kmmrule.json"],
            })), encoding="utf-8")
            config, _ = discover_user_config(config_index=config_index)
            assert "/rules/" in config.get("rule_sources", [])
            assert "/extra/mods.kmmrule.json" in config.get("rule_sources", [])

    def test_workspace_dir_created_with_default(self) -> None:
        """workspace_dir is filled with platform default when created."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            config, _ = discover_user_config(config_index=config_index)
            assert "workspace_dir" in config
            assert config["workspace_dir"] is not None
