"""Tests for the path_resolver module.

Uses pytest with tmp_path for temporary file structures.
"""

from pathlib import Path

import pytest

from modmanager.path_resolver import resolve_directory_path, resolve_file_path


# =============================================================================
# resolve_directory_path
# =============================================================================

class TestResolveDirectoryPath:
    """Tests for resolve_directory_path()."""

    def test_input_ends_with_dirname(self, tmp_path: Path) -> None:
        """输入 /path/to/steamapps → 返回 /path/to/steamapps/"""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        result = resolve_directory_path(str(steamapps), "steamapps")
        expected = str(steamapps) + "/"
        assert result == expected

    def test_input_ends_with_dirname_trailing_slash(self, tmp_path: Path) -> None:
        """输入 /path/to/steamapps/ → 返回 /path/to/steamapps/"""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        result = resolve_directory_path(str(steamapps) + "/", "steamapps")
        expected = str(steamapps) + "/"
        assert result == expected

    def test_input_is_parent_dir(self, tmp_path: Path) -> None:
        """输入 /path/to（父目录，内含 steamapps/）→ 返回 /path/to/steamapps/"""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        parent = tmp_path  # parent of steamapps
        result = resolve_directory_path(str(parent), "steamapps")
        expected = str(steamapps) + "/"
        assert result == expected

    def test_nested_dirname(self, tmp_path: Path) -> None:
        """路径有嵌套：/path/to/steamapps/steamapps/ 存在但 /path/to/steamapps/ 不存在
        → 返回内层 steamapps/"""
        outer = tmp_path / "steamapps"
        outer.mkdir()
        nested = outer / "steamapps"
        nested.mkdir()
        # input 指向 outer/steamapps（不存在），但 outer/steamapps/steamapps/ 存在
        result = resolve_directory_path(str(nested), "steamapps")
        expected = str(nested) + "/"
        assert result == expected

    def test_all_attempts_fail(self, tmp_path: Path) -> None:
        """所有试探失败 → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            resolve_directory_path(str(tmp_path / "nonexistent"), "steamapps")

    def test_input_is_empty_string(self) -> None:
        """输入空字符串 → ValueError"""
        with pytest.raises(ValueError, match="不能为空"):
            resolve_directory_path("", "steamapps")

    def test_path_is_file_not_directory(self, tmp_path: Path) -> None:
        """输入路径是一个文件而非目录 → NotADirectoryError"""
        f = tmp_path / "somefile.txt"
        f.write_text("hello")
        with pytest.raises(NotADirectoryError):
            resolve_directory_path(str(f), "steamapps")

    def test_path_with_normalization(self, tmp_path: Path) -> None:
        """路径包含冗余分隔符或 ..，规范化后仍能正确解析"""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        # 构造一个含冗余分隔符的输入
        raw = str(tmp_path) + "//./steamapps"
        result = resolve_directory_path(raw, "steamapps")
        expected = str(steamapps) + "/"
        assert result == expected

    def test_windows_style_path_converted(self, tmp_path: Path) -> None:
        """Windows 风格路径通过 normalize_posix 转换为 POSIX 格式后仍可正确解析"""
        steamapps = tmp_path / "steamapps"
        steamapps.mkdir()
        # 模拟 WSL 下的路径 —— 这里我们直接用 POSIX 路径，但使用反斜杠测试
        posix_str = str(steamapps)
        # 将 / 替换为 \\ 模拟 Windows 风格输入
        win_style = posix_str.replace("/", "\\")
        # 如果路径中不含 drive letter，normalize_posix 仍会转换分隔符
        result = resolve_directory_path(win_style, "steamapps")
        expected = str(steamapps) + "/"
        assert result == expected


# =============================================================================
# resolve_file_path
# =============================================================================

class TestResolveFilePath:
    """Tests for resolve_file_path()."""

    def test_input_is_file(self, tmp_path: Path) -> None:
        """输入 /path/to/file.json 且是文件 → 返回该路径"""
        f = tmp_path / "file.json"
        f.write_text("{}")
        result = resolve_file_path(str(f), "file.json")
        expected = str(f)
        assert result == expected

    def test_input_is_directory_with_trailing_slash(self, tmp_path: Path) -> None:
        """输入 /path/to/dir/，目录下存在 file.json → 返回 /path/to/dir/file.json"""
        target_dir = tmp_path / "somedir"
        target_dir.mkdir()
        f = target_dir / "file.json"
        f.write_text("{}")
        result = resolve_file_path(str(target_dir) + "/", "file.json")
        expected = str(f)
        assert result == expected

    def test_input_is_directory_no_trailing_slash(self, tmp_path: Path) -> None:
        """输入 /path/to/dir，是目录，目录下存在 file.json → 返回 /path/to/dir/file.json"""
        target_dir = tmp_path / "somedir"
        target_dir.mkdir()
        f = target_dir / "file.json"
        f.write_text("{}")
        result = resolve_file_path(str(target_dir), "file.json")
        expected = str(f)
        assert result == expected

    def test_input_nonexistent(self, tmp_path: Path) -> None:
        """输入 /path/to/nonexistent → FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            resolve_file_path(str(tmp_path / "nonexistent"), "file.json")

    def test_directory_without_file(self, tmp_path: Path) -> None:
        """输入 /path/to/dir/，目录下没有 file.json → FileNotFoundError"""
        target_dir = tmp_path / "somedir"
        target_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            resolve_file_path(str(target_dir) + "/", "file.json")

    def test_directory_without_file_no_slash(self, tmp_path: Path) -> None:
        """输入 /path/to/dir（目录），目录下没有 file.json → FileNotFoundError"""
        target_dir = tmp_path / "somedir"
        target_dir.mkdir()
        with pytest.raises(FileNotFoundError):
            resolve_file_path(str(target_dir), "file.json")

    def test_input_is_empty_string(self) -> None:
        """输入空字符串 → ValueError"""
        with pytest.raises(ValueError, match="不能为空"):
            resolve_file_path("", "database.json")

    def test_different_filename(self, tmp_path: Path) -> None:
        """使用不同的文件名（如 database.json vs user_config.json）"""
        d = tmp_path / "cfgdir"
        d.mkdir()
        db = d / "database.json"
        db.write_text("{}")
        cfg = d / "user_config.json"
        cfg.write_text("{}")

        # 用目录输入，分别找两个文件
        result_db = resolve_file_path(str(d), "database.json")
        assert result_db == str(db)

        result_cfg = resolve_file_path(str(d), "user_config.json")
        assert result_cfg == str(cfg)

        # 不存在
        with pytest.raises(FileNotFoundError):
            resolve_file_path(str(d), "missing.json")

    def test_path_with_normalization(self, tmp_path: Path) -> None:
        """规范化后的路径（.. 解析）"""
        target_dir = tmp_path / "realdir"
        target_dir.mkdir()
        f = target_dir / "data.json"
        f.write_text("{}")
        # 输入中包含 .. 和冗余分隔符
        raw = str(tmp_path / "linkdir" / ".." / "realdir") + "//"
        result = resolve_file_path(raw, "data.json")
        expected = str(f)
        assert result == expected
