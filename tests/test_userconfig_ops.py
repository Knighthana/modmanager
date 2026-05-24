"""Tests for userconfig_ops module — config lifecycle (init + save)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from modmgr.userconfig_ops import (
    DEFAULTS,
    REQUIRED_KEYS,
    userconfig_init,
    userconfig_save,
)


class TestUserconfigInit(unittest.TestCase):
    """Tests for userconfig_init() — create / patch user_config."""

    def test_creates_new_file_with_defaults(self) -> None:
        """No file → create with all fields."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            result = userconfig_init(path)

            self.assertEqual(set(result.keys()), set(REQUIRED_KEYS))
            # workspace_dir and databases are overridden by platform defaults
            for key in REQUIRED_KEYS:
                if key in ("workspace_dir", "databases"):
                    self.assertIsNotNone(result[key])
                else:
                    self.assertEqual(result[key], DEFAULTS[key])

            # File was actually written
            self.assertTrue(Path(path).exists())

    def test_patches_missing_keys(self) -> None:
        """Existing file missing keys → filled from DEFAULTS."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            partial = {
                "schema_namespace": "KMM_UserConfig",
                "schema_version": "knighthana@0.1.0",
                "baksuffix": "mybak",
                "bakignore": [],
                "rule_sources": {},
                "path_alias": [],
                "workspace_dir": None,
                "databases": {"default": {"path": "/custom/path"}},
            }
            Path(path).write_text(json.dumps(partial), encoding="utf-8")

            result = userconfig_init(path)

            # Existing values preserved
            self.assertEqual(result["baksuffix"], "mybak")
            self.assertEqual(result["databases"]["default"]["path"], "/custom/path")

    def test_preserves_existing_values(self) -> None:
        """Existing custom baksuffix value preserved, not overwritten."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            custom = dict(DEFAULTS)
            custom["baksuffix"] = "custom_suffix"
            Path(path).write_text(json.dumps(custom), encoding="utf-8")

            result = userconfig_init(path)

            self.assertEqual(result["baksuffix"], "custom_suffix")

    def test_platform_defaults_filled_on_create(self) -> None:
        """New file receives platform-specific workspace_dir and database path."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            result = userconfig_init(path)

            # Platform defaults are filled for workspace_dir and databases
            self.assertIsNotNone(result["workspace_dir"])
            self.assertIsNotNone(result["databases"]["default"]["path"])

            # Other fields still have DEFAULTS
            self.assertEqual(result["baksuffix"], DEFAULTS["baksuffix"])

    def test_invalid_json_raises(self) -> None:
        """Corrupt JSON file → ValueError."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            Path(path).write_text("this is not json", encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                userconfig_init(path)
            self.assertIn("Invalid JSON", str(ctx.exception))

    def test_wrong_namespace_raises(self) -> None:
        """Existing file with wrong schema_namespace → ValueError."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            bad = dict(DEFAULTS)
            bad["schema_namespace"] = "WrongNamespace"
            Path(path).write_text(json.dumps(bad), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                userconfig_init(path)
            self.assertIn("Wrong schema_namespace", str(ctx.exception))


class TestUserconfigSave(unittest.TestCase):
    """Tests for userconfig_save() — validate + sync + write."""

    def test_saves_valid_config(self) -> None:
        """Valid data writes successfully."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            # Create a valid config first
            config = userconfig_init(path)

            # Modify and save
            config["baksuffix"] = "newbak"
            userconfig_save(path, config)

            # Reload and verify
            saved = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(saved["baksuffix"], "newbak")

    def test_baksuffix_syncs_bakignore(self) -> None:
        """Changing baksuffix adds to bakignore."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            config = userconfig_init(path)
            # Set initial baksuffix
            config["baksuffix"] = "oldbak"
            config["bakignore"] = []
            userconfig_save(path, config)

            # Change baksuffix and save again
            config["baksuffix"] = "newbak"
            userconfig_save(path, config)

            # bakignore should now contain "newbak"
            saved = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertIn("newbak", saved["bakignore"])

    def test_baksuffix_sync_does_not_duplicate(self) -> None:
        """Same baksuffix → no duplicate in bakignore."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            config = userconfig_init(path)
            config["baksuffix"] = "mybak"
            config["bakignore"] = ["mybak"]
            userconfig_save(path, config)

            # Save again with same baksuffix
            config["baksuffix"] = "mybak"
            userconfig_save(path, config)

            saved = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertEqual(saved["bakignore"].count("mybak"), 1)

    def test_invalid_schema_raises(self) -> None:
        """Data failing schema validation → ValueError."""
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "user_config.json")
            config = userconfig_init(path)

            # Add an unknown key to trigger additionalProperties violation
            config["unknown_key"] = "should_not_exist"

            with self.assertRaises(ValueError) as ctx:
                userconfig_save(path, config)
            self.assertIn("Schema validation failed", str(ctx.exception))

            # File content unchanged (write didn't happen)
            saved = json.loads(Path(path).read_text(encoding="utf-8"))
            self.assertNotIn("unknown_key", saved)


if __name__ == "__main__":
    unittest.main()
