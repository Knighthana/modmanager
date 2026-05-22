"""Tests for restore_ops — pure restore primitive."""

import tempfile
from pathlib import Path

import pytest

from hana_modmgr.restore_ops import restore_entries


def _make_backupinfo(source_root: str, files: dict[str, str]) -> dict:
    """Build a minimal backupinfo tree from a dict of {rel_path: content}."""
    tree = {"name": Path(source_root).name, "type": "dir", "children": []}
    for rel_path, content in files.items():
        parts = rel_path.split("/")
        current = tree
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                import hashlib
                hv = hashlib.sha256(content.encode()).hexdigest()
                current["children"].append({
                    "name": part, "type": "file",
                    "isbackuped": True, "hashtype": "sha256", "hashvalue": hv,
                })
            else:
                existing = next((c for c in current["children"]
                                 if c["name"] == part and c["type"] == "dir"), None)
                if not existing:
                    existing = {"name": part, "type": "dir", "children": []}
                    current["children"].append(existing)
                current = existing
    return tree


class TestRestoreEntries:
    """restore_entries() — file-to-file restore primitive tests."""

    def test_force_restores_file(self):
        """force=True restores file regardless of hash."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            # Simulate run_differential_backup layout:
            # content_root = parent(backup_dir) = root
            # target = root/target/file.txt → rel = "target/file.txt"
            # backup copy = backup_dir / rel
            backup_copy = backup_dir / "target" / "file.txt"
            backup_copy.parent.mkdir(parents=True)
            backup_copy.write_text("restored content")

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_text("modified")

            backupinfo = {"tree": _make_backupinfo(
                str(root),
                {"target/file.txt": "restored content"},
            )}

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace",
                            "action_order": 0, "provenance_ref": "t",
                            "sidecar_ref": "t", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}

            result = restore_entries(entries, {str(backup_dir) + "/": backupinfo}, force=True)
            assert result["ok"], result["errors"]
            assert len(result["restored"]) == 1
            assert tgt.read_text() == "restored content"

    def test_force_skips_hash_check(self):
        """force=True skips hash verification entirely."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_copy = backup_dir / "target" / "file.txt"
            backup_copy.parent.mkdir(parents=True)
            backup_copy.write_text("orig")

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_text("same as backup")

            backupinfo = {"tree": _make_backupinfo(
                str(root),
                {"target/file.txt": "orig"},
            )}

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace",
                            "action_order": 0, "provenance_ref": "t",
                            "sidecar_ref": "t", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}

            result = restore_entries(entries, {str(backup_dir) + "/": backupinfo}, force=True)
            assert result["ok"], result["errors"]
            assert len(result["restored"]) == 1

    def test_no_backupinfo_errors(self):
        """Missing backupinfo produces error."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()

            entries = {str(backup_dir) + "/": [{
                "path": str(root / "tgt.txt"),
                "request": {"path": "!", "action": "replace",
                            "action_order": 0, "provenance_ref": "t",
                            "sidecar_ref": "t", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}

            result = restore_entries(entries, {})
            assert not result["ok"]
            assert any("E_BACKUP_INFO_MISSING" in e for e in result["errors"])

    def test_missing_backup_file_skipped(self):
        """Entry without backup file is skipped."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "bk"
            backup_dir.mkdir()

            backupinfo = {"tree": {
                "name": "root", "type": "dir", "children": [
                    {"name": "gone.txt", "type": "file", "isbackuped": False,
                     "hashtype": "sha256", "hashvalue": ""}
                ]
            }}
            entries = {str(backup_dir) + "/": [{
                "path": str(root / "gone.txt"),
                "request": {"path": "!", "action": "replace",
                            "action_order": 0, "provenance_ref": "t",
                            "sidecar_ref": "t", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}

            result = restore_entries(entries, {str(backup_dir) + "/": backupinfo})
            assert result["ok"]
            assert len(result["warnings"]) >= 1
            assert any("W_RESTORE_NOT_BACKED_UP" in w for w in result["warnings"])

    def test_return_contract_fields(self):
        """Result contains all required fields."""
        result = restore_entries({}, {})
        for key in ("ok", "restored", "skipped", "deleted", "orphans", "errors", "warnings", "dry_run", "force"):
            assert key in result, f"missing field: {key}"

    def test_force_false_hash_match_skips(self):
        """force=False skips file when hash matches backup (unchanged)."""
        import hashlib

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            content = "same content"
            hv = hashlib.sha256(content.encode()).hexdigest()

            # Create backup with matching hash in backupinfo
            backup_dir = root / "backup"
            backup_copy = backup_dir / "target" / "file.txt"
            backup_copy.parent.mkdir(parents=True)
            backup_copy.write_text(content)

            tgt = root / "target" / "file.txt"
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_text(content)  # same content → hash should match

            # Tree must mirror the directory structure:
            # source_root has subdir "target" containing "file.txt"
            backupinfo = {"tree": {
                "name": "root",
                "type": "dir",
                "children": [{
                    "name": "target", "type": "dir", "children": [{
                        "name": "file.txt", "type": "file",
                        "isbackuped": True, "hashtype": "sha256", "hashvalue": hv,
                    }]
                }]
            }}

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace",
                            "action_order": 0, "provenance_ref": "t",
                            "sidecar_ref": "t", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}

            result = restore_entries(entries, {str(backup_dir) + "/": backupinfo}, force=False)
            assert result["ok"], result["errors"]
            # Should be skipped because hash matches
            assert len(result["skipped"]) == 1
            assert len(result["restored"]) == 0

    def test_creates_parent_directories(self):
        """Restore creates parent dirs when target path doesn't exist."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_copy = backup_dir / "deep" / "nested" / "file.txt"
            backup_copy.parent.mkdir(parents=True)
            backup_copy.write_text("deep content")

            # Target doesn't exist at all
            tgt = root / "deep" / "nested" / "file.txt"

            backupinfo = {"tree": _make_backupinfo(
                str(root), {"deep/nested/file.txt": "deep content"},
            )}

            entries = {str(backup_dir) + "/": [{
                "path": str(tgt),
                "request": {"path": "!", "action": "replace",
                            "action_order": 0, "provenance_ref": "t",
                            "sidecar_ref": "t", "mixed_id": "0:0",
                            "hashtype": "sha256", "hashvalue": ""},
            }]}

            result = restore_entries(entries, {str(backup_dir) + "/": backupinfo}, force=True)
            assert result["ok"], result["errors"]
            assert len(result["restored"]) == 1
            assert tgt.read_text() == "deep content"
