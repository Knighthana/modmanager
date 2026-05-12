"""Tests for modmanager.orchestrator module."""

from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path
from unittest import TestCase

from modmanager.orchestrator import (
    PipelineResult,
    _apply_managed_filter,
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
            backup_result={"ok": True},
            apply_result={"ok": True},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ["E_SOMETHING"])
        self.assertEqual(result.trees, [{"path": "/a.txt"}])
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
                backup_dir=str(Path(td) / "nonexistent") + "/",
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
        result = compute(
            database={},
            kmm_rule_paths=["/nonexistent/rule.json"],
            user_config_path="/nonexistent/user_config.json",
            managed_entries={"game": {"270150": ["/fake/path/"]}},
        )
        # Should still fail due to bad inputs (not due to managed_entries)
        self.assertFalse(result.ok)
        self.assertTrue(len(result.errors) > 0)

    def test_compute_managed_entries_none(self) -> None:
        """compute() with managed_entries=None should still work (backward compat)."""
        result = compute(
            database={},
            kmm_rule_paths=["/nonexistent/rule.json"],
            user_config_path="/nonexistent/user_config.json",
            managed_entries=None,
        )
        self.assertFalse(result.ok)


class TestRunManagedEntries(TestCase):
    """Tests for run() with managed_entries."""

    def test_run_accepts_managed_entries(self) -> None:
        """run() should accept managed_entries without error."""
        result = run(
            database={},
            kmm_rule_paths=["/nonexistent/rule.json"],
            user_config_path="/nonexistent/user_config.json",
            backup_dir="/tmp",
            managed_entries={"game": {"270150": ["/fake/path/"]}},
        )
        self.assertFalse(result.ok)
        self.assertTrue(len(result.errors) > 0)

    def test_run_managed_entries_none(self) -> None:
        """run() with managed_entries=None should still work (backward compat)."""
        result = run(
            database={},
            kmm_rule_paths=["/nonexistent/rule.json"],
            user_config_path="/nonexistent/user_config.json",
            backup_dir="/tmp",
            managed_entries=None,
        )
        self.assertFalse(result.ok)


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
