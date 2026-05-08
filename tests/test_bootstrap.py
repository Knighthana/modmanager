"""Tests for modmanager.bootstrap module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from modmanager.bootstrap import (
    _detect_software_dir,
    discover_user_config,
    generate_database,
)
from modmanager import bootstrap as bootstrap_module


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

    def test_discover_user_config_no_files_raises(self) -> None:
        """Pass a non-existent home_dir — should raise FileNotFoundError."""
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / "nonexistent_home"
            with self.assertRaises(FileNotFoundError):
                discover_user_config(home_dir=str(fake_home))

    def test_discover_user_config_single_level(self) -> None:
        """Single user_config.json at ~/.config/kmm/ should be found."""
        with tempfile.TemporaryDirectory() as td:
            home_dir = str(td)
            config_dir = Path(td) / ".config" / "kmm"
            config_dir.mkdir(parents=True)
            config_file = config_dir / "user_config.json"
            data = {"key1": "value1", "path_alias": []}
            config_file.write_text(json.dumps(data), encoding="utf-8")

            result = discover_user_config(home_dir=home_dir)
            self.assertEqual(result.get("key1"), "value1")
            self.assertEqual(result.get("path_alias"), [])

    def test_discover_user_config_multi_level_merge(self) -> None:
        """Three tiers merged; higher priority overrides lower."""
        with tempfile.TemporaryDirectory() as td:
            home_dir = str(td)

            # Tier 1: ~/.config/kmm/user_config.json
            tier1_dir = Path(td) / ".config" / "kmm"
            tier1_dir.mkdir(parents=True)
            (tier1_dir / "user_config.json").write_text(
                json.dumps({"shared_key": "from_tier1", "tier1_only": "yes", "override_me": "tier1"}),
                encoding="utf-8",
            )

            # Tier 2: software dir (simulate with PWD-like placement inside td)
            tier2_dir = Path(td) / "software_root"
            tier2_dir.mkdir(parents=True)

            # Tier 3: PWD (current working directory)
            tier3_dir = Path(td) / "cwd"
            tier3_dir.mkdir(parents=True)
            (tier3_dir / "user_config.json").write_text(
                json.dumps({"shared_key": "from_tier3", "tier3_only": "yes", "override_me": "tier3"}),
                encoding="utf-8",
            )

            # Simulate _detect_software_dir pointing to tier2
            with patch("modmanager.bootstrap._detect_software_dir", return_value=str(tier2_dir)):
                (tier2_dir / "user_config.json").write_text(
                    json.dumps({"tier2_only": "yes", "override_me": "tier2"}),
                    encoding="utf-8",
                )

                # Change cwd to tier3
                original_cwd = os.getcwd()
                try:
                    os.chdir(str(tier3_dir))
                    result = discover_user_config(home_dir=home_dir)
                finally:
                    os.chdir(original_cwd)

            # Tier3 overrides tier2 which overrides tier1
            self.assertEqual(result.get("shared_key"), "from_tier3")
            self.assertEqual(result.get("override_me"), "tier3")
            self.assertEqual(result.get("tier1_only"), "yes")
            self.assertEqual(result.get("tier2_only"), "yes")
            self.assertEqual(result.get("tier3_only"), "yes")

    def test_discover_user_config_invalid_json_skipped(self) -> None:
        """A tier with invalid JSON content is skipped; other tiers still work."""
        with tempfile.TemporaryDirectory() as td:
            home_dir = str(td)

            # Tier 1: valid
            tier1_dir = Path(td) / ".config" / "kmm"
            tier1_dir.mkdir(parents=True)
            (tier1_dir / "user_config.json").write_text(
                json.dumps({"key": "from_tier1"}),
                encoding="utf-8",
            )

            # Simulate software_dir for tier2 with INVALID JSON
            tier2_dir = Path(td) / "software_root"
            tier2_dir.mkdir(parents=True)

            with patch("modmanager.bootstrap._detect_software_dir", return_value=str(tier2_dir)):
                (tier2_dir / "user_config.json").write_text(
                    "this is not valid json {{{",
                    encoding="utf-8",
                )

                # Tier 3: valid (PWD override)
                tier3_dir = Path(td) / "cwd_valid"
                tier3_dir.mkdir(parents=True)
                (tier3_dir / "user_config.json").write_text(
                    json.dumps({"key": "from_tier3"}),
                    encoding="utf-8",
                )

                original_cwd = os.getcwd()
                try:
                    os.chdir(str(tier3_dir))
                    result = discover_user_config(home_dir=home_dir)
                finally:
                    os.chdir(original_cwd)

            # Tier3 should override tier1, tier2 (invalid) skipped
            self.assertEqual(result.get("key"), "from_tier3")


class TestGenerateDatabase(TestCase):
    """Tests for generate_database()."""

    def test_generate_database_invalid_mode(self) -> None:
        """Passing an invalid mode raises ValueError."""
        with self.assertRaises(ValueError):
            generate_database("invalid")

    def test_generate_database_manual_empty_paths(self) -> None:
        """Manual mode with empty paths raises ValueError."""
        with self.assertRaises(ValueError):
            generate_database("manual", paths=[])

    def test_generate_database_manual_none_paths(self) -> None:
        """Manual mode with None paths raises ValueError."""
        with self.assertRaises(ValueError):
            generate_database("manual", paths=None)

    def test_generate_database_cache_hit(self) -> None:
        """A valid cache file is loaded instead of scanning."""
        with tempfile.TemporaryDirectory() as td:
            cache_path = str(Path(td) / "cache.json")
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
            Path(cache_path).write_text(json.dumps(cache_data), encoding="utf-8")

            result = generate_database("auto", cache_path=cache_path)
            self.assertEqual(result, cache_data)

    def test_generate_database_cache_empty_file(self) -> None:
        """An empty cache file should be ignored (fall through to scan)."""
        with tempfile.TemporaryDirectory() as td:
            cache_path = str(Path(td) / "cache.json")
            # Create an empty file
            Path(cache_path).write_text("", encoding="utf-8")

            # Patch discover_with_fallback to raise so we can detect fall-through
            with patch.object(
                bootstrap_module, "discover_with_fallback",
                side_effect=ValueError("mocked: no Steam"),
            ):
                with self.assertRaises(ValueError):
                    generate_database("auto", cache_path=cache_path)

    def test_generate_database_cache_invalid_structure(self) -> None:
        """A cache file without 'steamlib' list is ignored (fall through to scan)."""
        with tempfile.TemporaryDirectory() as td:
            cache_path = str(Path(td) / "cache.json")
            Path(cache_path).write_text(
                json.dumps({"some_other_key": "value"}), encoding="utf-8"
            )

            # Patch discover_with_fallback to raise so we can detect fall-through
            with patch.object(
                bootstrap_module, "discover_with_fallback",
                side_effect=ValueError("mocked: no Steam"),
            ):
                with self.assertRaises(ValueError):
                    generate_database("auto", cache_path=cache_path)
