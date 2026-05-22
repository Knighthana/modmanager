"""Tests for apply_ops — pure apply primitive."""

import os
import tempfile
from pathlib import Path

import pytest

from hana_modmgr.apply_ops import apply_entries


class TestApplyEntries:
    """apply_entries() — file-to-file primitive tests."""

    def test_replace_copies_file(self):
        """replace action copies source to target."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src.txt"
            tgt = root / "tgt.txt"
            src.write_text("hello world")
            tgt.write_text("old")

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": str(src), "action": "replace",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            assert result["ok"]
            assert len(result["applied"]) == 1
            assert result["applied"][0]["action"] == "replace"
            assert tgt.read_text() == "hello world"

    def test_create_copies_file(self):
        """create action copies source to non-existent target."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src.txt"
            tgt = root / "sub" / "new.txt"
            src.write_text("created")

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": str(src), "action": "create",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            assert result["ok"]
            assert len(result["applied"]) == 1
            assert tgt.read_text() == "created"

    def test_delete_removes_file(self):
        """delete action removes target file."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tgt = root / "remove_me.txt"
            tgt.write_text("gone")

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": "!", "action": "delete",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            assert result["ok"]
            assert len(result["applied"]) == 1
            assert result["applied"][0]["action"] == "delete"
            assert not tgt.exists()

    def test_dry_run_does_not_modify_files(self):
        """dry_run=True returns would-apply results without writing."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src.txt"
            tgt = root / "tgt.txt"
            src.write_text("new")
            tgt.write_text("old")

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": str(src), "action": "replace",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries, dry_run=True)
            assert result["ok"]
            assert result["dry_run"]
            assert len(result["applied"]) == 1
            assert tgt.read_text() == "old"  # unchanged

    def test_vacuous_node_skipped(self):
        """entries with request=None are skipped."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tgt = root / "orphan.txt"
            tgt.write_text("skip me")

            entries = {str(root) + "/": [{
                "path": str(tgt), "request": None,
            }]}

            result = apply_entries(entries)
            assert result["ok"]
            assert len(result["applied"]) == 0
            assert len(result["skipped"]) == 1

    def test_rejects_directory_target(self):
        """Directory target raises error (file-to-file only)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src.txt"
            src.write_text("x")
            subdir = root / "sub"
            subdir.mkdir()

            entries = {str(root) + "/": [{
                "path": str(subdir) + "/",  # dir-style path
                "request": {
                    "path": str(src), "action": "replace",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            assert not result["ok"]
            assert len(result["errors"]) == 1
            assert "E_APPLY_NOT_FILE" in result["errors"][0]

    def test_rejects_directory_source(self):
        """Directory source raises IsADirectoryError."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tgt = root / "tgt.txt"
            tgt.write_text("x")
            subdir = root / "sub"
            subdir.mkdir()

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": str(subdir), "action": "replace",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            assert not result["ok"]
            assert any("E_APPLY_DIRECTORY_NOT_ALLOWED" in e for e in result["errors"])

    def test_missing_source_errors(self):
        """Missing source file produces error."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tgt = root / "tgt.txt"
            tgt.write_text("x")

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": str(root / "gone.txt"), "action": "replace",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            assert not result["ok"]
            assert any("E_APPLY_MISSING_SOURCE" in e for e in result["errors"])

    def test_return_contract_fields(self):
        """Result contains all 7 required fields."""
        with tempfile.TemporaryDirectory() as td:
            result = apply_entries({})
            for key in ("ok", "applied", "skipped", "errors", "warnings", "diagnostics", "dry_run"):
                assert key in result, f"missing field: {key}"

    def test_missing_target_creates_parents(self):
        """replace action creates parent directories when needed."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src.txt"
            src.write_text("x")
            tgt = root / "nonexistent" / "tgt.txt"
            # Parent doesn't exist — makedirs should handle it

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": str(src), "action": "replace",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            assert result["ok"], result["errors"]
            assert len(result["applied"]) == 1
            assert tgt.read_text() == "x"

    def test_delete_nonexistent_target_errors(self):
        """E_APPLY_MISSING_TARGET when deleting non-existent file."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tgt = root / "gone.txt"
            # File doesn't exist

            entries = {str(root) + "/": [{
                "path": str(tgt),
                "request": {
                    "path": "!", "action": "delete",
                    "action_order": 0, "provenance_ref": "t",
                    "sidecar_ref": "t", "mixed_id": "0:0",
                    "hashtype": "sha256", "hashvalue": "",
                }
            }]}

            result = apply_entries(entries)
            # FileNotFoundError → E_APPLY_MISSING_SOURCE or similar
            assert not result["ok"]
