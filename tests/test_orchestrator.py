"""Tests for modmanager_cli.orchestrator module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from modmanager_cli.orchestrator import (
    PipelineResult,
    apply,
    backup,
    compute,
    run,
)


class TestPipelineResult(TestCase):
    """Tests for PipelineResult dataclass."""

    def test_pipeline_result_defaults(self) -> None:
        """Verify default field values of an empty PipelineResult."""
        result = PipelineResult(ok=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.forest, [])
        self.assertEqual(result.final_mapping, [])
        self.assertEqual(result.mapping_result, {})
        self.assertIsNone(result.backup_result)
        self.assertIsNone(result.apply_result)

    def test_pipeline_result_custom_values(self) -> None:
        """Verify custom field assignment."""
        result = PipelineResult(
            ok=False,
            errors=["E_SOMETHING"],
            warnings=["W_SOMETHING"],
            forest=[{"path": "/a.txt"}],
            final_mapping=[{"path": "/b.txt"}],
            mapping_result={"key": "val"},
            backup_result={"ok": True},
            apply_result={"ok": True},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ["E_SOMETHING"])
        self.assertEqual(result.forest, [{"path": "/a.txt"}])
        self.assertEqual(result.backup_result, {"ok": True})


class TestCompute(TestCase):
    """Tests for compute()."""

    def test_compute_aggregation_failure(self) -> None:
        """Invalid kmm_rule_paths should result in a failed PipelineResult."""
        result = compute(
            database={},
            kmm_rule_paths=["/nonexistent/rule.json"],
            user_config_path="/nonexistent/user_config.json",
        )
        self.assertFalse(result.ok)
        self.assertTrue(len(result.errors) > 0)
        # Should contain file-load related error messages
        self.assertTrue(
            any("E_KMM_RULE_LOAD_FAILED" in e for e in result.errors)
            or any("E_USER_CONFIG_LOAD_FAILED" in e for e in result.errors)
        )


class TestBackup(TestCase):
    """Tests for backup()."""

    def test_backup_no_files(self) -> None:
        """Empty final_mapping should return ok result with empty backed_up."""
        result = backup(
            mapping_result={"final_mapping": []},
            backup_dir="/nonexistent/backup",
        )
        self.assertTrue(result.get("ok"))
        self.assertEqual(result.get("backed_up"), [])
        self.assertEqual(result.get("skipped"), [])


class TestApply(TestCase):
    """Tests for apply()."""

    def test_apply_dry_run_missing_backup_dir(self) -> None:
        """Dry-run apply without backup gate should fail."""
        with tempfile.TemporaryDirectory() as td:
            result = apply(
                final_mapping=[],
                backup_dir=str(Path(td) / "nonexistent"),
                dry_run=False,
            )
            self.assertFalse(result.get("ok"))
            self.assertTrue(len(result.get("errors", [])) > 0)


class TestRun(TestCase):
    """Tests for the full run() pipeline."""

    def test_run_fails_on_bad_inputs(self) -> None:
        """Run pipeline with bad inputs should return failed PipelineResult."""
        result = run(
            database={},
            kmm_rule_paths=["/nonexistent/rule.json"],
            user_config_path="/nonexistent/user_config.json",
            backup_dir="/tmp",
        )
        self.assertFalse(result.ok)
        self.assertTrue(len(result.errors) > 0)


class TestProgressCallback(TestCase):
    """Tests for progress callback invocation."""

    def test_progress_callback_invoked(self) -> None:
        """Progress callback should be called during compute with bad inputs."""
        calls: list[tuple] = []

        def callback(step: str, finished: int, total: int, message: str = "") -> None:
            calls.append((step, finished, total, message))

        result = compute(
            database={},
            kmm_rule_paths=["/nonexistent/rule.json"],
            user_config_path="/nonexistent/user_config.json",
            on_progress=callback,
        )

        # Callback should have been called at least for aggregate phase
        self.assertTrue(len(calls) > 0)
        # Should have "aggregate" step
        steps = [c[0] for c in calls]
        self.assertIn("aggregate", steps)

        # Result should still be failed (bad inputs)
        self.assertFalse(result.ok)
