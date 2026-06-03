"""Tests for gate boundary — per repo_test/gate_boundary.md.

T-GT-01 ~ T-GT-08: verify check_backup_gate migrated out of primitive.
"""

import importlib
import json
import tempfile
from pathlib import Path
from unittest import TestCase

import pytest

from modmgr.orchestrator.fileops.planner.planner import check_backup_gate


class TestGateBoundary:
    """Black-box boundary tests — check_backup_gate no longer in backup_ops."""

    # ── 2.1 原语边界 ────────────────────────────────────────────────

    def test_tgt01_import_from_backup_ops_raises_importerror(self):
        """T-GT-01: from modmgr.backup_ops import check_backup_gate → ImportError"""
        with pytest.raises(ImportError):
            from modmgr.backup_ops import check_backup_gate  # type: ignore[import-unused]
            _ = check_backup_gate

    def test_tgt02_all_does_not_contain_gate(self):
        """T-GT-02: backup_ops.__all__ 不含 "check_backup_gate"."""
        import modmgr.backup_ops as backup_ops

        assert "check_backup_gate" not in backup_ops.__all__

    def test_tgt03_no_check_gate_function_in_backup_ops(self):
        """T-GT-03: backup_ops.py 中不存在任何名为 check_*_gate 的函数。"""
        import modmgr.backup_ops as backup_ops

        names = dir(backup_ops)
        gate_funcs = [n for n in names if n.startswith("check_") and n.endswith("_gate")]
        assert gate_funcs == [], f"Found unexpected gate functions in backup_ops: {gate_funcs}"

    def test_tgt04_apply_ops_no_gate_import(self):
        """T-GT-04: apply_ops.py 不 import backup_ops 的 gate 函数。"""
        import inspect
        import modmgr.apply_ops as apply_ops

        source = inspect.getsource(apply_ops)
        # Check no reference to check_backup_gate
        assert "check_backup_gate" not in source, "apply_ops references check_backup_gate"

    def test_tgt05_preflight_no_backup_ops_import(self):
        """T-GT-05: preflight.py 不 import backup_ops。"""
        import inspect
        import modmgr.orchestrator.fileops.planner.preflight as preflight

        source = inspect.getsource(preflight)
        assert "backup_ops" not in source, "preflight still imports from backup_ops"

    # ── 2.2 Planner 新职责 ─────────────────────────────────────────

    def test_tgt06_importable_from_planner(self):
        """T-GT-06: check_backup_gate 在 planner_fileops.py 中可 import。"""
        from modmgr.orchestrator.fileops.planner.planner import check_backup_gate as cbg

        assert callable(cbg)
        assert cbg.__name__ == "check_backup_gate"

    def test_tgt07_function_identity_before_and_after(self):
        """T-GT-07: 功能与迁移前一致（同一输入 → 同一结果）。"""
        # Case 1: missing backup_dir
        errors = check_backup_gate("/nonexistent/backup_dir/")
        assert "E_BACKUP_DIR_MISSING" in str(errors)

        # Case 2: valid backup_dir with complete backupinfo
        with tempfile.TemporaryDirectory() as td:
            backup_dir = str(Path(td) / "backup") + "/"
            Path(backup_dir).mkdir()
            info = {
                "schema_namespace": "KMM_BackupInfo",
                "tree_created_time": "2026-01-01T00:00:00Z",
                "last_modified_time": "2026-01-01T00:00:00Z",
                "schema_version": "knighthana@0.1.0",
                "tree": {"name": "root", "type": "dir", "children": []},
            }
            (Path(backup_dir) / "backupinfo.json").write_text(json.dumps(info))
            errors = check_backup_gate(backup_dir)
            assert errors == [], f"Expected empty errors, got: {errors}"

        # Case 3: missing backupinfo.json
        with tempfile.TemporaryDirectory() as td:
            backup_dir = str(Path(td) / "backup") + "/"
            Path(backup_dir).mkdir()
            errors = check_backup_gate(backup_dir)
            assert "E_BACKUP_INFO_MISSING" in str(errors)

        # Case 4: missing tree in backupinfo.json
        with tempfile.TemporaryDirectory() as td:
            backup_dir = str(Path(td) / "backup") + "/"
            Path(backup_dir).mkdir()
            (Path(backup_dir) / "backupinfo.json").write_text(
                json.dumps({"schema_version": "1"})
            )
            errors = check_backup_gate(backup_dir)
            assert "E_BACKUP_TREE_MISSING" in str(errors)

    def test_tgt08_plan_fileops_manifest_has_gate_result(self):
        """T-GT-08: plan_fileops() 输出的 preflight_manifest 含 gate 结果。"""
        from unittest.mock import patch

        from modmgr.orchestrator.entry import Intent, TaskRequest
        from modmgr.orchestrator.fileops.planner.planner import plan_fileops

        context = {
            "final_mapping": [{"path": "/game/file.txt", "request": {"action": "replace", "path": "/src/file.txt"}}],
            "database": {
                "game": [{"basepath": "/game", "mixed_id": "game:270150"}],
                "mod": [],
                "steamlib": [],
            },
            "user_config": {"baksuffix": "kmmbackup"},
        }
        request = TaskRequest(
            identity="cli",
            intent=Intent.APPLY,
            resolver_type="file_paths",
            resolver_args={},
            flags={"bakignore": [], "force": False, "dry_run": False},
        )

        # Mock build_backup_dirs to return a known backup_dir
        with patch("modmgr.orchestrator.fileops.planner.planner.build_backup_dirs") as mock_build:
            mock_build.return_value = (
                {"/tmp/mock_backup.kmmbackup/": ["/game/file.txt"]},
                [],
            )
            plan = plan_fileops(request, context)

        # preflight_manifest should exist for APPLY intent
        assert plan.preflight_manifest is not None
        assert "backup_dirs" in plan.preflight_manifest
        # Each backup_dir entry should have gate_pass and gate_errors
        for entry in plan.preflight_manifest["backup_dirs"]:
            assert "gate_pass" in entry
            assert "gate_errors" in entry
        # Since mock backup_dir doesn't exist, gate should fail
        assert plan.preflight_ok is False
