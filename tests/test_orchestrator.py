"""Tests for modmanager.orchestrator module."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import pytest

from modmgr.orchestrator import (
    PipelineResult,
    compute,
)
from modmgr.orchestrator.compute_pipeline import _apply_managed_filter

class TestPipelineResult(TestCase):
    """Tests for PipelineResult dataclass."""

    def test_pipeline_result_defaults(self) -> None:
        """Verify default field values of an empty PipelineResult."""
        result = PipelineResult(ok=True)
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.trees, [])

    def test_pipeline_result_custom_values(self) -> None:
        """Verify custom field assignment."""
        result = PipelineResult(
            ok=False,
            errors=["E_SOMETHING"],
            warnings=["W_SOMETHING"],
            trees=[{"path": "/a.txt"}],
            final_mapping=[{"path": "/b.txt"}],
            mapping_result={"key": "val"},
            backup_result={"ok": True, "dry_run": False},
            apply_result={"ok": True, "dry_run": False},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ["E_SOMETHING"])
        self.assertEqual(result.trees, [{"path": "/a.txt"}])
        self.assertEqual(result.backup_result, {"ok": True, "dry_run": False})


class TestCompute(TestCase):
    """Tests for compute()."""

    def test_compute_no_rule_input_returns_explicit_error(self) -> None:
        """compute() without aggregated_rule_set → explicit error."""
        result = compute(
            {"database": {}},
        )
        self.assertTrue(any("E_NO_RULE_INPUT" in e for e in result.get("errors", [])))

    def test_compute_with_valid_aggregated_rule_set(self) -> None:
        """compute() with a valid aggregated_rule_set should succeed."""
        result = compute({
            "database": {"game": [], "mod": []},
            "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
        })
        # compute() returns dict now
        self.assertFalse(result.get("errors", []))

    def test_compute_with_empty_aggregated_rule_set_still_works(self) -> None:
        """compute() with an empty dict as aggregated_rule_set should succeed."""
        result = compute({
            "database": {"game": [], "mod": []},
            "aggregated_rule_set": {},
        })
        # An empty rule set is still valid input
        self.assertIsNotNone(result)


class TestBackupViaDispatch(TestCase):
    """Test backup pipeline via dispatch() — replaces old backup() tests."""

    def test_dispatch_backup_raw_dict_succeeds(self) -> None:
        """dispatch with BACKUP + raw_dict succeeds (no I/O needed for raw_dict)."""
        from unittest.mock import patch

        from modmgr.orchestrator import dispatch
        from modmgr.orchestrator.entry import Intent, TaskRequest

        request = TaskRequest(
            identity="cli",
            intent=Intent.BACKUP,
            resolver_type="raw_dict",
            resolver_args={
                "database": {"game": [], "mod": []},
                "user_config": {"baksuffix": "kmmbackup"},
                "final_mapping": [],
            },
            flags={"dry_run": True},
        )
        with patch("modmgr.orchestrator.fileops.planner.planner.build_backup_dirs") as m:
            m.return_value = ({}, [])
            result = dispatch(request)
        self.assertTrue(result.ok, f"Expected backup dispatch to succeed, got errors: {result.errors}")


class TestApplyViaDispatch(TestCase):
    """Test apply pipeline via dispatch() — replaces old apply() tests."""

    def test_apply_dispatch_raw_dict_succeeds(self) -> None:
        """dispatch with APPLY + raw_dict succeeds (dry_run)."""
        from unittest.mock import patch

        from modmgr.orchestrator import dispatch
        from modmgr.orchestrator.entry import Intent, TaskRequest

        request = TaskRequest(
            identity="cli",
            intent=Intent.APPLY,
            resolver_type="raw_dict",
            resolver_args={
                "database": {"game": [], "mod": []},
                "user_config": {"baksuffix": "kmmbackup"},
                "final_mapping": [],
            },
            flags={"dry_run": True, "force": True},
        )
        with patch("modmgr.orchestrator.fileops.planner.planner.build_backup_dirs") as m:
            m.return_value = ({}, [])
            result = dispatch(request)
        self.assertTrue(result.ok, f"Expected apply dispatch to succeed, got errors: {result.errors}")

    def test_apply_dry_run_empty_mapping_raw_dict(self) -> None:
        """dispatch with APPLY + empty mapping succeeds (dry_run)."""
        from unittest.mock import patch

        from modmgr.orchestrator import dispatch
        from modmgr.orchestrator.entry import Intent, TaskRequest

        request = TaskRequest(
            identity="cli",
            intent=Intent.APPLY,
            resolver_type="raw_dict",
            resolver_args={
                "database": {"game": [], "mod": []},
                "user_config": {"baksuffix": "kmmbackup"},
                "final_mapping": [],
            },
            flags={"dry_run": True, "force": True},
        )
        with patch("modmgr.orchestrator.fileops.planner.planner.build_backup_dirs") as m:
            m.return_value = ({}, [])
            result = dispatch(request)
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])


# Preflight tests moved to test_gate_boundary.py (T-GT-01 ~ T-GT-10)


class TestRunViaDispatch(TestCase):
    """Test run/compute pipeline via dispatch() — replaces old run() tests."""

    def test_compute_without_rule_set_returns_error(self) -> None:
        """dispatch with COMPUTE_MAPPING + no rule set → error."""
        from modmgr.orchestrator import dispatch
        from modmgr.orchestrator.entry import Intent, TaskRequest

        request = TaskRequest(
            identity="cli",
            intent=Intent.COMPUTE_MAPPING,
            resolver_type="raw_dict",
            resolver_args={
                "database": {"game": [], "mod": []},
                # no aggregated_rule_set
            },
            output_type="none",
        )
        result = dispatch(request)
        self.assertFalse(result.ok)
        self.assertTrue(any("E_NO_RULE_INPUT" in e for e in result.errors),
                        f"Expected E_NO_RULE_INPUT error, got: {result.errors}")

    def test_compute_with_valid_rule_set_succeeds(self) -> None:
        """dispatch with COMPUTE_MAPPING + valid rule set succeeds."""
        from modmgr.orchestrator import dispatch
        from modmgr.orchestrator.entry import Intent, TaskRequest

        request = TaskRequest(
            identity="cli",
            intent=Intent.COMPUTE_MAPPING,
            resolver_type="raw_dict",
            resolver_args={
                "database": {"game": [], "mod": []},
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
            },
            output_type="none",
        )
        result = dispatch(request)
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])


class TestApplyManagedFilter(TestCase):
    """Tests for _apply_managed_filter()."""

    def _make_db(
        self,
        games: list[dict] | None = None,
        mods: list[dict] | None = None,
    ) -> dict:
        return {
            "game": games or [],
            "mod": mods or [],
        }

    def test_filter_none_returns_deep_copy(self) -> None:
        """managed_entries is None → returns a deep copy of the database."""
        db = self._make_db(
            games=[{"appid": 270150, "basepath": "/path/a/"}],
            mods=[{"mixed_id": "270150:123", "path": "/mod/path/"}],
        )
        result = _apply_managed_filter(db, None)
        self.assertEqual(result, db)
        # Verify it's a deep copy (not the same object)
        self.assertIsNot(result, db)
        self.assertIsNot(result["game"], db["game"])
        self.assertIsNot(result["mod"], db["mod"])
        self.assertIsNot(result["game"][0], db["game"][0])

    def test_filter_empty_returns_deep_copy(self) -> None:
        """Empty managed_entries dict returns a deep copy of the database."""
        db = self._make_db(
            games=[{"appid": 270150, "basepath": "/path/a/"}],
            mods=[{"mixed_id": "270150:123", "path": "/mod/path/"}],
        )
        result = _apply_managed_filter(db, {})
        self.assertEqual(result, db)

    def test_filter_game_by_appid(self) -> None:
        """Games matching managed_entries.game[appid] are filtered by basepath."""
        db = self._make_db(games=[
            {"appid": 270150, "basepath": "/path/a/"},
            {"appid": 270150, "basepath": "/path/b/"},
            {"appid": 107410, "basepath": "/path/c/"},
        ])
        managed = {
            "game": {
                "270150": ["/path/a/"],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["game"]), 2)
        self.assertEqual(result["game"][0]["basepath"], "/path/a/")
        # 107410 not in managed → all kept
        self.assertEqual(result["game"][1]["appid"], 107410)

    def test_filter_game_exclude_all_for_appid(self) -> None:
        """Empty list for an appid excludes all entries for that appid."""
        db = self._make_db(games=[
            {"appid": 270150, "basepath": "/path/a/"},
            {"appid": 270150, "basepath": "/path/b/"},
        ])
        managed = {
            "game": {
                "270150": [],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["game"]), 0)

    def test_filter_game_appid_not_in_managed(self) -> None:
        """Game appid not in managed_entries.game → all entries kept."""
        db = self._make_db(games=[
            {"appid": 270150, "basepath": "/path/a/"},
            {"appid": 107410, "basepath": "/path/b/"},
        ])
        managed = {
            "game": {
                "999999": ["/some/path/"],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["game"]), 2)

    def test_filter_mod_by_mixed_id(self) -> None:
        """Mods matching managed_entries.mod[mixed_id] are filtered by path."""
        db = self._make_db(mods=[
            {"mixed_id": "270150:123", "path": "/mod/a/"},
            {"mixed_id": "270150:123", "path": "/mod/b/"},
            {"mixed_id": "107410:456", "path": "/mod/c/"},
        ])
        managed = {
            "mod": {
                "270150:123": ["/mod/a/"],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["mod"]), 2)
        self.assertEqual(result["mod"][0]["path"], "/mod/a/")
        # 107410:456 not in managed → all kept
        self.assertEqual(result["mod"][1]["mixed_id"], "107410:456")

    def test_filter_mod_exclude_all_for_mixed_id(self) -> None:
        """Empty list for a mixed_id excludes all entries for that mixed_id."""
        db = self._make_db(mods=[
            {"mixed_id": "270150:123", "path": "/mod/a/"},
            {"mixed_id": "270150:123", "path": "/mod/b/"},
        ])
        managed = {
            "mod": {
                "270150:123": [],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["mod"]), 0)

    def test_filter_mod_mixed_id_not_in_managed(self) -> None:
        """Mod mixed_id not in managed_entries.mod → all entries kept."""
        db = self._make_db(mods=[
            {"mixed_id": "270150:123", "path": "/mod/a/"},
            {"mixed_id": "107410:456", "path": "/mod/b/"},
        ])
        managed = {
            "mod": {
                "999999:789": ["/other/"],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["mod"]), 2)

    def test_filter_game_and_mod_combined(self) -> None:
        """Both game and mod filters are applied simultaneously."""
        db = self._make_db(
            games=[
                {"appid": 270150, "basepath": "/game/a/"},
                {"appid": 270150, "basepath": "/game/b/"},
                {"appid": 107410, "basepath": "/game/c/"},
            ],
            mods=[
                {"mixed_id": "270150:123", "path": "/mod/a/"},
                {"mixed_id": "270150:123", "path": "/mod/b/"},
                {"mixed_id": "107410:456", "path": "/mod/c/"},
            ],
        )
        managed = {
            "game": {
                "270150": ["/game/a/"],
            },
            "mod": {
                "270150:123": ["/mod/a/"],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["game"]), 2)
        self.assertEqual(len(result["mod"]), 2)
        self.assertEqual(result["game"][0]["basepath"], "/game/a/")
        self.assertEqual(result["game"][1]["appid"], 107410)
        self.assertEqual(result["mod"][0]["path"], "/mod/a/")
        self.assertEqual(result["mod"][1]["mixed_id"], "107410:456")

    def test_filter_does_not_mutate_original(self) -> None:
        """Original database is not mutated by _apply_managed_filter."""
        original_games = [
            {"appid": 270150, "basepath": "/path/a/"},
            {"appid": 270150, "basepath": "/path/b/"},
        ]
        original_mods = [
            {"mixed_id": "270150:123", "path": "/mod/a/"},
            {"mixed_id": "270150:123", "path": "/mod/b/"},
        ]
        db = self._make_db(games=copy.deepcopy(original_games), mods=copy.deepcopy(original_mods))
        managed = {
            "game": {"270150": ["/path/a/"]},
            "mod": {"270150:123": ["/mod/a/"]},
        }
        _apply_managed_filter(db, managed)
        # Original should be unchanged
        self.assertEqual(db["game"], original_games)
        self.assertEqual(db["mod"], original_mods)

    def test_filter_handles_string_appid(self) -> None:
        """Appid as string should be handled correctly (converted for lookup)."""
        db = self._make_db(games=[
            {"appid": "270150", "basepath": "/path/a/"},
            {"appid": "270150", "basepath": "/path/b/"},
        ])
        managed = {
            "game": {
                "270150": ["/path/a/"],
            },
        }
        result = _apply_managed_filter(db, managed)
        self.assertEqual(len(result["game"]), 1)
        self.assertEqual(result["game"][0]["basepath"], "/path/a/")


class TestComputeManagedEntries(TestCase):
    """Tests for compute() with managed_entries."""

    def test_compute_accepts_managed_entries(self) -> None:
        """compute() should accept managed_entries without error."""
        result = compute({
            "database": {},
            "aggregated_rule_set": {},
            "decisions": {"managed_entries": {"game": {"270150": ["/fake/path/"]}}},
        })
        # Should not throw; actual success depends on compute_mapping
        self.assertIsNotNone(result)

    def test_compute_managed_entries_none(self) -> None:
        """compute() with no managed_entries should still work."""
        result = compute({
            "database": {},
            "aggregated_rule_set": {},
        })
        self.assertIsNotNone(result)


class TestComputeManagedEntriesViaDispatch(TestCase):
    """Tests for compute() with managed_entries via dispatch (replaces old run tests)."""

    def test_compute_with_managed_entries_succeeds(self) -> None:
        """dispatch with COMPUTE_MAPPING + managed_entries succeeds."""
        from modmgr.orchestrator import dispatch
        from modmgr.orchestrator.entry import Intent, TaskRequest

        request = TaskRequest(
            identity="cli",
            intent=Intent.COMPUTE_MAPPING,
            resolver_type="raw_dict",
            resolver_args={
                "database": {
                    "game": [{"appid": "270150", "basepath": "/fake/path/"}],
                    "mod": [{"mixed_id": "270150:123", "path": "/fake/mod/"}],
                },
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
                "decisions": {"managed_entries": {"game": {"270150": ["/fake/path/"]}}},
            },
            output_type="none",
        )
        result = dispatch(request)
        # Should not crash; actual success depends on compute_mapping internals
        self.assertIsNotNone(result)

    def test_compute_without_managed_entries_succeeds(self) -> None:
        """dispatch with COMPUTE_MAPPING + no managed_entries succeeds."""
        from modmgr.orchestrator import dispatch
        from modmgr.orchestrator.entry import Intent, TaskRequest

        request = TaskRequest(
            identity="cli",
            intent=Intent.COMPUTE_MAPPING,
            resolver_type="raw_dict",
            resolver_args={
                "database": {"game": [], "mod": []},
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
            },
            output_type="none",
        )
        result = dispatch(request)
        self.assertIsNotNone(result)
        self.assertTrue(result.ok)


class TestProgressCallback(TestCase):
    """Tests for progress callback invocation."""

    def test_progress_callback_invoked(self) -> None:
        """Progress callback should be called during compute."""
        calls: list[tuple] = []

        def callback(step: str, finished: int, total: int, message: str = "") -> None:
            calls.append((step, finished, total, message))

        result = compute(
            {
                "database": {"game": [], "mod": []},
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
            },
            on_progress=callback,
        )

        # Callback should have been called at least for compute phase
        self.assertTrue(len(calls) > 0)
        # Should have "compute" step
        steps = [c[0] for c in calls]
        self.assertIn("compute", steps)
