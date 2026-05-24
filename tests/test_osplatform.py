"""Tests for modmgr.osplatform — platform detection and default values.

Per DESIGN_OSPLATFORM.md §七:
  - ``platform()`` returns one of the four known values
  - ``defaultvalue`` get methods return correct platform-appropriate paths
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from modmgr.osplatform import defaultvalue, platform


class TestPlatform(TestCase):
    """Tests for osplatform.platform()."""

    def test_platform_returns_string(self) -> None:
        """platform() always returns a string."""
        result = platform()
        self.assertIsInstance(result, str)

    def test_platform_is_known_value(self) -> None:
        """platform() returns one of the four known values."""
        result = platform()
        self.assertIn(result, ("linux", "windows", "darwin", "wsl"))

    def test_platform_windows(self) -> None:
        """When sys.platform == 'win32', platform() returns 'windows'."""
        with patch("modmgr.osplatform.sys.platform", "win32"):
            self.assertEqual(platform(), "windows")

    def test_platform_darwin(self) -> None:
        """When sys.platform == 'darwin', platform() returns 'darwin'."""
        with patch("modmgr.osplatform.sys.platform", "darwin"):
            self.assertEqual(platform(), "darwin")

    def test_platform_linux(self) -> None:
        """On Linux (no WSL), platform() returns 'linux'."""
        with patch("modmgr.osplatform.sys.platform", "linux"):
            with patch("builtins.open", side_effect=FileNotFoundError()):
                self.assertEqual(platform(), "linux")

    def test_platform_wsl(self) -> None:
        """On WSL (/proc/version contains 'microsoft'), platform() returns 'wsl'."""
        with patch("modmgr.osplatform.sys.platform", "linux"):
            with patch("builtins.open") as mock_open:
                mock_file = mock_open.return_value.__enter__.return_value
                mock_file.read.return_value = (
                    "Linux version 6.6.114.1-microsoft-standard-WSL2 "
                    "(root@507f3e43091d) (gcc (GCC) 13.2.0, GNU ld (GNU Binutils) 2.41) "
                    "#1 SMP PREEMPT_DYNAMIC Mon Dec  1 20:46:23 UTC 2025"
                )
                self.assertEqual(platform(), "wsl")


class TestDefaultValues(TestCase):
    """Tests for osplatform.defaultvalue methods."""

    def test_userconfig_index_get_has_type_path(self) -> None:
        """userconfig_index_get() returns a dict with 'type': 'path'."""
        result = defaultvalue.userconfig_index_get()
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("type"), "path")

    def test_userconfig_index_get_has_string(self) -> None:
        """userconfig_index_get() returns a dict with a non-empty 'string' key."""
        result = defaultvalue.userconfig_index_get()
        self.assertIsInstance(result.get("string"), str)
        self.assertTrue(len(result["string"]) > 0)

    def test_workspace_dir_get_ends_with_workspace(self) -> None:
        """workspace_dir_get() returns a path ending with 'workspace'."""
        result = defaultvalue.workspace_dir_get()
        self.assertTrue(result.endswith("workspace") or result.endswith("workspace/"))

    def test_database_path_get_ends_with_database_json(self) -> None:
        """database_path_get() returns a path ending with 'database.json'."""
        result = defaultvalue.database_path_get()
        self.assertTrue(result.endswith("database.json"))

    def test_working_pathstyle_get_returns_string(self) -> None:
        """working_pathstyle_get() returns 'linux' or 'windows'."""
        result = defaultvalue.working_pathstyle_get()
        self.assertIn(result, ("linux", "windows"))

    def test_defaults_use_forward_slashes(self) -> None:
        """All default paths use forward slashes (POSIX style)."""
        for getter in (
            defaultvalue.workspace_dir_get,
            defaultvalue.database_path_get,
        ):
            result = getter()
            self.assertNotIn("\\", result, f"{getter.__name__} contains backslashes")

    def test_linux_defaults(self) -> None:
        """On Linux, defaults point to XDG-style paths."""
        with patch("modmgr.osplatform.sys.platform", "linux"):
            with patch("builtins.open", side_effect=FileNotFoundError()):
                home = os.environ.get("HOME", str(Path.home()))
                ws = defaultvalue.workspace_dir_get()
                db = defaultvalue.database_path_get()
                self.assertTrue(ws.startswith(home))
                self.assertTrue(db.startswith(home))

    def test_windows_defaults(self) -> None:
        """On Windows, defaults use APPDATA/LOCALAPPDATA."""
        with patch("modmgr.osplatform.sys.platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": "C:\\Users\\test\\AppData\\Roaming", "LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}):
                uc = defaultvalue.userconfig_index_get()
                self.assertIn("AppData/Roaming/kmm/user_config.json", uc["string"])
                ws = defaultvalue.workspace_dir_get()
                self.assertIn("AppData/Local/kmm/workspace", ws)
                db = defaultvalue.database_path_get()
                self.assertIn("AppData/Local/kmm/database/database.json", db)

    def test_darwin_defaults(self) -> None:
        """On macOS, defaults use Library paths."""
        with patch("modmgr.osplatform.sys.platform", "darwin"):
            home = "/Users/testuser"
            with patch.dict(os.environ, {"HOME": home}):
                uc = defaultvalue.userconfig_index_get()
                self.assertIn("Library/Preferences/kmm/user_config.json", uc["string"])
                ws = defaultvalue.workspace_dir_get()
                self.assertIn("Library/Caches/kmm/workspace", ws)
                db = defaultvalue.database_path_get()
                self.assertIn("Library/Application Support/kmm/database.json", db)

    def test_wsl_defaults_match_linux(self) -> None:
        """On WSL, defaults are the same as Linux."""
        with patch("modmgr.osplatform.sys.platform", "linux"):
            with patch("builtins.open") as mock_open:
                mock_file = mock_open.return_value.__enter__.return_value
                mock_file.read.return_value = "Linux version 6.6-microsoft-standard-WSL2"
                ws = defaultvalue.workspace_dir_get()
                db = defaultvalue.database_path_get()
                self.assertTrue(ws.endswith(".cache/kmm/workspace") or ws.endswith(".cache/kmm/workspace/") or ws.endswith(".cache\\kmm\\workspace"))
                self.assertTrue(db.endswith(".local/share/kmm/database.json"))
