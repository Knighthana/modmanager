"""Tests for normalize_path() — per DESIGN_PATH_CASE.md §六."""

from __future__ import annotations

import sys
from unittest import TestCase
from unittest.mock import patch

from modmgr.paths import normalize_path, normalize_posix


class TestNormalizePath(TestCase):
    """normalize_path() — L1 style + L2 case normalization."""

    # ── L1: style normalization (same as normalize_posix) ──────────

    def test_style_normalization_backslash(self) -> None:
        """Backslashes converted to forward slashes."""
        result = normalize_path(r"C:\Games\Steam\steamapps\workshop\content\270150", source_platform="windows")
        self.assertNotIn("\\", result)

    def test_style_collapses_redundant_slashes(self) -> None:
        """Multiple consecutive slashes collapsed."""
        result = normalize_path("/a//b///c", source_platform="linux")
        self.assertEqual(result, "/a/b/c")

    # ── L2: Windows / WSL → lowercase ─────────────────────────────

    def test_windows_lowercase(self) -> None:
        """Windows platform: entire path lowercased."""
        result = normalize_path(
            r"D:\Games\Steam\steamapps\Workshop\Content\270150",
            source_platform="windows",
        )
        self.assertEqual(result, "/mnt/d/games/steam/steamapps/workshop/content/270150")

    def test_wsl_lowercase(self) -> None:
        """WSL mount: entire path lowercased."""
        result = normalize_path(
            "/mnt/c/Program Files (x86)/Steam/steamapps",
            source_platform="wsl",
        )
        self.assertEqual(result, "/mnt/c/program files (x86)/steam/steamapps")

    def test_wsl_auto_detect_lowercase(self) -> None:
        """WSL paths auto-detected and lowercased."""
        from modmgr.osplatform import platform as _os_platform
        current = _os_platform()
        if current not in ("wsl",):
            # On native Linux / darwin the auto-detection uses osplatform.platform()
            # which returns "linux"/"darwin" — not "wsl".  Simulate WSL.
            with patch("modmgr.osplatform.platform", return_value="wsl"):
                result = normalize_path("/mnt/d/Games/SteamApps")
                self.assertEqual(result, "/mnt/d/games/steamapps")
        else:
            result = normalize_path("/mnt/d/Games/SteamApps")
            self.assertEqual(result, "/mnt/d/games/steamapps")

    # ── L2: Linux / macOS → preserve case ─────────────────────────

    def test_linux_preserves_case(self) -> None:
        """Linux platform: case preserved."""
        result = normalize_path(
            "/home/User/.steam/Steam/steamapps",
            source_platform="linux",
        )
        self.assertEqual(result, "/home/User/.steam/Steam/steamapps")

    def test_darwin_preserves_case(self) -> None:
        """macOS platform: case preserved."""
        result = normalize_path(
            "/Users/Name/Library/Preferences/kmm/user_config.json",
            source_platform="darwin",
        )
        self.assertEqual(result, "/Users/Name/Library/Preferences/kmm/user_config.json")

    def test_linux_default_preserves_case(self) -> None:
        """Without source_platform on Linux, case preserved."""
        if sys.platform == "win32":
            self.skipTest("Default platform on Windows differs")

        result = normalize_path("/home/User/MyRule.kmmrule.json")
        # Should NOT be lowercased (Linux default)
        self.assertIn("User", result)
        self.assertIn("MyRule", result)

    # ── Idempotence ───────────────────────────────────────────────

    def test_idempotent(self) -> None:
        """normalize_path() is idempotent."""
        path = "/mnt/d/Games/SteamApps/common"
        first = normalize_path(path, source_platform="wsl")
        second = normalize_path(first, source_platform="wsl")
        self.assertEqual(first, second)

    # ── Auto-detection ────────────────────────────────────────────

    def test_auto_detect_windows(self) -> None:
        """On Windows runtime, source_platform auto-detected as 'windows'."""
        from modmgr.osplatform import platform as _os_platform
        if _os_platform() != "windows":
            # Simulate Windows runtime
            with patch("modmgr.osplatform.platform", return_value="windows"):
                with patch("modmgr.paths.detect_platform", return_value="windows"):
                    result = normalize_path(r"D:\Games\SteamApps")
                    self.assertEqual(result, normalize_path(r"D:\Games\SteamApps", source_platform="windows"))
        else:
            result = normalize_path(r"D:\Games\SteamApps")
            self.assertEqual(result, normalize_path(r"D:\Games\SteamApps", source_platform="windows"))


class TestNormalizePosixRegression(TestCase):
    """Ensure normalize_posix is unchanged."""

    def test_normalize_posix_unchanged(self) -> None:
        """normalize_posix still converts backslashes and collapses slashes."""
        result = normalize_posix(r"C:\foo\\bar")
        self.assertNotIn("\\", result)
        self.assertNotIn("//", result)
