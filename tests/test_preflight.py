"""Tests for preflight module — per DESIGN_PREFLIGHT_APPLY.md §XI."""

import json
import tempfile
from pathlib import Path

import pytest

from modmanager.orchestrator.preflight import (
    run_apply_preflight,
    run_restore_preflight,
)
from modmanager.orchestrator.resolver import CleanContext


def _make_context() -> CleanContext:
    return CleanContext(
        final_mapping=[],
        database={"game": [], "mod": [], "steamlib": []},
        user_config={"baksuffix": "kmmbackup"},
    )


class TestApplyPreflight:
    """run_apply_preflight() — per DESIGN_PREFLIGHT_APPLY.md §XI."""

    def test_manifest_has_required_fields(self):
        """manifest contains ok, backup_dirs, errors, warnings, timestamp."""
        manifest = run_apply_preflight({}, _make_context())
        for key in ("ok", "backup_dirs", "errors", "warnings", "timestamp"):
            assert key in manifest, f"missing manifest field: {key}"

    def test_backup_dirs_entry_structure(self):
        """Each backup_dirs entry has path, gate_pass, gate_errors, applicable_entries."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            # Create valid backupinfo so gate passes
            info = {
                "schema_namespace": "KMM_BackupInfo",
                "snapshot_time": "2026-01-01T00:00:00Z",
                "last_modified_time": "2026-01-01T00:00:00Z",
                "schema_version": "knighthana@0.1.0",
                "tree": {"name": "root", "type": "dir", "children": []},
            }
            (backup_dir / "backupinfo.json").write_text(json.dumps(info))

            manifest = run_apply_preflight(
                {str(backup_dir) + "/": ["/some/file.txt"]},
                _make_context(),
            )
            assert manifest["ok"]
            entry = manifest["backup_dirs"][0]
            for key in ("path", "gate_pass", "gate_errors", "applicable_entries"):
                assert key in entry, f"missing entry field: {key}"
            assert entry["gate_pass"] is True

    def test_missing_backup_dir_fails_gate(self):
        """E_BACKUP_DIR_MISSING when backup_dir doesn't exist."""
        manifest = run_apply_preflight(
            {"/nonexistent/path/": ["/some/file.txt"]},
            _make_context(),
        )
        assert manifest["ok"] is False
        entry = manifest["backup_dirs"][0]
        assert entry["gate_pass"] is False
        assert any("E_BACKUP_DIR_MISSING" in e for e in entry["gate_errors"])

    def test_missing_backupinfo_fails_gate(self):
        """E_BACKUP_INFO_MISSING when backupinfo.json absent."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            # No backupinfo.json

            manifest = run_apply_preflight(
                {str(backup_dir) + "/": ["/some/file.txt"]},
                _make_context(),
            )
            assert manifest["ok"] is False
            entry = manifest["backup_dirs"][0]
            assert entry["gate_pass"] is False
            assert any("E_BACKUP_INFO_MISSING" in e for e in entry["gate_errors"])

    def test_missing_tree_fails_gate(self):
        """E_BACKUP_TREE_MISSING when backupinfo has no tree."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            info = {"schema_namespace": "KMM_BackupInfo", "schema_version": "1"}
            (backup_dir / "backupinfo.json").write_text(json.dumps(info))

            manifest = run_apply_preflight(
                {str(backup_dir) + "/": ["/some/file.txt"]},
                _make_context(),
            )
            assert manifest["ok"] is False
            entry = manifest["backup_dirs"][0]
            assert entry["gate_pass"] is False

    def test_preflight_does_not_modify_disk(self):
        """preflight does NOT write files or modify disk state."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            info = {
                "schema_namespace": "KMM_BackupInfo",
                "snapshot_time": "2026-01-01T00:00:00Z",
                "last_modified_time": "2026-01-01T00:00:00Z",
                "schema_version": "knighthana@0.1.0",
                "tree": {"name": "root", "type": "dir", "children": []},
            }
            (backup_dir / "backupinfo.json").write_text(json.dumps(info))

            before_files = set(str(p) for p in root.rglob("*"))
            run_apply_preflight(
                {str(backup_dir) + "/": ["/some/file.txt"]},
                _make_context(),
            )
            after_files = set(str(p) for p in root.rglob("*"))
            assert before_files == after_files, "preflight modified disk!"

    def test_empty_backup_dirs_returns_ok(self):
        """Empty backup_dirs trivially passes preflight."""
        manifest = run_apply_preflight({}, _make_context())
        assert manifest["ok"] is True
        assert manifest["backup_dirs"] == []


class TestRestorePreflight:
    """run_restore_preflight() — per DESIGN_PREFLIGHT_APPLY.md."""

    def test_manifest_has_required_fields(self):
        """manifest contains ok, backup_dirs, errors, warnings, timestamp."""
        manifest = run_restore_preflight({}, _make_context())
        for key in ("ok", "backup_dirs", "errors", "warnings", "timestamp"):
            assert key in manifest, f"missing manifest field: {key}"

    def test_existing_backup_dir_passes(self):
        """backup_dir that exists on disk passes preflight."""
        with tempfile.TemporaryDirectory() as td:
            backup_dir = Path(td) / "backup"
            backup_dir.mkdir()

            manifest = run_restore_preflight(
                {str(backup_dir) + "/": ["/some/file.txt"]},
                _make_context(),
            )
            assert manifest["ok"]
            entry = manifest["backup_dirs"][0]
            assert entry["gate_pass"] is True
            assert entry["gate_errors"] == []

    def test_missing_backup_dir_fails(self):
        """E_BACKUP_DIR_MISSING when backup_dir doesn't exist."""
        manifest = run_restore_preflight(
            {"/nonexistent/": ["/some/file.txt"]},
            _make_context(),
        )
        assert manifest["ok"] is False
        entry = manifest["backup_dirs"][0]
        assert entry["gate_pass"] is False
        assert any("E_BACKUP_DIR_MISSING" in e for e in manifest["errors"])

    def test_preflight_does_not_modify_disk(self):
        """preflight does NOT modify disk state."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backup"
            backup_dir.mkdir()

            before_files = set(str(p) for p in root.rglob("*"))
            run_restore_preflight(
                {str(backup_dir) + "/": ["/some/file.txt"]},
                _make_context(),
            )
            after_files = set(str(p) for p in root.rglob("*"))
            assert before_files == after_files, "preflight modified disk!"
