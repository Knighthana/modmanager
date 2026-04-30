"""Tests for the pathstyle module."""
import unittest

from modmanager.pathstyle import PathStyle, convert_path, detect_pathstyle, normalize


class TestDetectPathstyle(unittest.TestCase):
    def test_linux_absolute(self):
        self.assertEqual(detect_pathstyle("/mnt/d/Games"), PathStyle.LINUX)

    def test_linux_relative(self):
        self.assertEqual(detect_pathstyle("some/relative/path"), PathStyle.LINUX)

    def test_windows_backslash(self):
        self.assertEqual(detect_pathstyle(r"C:\Users\foo"), PathStyle.WINDOWS)

    def test_windows_forward_slash(self):
        self.assertEqual(detect_pathstyle("D:/Games/steamapps"), PathStyle.WINDOWS)

    def test_windows_lowercase_drive(self):
        self.assertEqual(detect_pathstyle(r"c:\foo\bar"), PathStyle.WINDOWS)

    def test_windows_unc(self):
        self.assertEqual(detect_pathstyle(r"\\server\share"), PathStyle.WINDOWS)


class TestConvertPath(unittest.TestCase):
    # ── Linux → Windows ──────────────────────────────────────────────────────
    def test_linux_to_windows_basic(self):
        self.assertEqual(convert_path("/mnt/d/Games/foo", PathStyle.WINDOWS), r"D:\Games\foo")

    def test_linux_to_windows_c_drive(self):
        self.assertEqual(convert_path("/mnt/c/Users/bar", PathStyle.WINDOWS), r"C:\Users\bar")

    def test_linux_to_windows_drive_only(self):
        self.assertEqual(convert_path("/mnt/d", PathStyle.WINDOWS), "D:\\")

    # ── Windows → Linux ──────────────────────────────────────────────────────
    def test_windows_backslash_to_linux(self):
        self.assertEqual(convert_path(r"D:\Games\steamapps\mod", PathStyle.LINUX), "/mnt/d/Games/steamapps/mod")

    def test_windows_forward_slash_to_linux(self):
        self.assertEqual(convert_path("C:/Users/foo/bar", PathStyle.LINUX), "/mnt/c/Users/foo/bar")

    def test_windows_lowercase_drive_to_linux(self):
        self.assertEqual(convert_path(r"c:\foo", PathStyle.LINUX), "/mnt/c/foo")

    # ── same style: just normalise separators ────────────────────────────────
    def test_linux_no_change(self):
        self.assertEqual(convert_path("/mnt/d/foo/bar", PathStyle.LINUX), "/mnt/d/foo/bar")

    def test_windows_normalise_to_backslash(self):
        self.assertEqual(convert_path("D:/Games/foo", PathStyle.WINDOWS), r"D:\Games\foo")


class TestNormalize(unittest.TestCase):
    def test_normalize_linux(self):
        # Windows path requested as Linux
        self.assertEqual(normalize(r"C:\foo\bar", PathStyle.LINUX), "/mnt/c/foo/bar")

    def test_normalize_windows(self):
        # Linux path requested as Windows
        self.assertEqual(normalize("/mnt/d/Games", PathStyle.WINDOWS), r"D:\Games")

    def test_normalize_already_target(self):
        # No conversion needed
        self.assertEqual(normalize("/mnt/c/hello", PathStyle.LINUX), "/mnt/c/hello")


if __name__ == "__main__":
    unittest.main()
