"""Tests for restore flow per DESIGN_RESTORE_OPS.md."""

import hashlib
import tempfile
from pathlib import Path

import pytest

from modmanager.restore_ops import restore_entries


def _make_tree_with_file(
    root_name: str,
    rel_path: str,
    *,
    isbackuped: bool = True,
    hashtype: str = "sha256",
    hashvalue: str = "",
) -> dict:
    """Build a minimal tree containing a single file node at rel_path."""
    parts = rel_path.split("/")
    # Build from leaves up
    node: dict = {
        "name": parts[-1],
        "type": "file",
        "isbackuped": isbackuped,
        "hashtype": hashtype,
        "hashvalue": hashvalue,
    }
    for part in reversed(parts[:-1]):
        node = {"name": part, "type": "dir", "children": [node]}
    return {"name": root_name, "type": "dir", "children": node["children"] if "children" in node else [node]}


class TestRestorePerDesign:
    """Per DESIGN_RESTORE_OPS.md §四 — restore execution flow."""

    def test_node_not_in_tree_deletes_source_file(self):
        """§四-3: tree 上无对应结点 → 直接删除源目录中的对应文件."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True)
            tgt.write_text("should be deleted")

            backup_dir = root / "backup"
            backup_dir.mkdir()
            tree = _make_tree_with_file("target", "other.txt")  # tree has "other.txt", not "file.txt"

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}
            result = restore_entries(entries, {str(backup_dir) + "/": {"tree": tree}}, force=True)
            assert result["ok"], result["errors"]
            assert len(result["restored"]) == 0  # not restored — deleted
            assert not tgt.exists(), f"file should be deleted: {tgt}"

    def test_isbackuped_false_skips_with_warning(self):
        """§四-4: isbackuped=false → skip 并记录详细警告."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            backup_file = backup_dir / "target" / "file.txt"
            backup_file.parent.mkdir(parents=True)
            backup_file.write_text("backup content")

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_text("current content")

            tree = _make_tree_with_file("target", "target/file.txt", isbackuped=False)

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}
            result = restore_entries(entries, {str(backup_dir) + "/": {"tree": tree}}, force=True)
            assert result["ok"]
            assert len(result["restored"]) == 0
            assert len(result["warnings"]) >= 1

    def test_invalid_hash_skips_with_warning(self):
        """§四-4: hashtype='invalid' 或 hashvalue='0' → skip 并记录警告."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            backup_file = backup_dir / "target" / "file.txt"
            backup_file.parent.mkdir(parents=True)
            backup_file.write_text("backup content")

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_text("current content")

            tree = _make_tree_with_file("target", "target/file.txt",
                                        isbackuped=True,
                                        hashtype="invalid",
                                        hashvalue="0")

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}
            result = restore_entries(entries, {str(backup_dir) + "/": {"tree": tree}}, force=True)
            assert result["ok"]
            assert len(result["restored"]) == 0
            assert len(result["warnings"]) >= 1

    def test_hash_match_skips(self):
        """§四-5: hash 相同时 skip."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            content = b"same content"
            hv = hashlib.sha256(content).hexdigest()

            backup_dir = root / "backup"
            backup_dir.mkdir()
            backup_file = backup_dir / "target" / "file.txt"
            backup_file.parent.mkdir(parents=True)
            backup_file.write_bytes(content)

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_bytes(content)

            tree = _make_tree_with_file("target", "target/file.txt",
                                        isbackuped=True,
                                        hashtype="sha256",
                                        hashvalue=hv)

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}
            result = restore_entries(entries, {str(backup_dir) + "/": {"tree": tree}}, force=False)
            assert result["ok"], result["errors"]
            assert len(result["skipped"]) == 1
            assert len(result["restored"]) == 0

    def test_hash_mismatch_restores(self):
        """§四-5: hash 不相同 → 加入批量操作列表，执行恢复."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_content = b"backup version"
            current_content = b"current version"
            hv = hashlib.sha256(backup_content).hexdigest()

            backup_dir = root / "backup"
            backup_dir.mkdir()
            backup_file = backup_dir / "target" / "file.txt"
            backup_file.parent.mkdir(parents=True)
            backup_file.write_bytes(backup_content)

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_bytes(current_content)  # different content

            tree = _make_tree_with_file("target", "target/file.txt",
                                        isbackuped=True,
                                        hashtype="sha256",
                                        hashvalue=hv)

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}
            result = restore_entries(entries, {str(backup_dir) + "/": {"tree": tree}}, force=False)
            assert result["ok"], result["errors"]
            assert len(result["restored"]) == 1
            assert tgt.read_bytes() == backup_content

    def test_dry_run_does_not_modify_files(self):
        """dry_run=true 时不修改文件，但返回报告."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_content = b"backup version"
            current_content = b"current version"
            hv = hashlib.sha256(backup_content).hexdigest()

            backup_dir = root / "backup"
            backup_dir.mkdir()
            backup_file = backup_dir / "target" / "file.txt"
            backup_file.parent.mkdir(parents=True)
            backup_file.write_bytes(backup_content)

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_bytes(current_content)

            tree = _make_tree_with_file("target", "target/file.txt",
                                        isbackuped=True,
                                        hashtype="sha256",
                                        hashvalue=hv)

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}
            result = restore_entries(entries, {str(backup_dir) + "/": {"tree": tree}},
                                     force=False, dry_run=True)
            assert result["ok"], result["errors"]
            assert result["dry_run"] is True
            # File should NOT be modified
            assert tgt.read_bytes() == current_content
            # But report should show what WOULD happen
            assert len(result["restored"]) == 1
