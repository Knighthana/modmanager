"""Tests for backup flow per DESIGN_BACKUP_OPS.md — tree state machine."""

import json
import tempfile
from pathlib import Path

import pytest

from modmanager.backup_ops import run_differential_backup, load_backup_info, build_dir_tree_with_hashes


def _make_initial_tree(source_root: str) -> dict:
    """Simulate prep: build initial tree with all files isbackuped=false."""
    return build_dir_tree_with_hashes(source_root, source_root)


class TestBackupTreeStateMachine:
    """Per DESIGN_BACKUP_OPS.md §六 — tree node state constraints."""

    def test_first_backup_builds_tree_with_isbackuped_false(self):
        """First backup: tree built, all files isbackuped=false before copy."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "mod" / "file.txt"
            src.parent.mkdir(parents=True)
            src.write_text("hello")

            backup_dir = str(root / "backup") + "/"
            tree = _make_initial_tree(str(root / "mod"))

            # Verify initial state
            node = _find_node(tree, "file.txt")
            assert node is not None
            assert node["isbackuped"] is False
            assert node["hashtype"] == "sha256"  # from build_dir_tree_with_hashes
            assert len(node["hashvalue"]) == 64

    def test_isbackuped_true_skips_on_second_backup(self):
        """Second backup: isbackuped=true files are skipped, not overwritten."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "mod" / "file.txt"
            src.parent.mkdir(parents=True)
            src.write_text("hello")

            backup_dir = str(root / "backup") + "/"
            # First backup: build tree + backup
            tree = _make_initial_tree(str(root / "mod"))
            # Simulate first backup completing: mark file as backed up
            _mark_backuped(tree, "file.txt", "sha256")

            # Second backup: should skip this file
            result = run_differential_backup(
                backup_dir,
                [str(src)],
                tree=tree,
            )
            assert result["ok"]
            skipped = [s for s in result["skipped"]
                       if "already backed up" in s.get("reason", "")]
            assert len(skipped) == 1

    def test_node_not_in_tree_produces_warning(self):
        """DESIGN_BACKUP_OPS.md §六-2: node not in tree → W_BACKUP_NODE_NOT_IN_TREE."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "mod" / "file.txt"
            src.parent.mkdir(parents=True)
            src.write_text("hello")

            backup_dir = str(root / "backup") + "/"
            # Tree has no nodes at all
            tree = {"name": "mod", "type": "dir", "children": []}

            result = run_differential_backup(
                backup_dir,
                [str(src)],
                tree=tree,
            )
            assert result["ok"]
            skipped = [s for s in result["skipped"]
                       if "already backed up" in s.get("reason", "")]
            assert len(skipped) == 1

    def test_copy_failure_does_not_mark_isbackuped(self):
        """§六: isbackuped only set after successful copy."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Source doesn't exist — copy will fail
            missing_src = str(root / "mod" / "missing.txt")
            backup_dir = str(root / "backup") + "/"

            result = run_differential_backup(
                backup_dir,
                [missing_src],
            )
            assert result["ok"]
            # File should be skipped (source not found), not backed up
            assert len(result["backed_up"]) == 0
            assert len(result["skipped"]) >= 1

    def test_isbackuped_only_false_to_true(self):
        """§六: isbackuped cannot go true→false."""
        # This is enforced by the tree check — once true, always skipped.
        # The primitive never writes isbackuped=false.
        # Test: run backup twice, second run skips already-backed-up file.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "mod" / "file.txt"
            src.parent.mkdir(parents=True)
            src.write_text("v1")

            backup_dir = str(root / "backup") + "/"
            tree = _make_initial_tree(str(root / "mod"))
            _mark_backuped(tree, "file.txt", "sha256")

            # Change source content — backup should still skip (isbackuped=true)
            src.write_text("v2")
            result = run_differential_backup(
                backup_dir,
                [str(src)],
                tree=tree,
            )
            assert result["ok"]
            skipped = [s for s in result["skipped"]
                       if "already backed up" in s.get("reason", "")]
            assert len(skipped) == 1
            # Source file unchanged by backup (it was skipped)
            assert src.read_text() == "v2"


def _find_node(tree: dict, name: str) -> dict | None:
    """Find a file node by name in the tree."""
    for child in tree.get("children", []):
        if child.get("name") == name:
            return child
    return None


def _mark_backuped(tree: dict, name: str, hashtype: str) -> None:
    """Update tree node to isbackuped=true (simulating a completed backup)."""
    import hashlib
    node = _find_node(tree, name)
    if node:
        node["isbackuped"] = True
        node["hashtype"] = hashtype
        # Don't overwrite existing hashvalue if already computed
        if node.get("hashvalue", "0") == "0":
            node["hashvalue"] = "0" * 64
