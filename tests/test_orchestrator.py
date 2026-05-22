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
            backup_result={"ok": True},
            apply_result={"ok": True},
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ["E_SOMETHING"])
        self.assertEqual(result.trees, [{"path": "/a.txt"}])
        self.assertEqual(result.backup_result, {"ok": True})


class TestCompute(TestCase):
    """Tests for compute()."""

    def test_compute_no_rule_input_returns_explicit_error(self) -> None:
        """compute() without aggregated_rule_set → explicit error."""
        result = compute(
            database={},
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("E_NO_RULE_INPUT" in e for e in result.errors))

    def test_compute_with_valid_aggregated_rule_set(self) -> None:
        """compute() with a valid aggregated_rule_set should succeed."""
        result = compute(
            database={"game": [], "mod": []},
            aggregated_rule_set={"schema_namespace": "KMM_RuleSet", "operation": []},
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])

    def test_compute_with_empty_aggregated_rule_set_still_works(self) -> None:
        """compute() with an empty dict as aggregated_rule_set should succeed."""
        result = compute(
            database={"game": [], "mod": []},
            aggregated_rule_set={},
        )
        # An empty rule set is still valid input; actual success depends on compute_mapping
        self.assertIsNotNone(result)


@pytest.mark.skip(reason="backup() removed in orchestrator refactor")
class TestBackup(TestCase):
    """Tests for backup()."""

    def test_backup_no_files(self) -> None:
        """Empty final_mapping should raise ValueError (no paths to backup)."""
        with self.assertRaises(ValueError):
            backup(
                final_mapping=[],
                database={},
                user_config={},
            )


@pytest.mark.skip(reason="apply() removed in orchestrator refactor")
class TestApply(TestCase):
    """Tests for apply()."""

    def test_apply_dry_run_empty_mapping(self) -> None:
        """Empty final_mapping should raise ValueError (no paths to apply)."""
        with self.assertRaises(ValueError):
            apply(
                final_mapping=[],
                database={},
                user_config={},
                dry_run=False,
            )

    @patch("modmgr.orchestrator.apply_final_mapping")
    @patch("modmgr.orchestrator.build_backup_dirs")
    def test_apply_matches_paths_after_normalization(
        self,
        mock_build_backup_dirs,
        mock_apply_final_mapping,
    ) -> None:
        """Path matching should use normalized paths to avoid // vs / misses."""
        mock_build_backup_dirs.return_value = (
            {
                "/tmp/fixture/270150.abcd.kmmbackup/": [
                    "/tmp/fixture/content/2606099273/file.txt"
                ]
            },
            [],
        )
        mock_apply_final_mapping.return_value = {
            "ok": True,
            "applied": ["/tmp/fixture/content/2606099273/file.txt"],
            "skipped": [],
            "errors": [],
        }

        result = apply(
            final_mapping=[
                {
                    "path": "/tmp/fixture//content//2606099273/file.txt",
                    "request": {"action": "replace", "path": "/tmp/src/file.txt"},
                }
            ],
            database={},
            user_config={},
            dry_run=False,
        )

        self.assertTrue(result["ok"])
        mock_apply_final_mapping.assert_called_once()
        matched_entries = mock_apply_final_mapping.call_args.args[0]
        self.assertEqual(len(matched_entries), 1)
        self.assertEqual(
            matched_entries[0]["path"],
            "/tmp/fixture//content//2606099273/file.txt",
        )

    @patch("modmgr.orchestrator.apply_final_mapping")
    @patch("modmgr.orchestrator.build_backup_dirs")
    def test_apply_warns_when_backup_dir_has_no_matched_entries(
        self,
        mock_build_backup_dirs,
        mock_apply_final_mapping,
    ) -> None:
        """When a backup_dir has no matched mapping entries, a warning should be emitted."""
        mock_build_backup_dirs.return_value = (
            {
                "/tmp/fixture/270150.abcd.kmmbackup/": [
                    "/tmp/fixture/content/2606099273/not-in-mapping.txt"
                ]
            },
            [],
        )
        result = apply(
            final_mapping=[
                {
                    "path": "/tmp/fixture/content/2606099273/another.txt",
                    "request": {"action": "replace", "path": "/tmp/src/file.txt"},
                }
            ],
            database={},
            user_config={},
            dry_run=False,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["applied"], [])
        self.assertTrue(
            any(
                "W_APPLY_DIR_NO_MATCHED_ENTRIES" in w
                for w in result.get("warnings", [])
            )
        )
        self.assertTrue(
            any(
                "W_APPLY_NO_EFFECT" in w
                for w in result.get("warnings", [])
            )
        )
        self.assertEqual(result["diagnostics"]["processed_dirs"], 0)
        self.assertEqual(
            len(result["diagnostics"]["no_matched_entry_dirs"]),
            1,
        )
        mock_apply_final_mapping.assert_not_called()

    @patch("modmgr.orchestrator.apply_final_mapping")
    @patch("modmgr.orchestrator.build_backup_dirs")
    def test_apply_does_not_restore_kmmbakignore(
        self,
        mock_build_backup_dirs,
        mock_apply_final_mapping,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            contentid_dir = Path(tmp) / "content" / "2606099273"
            backup_dir = contentid_dir / "2606099273.abcd.kmmbackup"
            backup_dir.mkdir(parents=True)
            (backup_dir / ".kmmbakignore").write_text("*.log\n", encoding="utf-8")

            target = str(contentid_dir / "file.txt")
            mock_build_backup_dirs.return_value = ({str(backup_dir) + "/": [target]}, [])
            mock_apply_final_mapping.return_value = {
                "ok": True,
                "applied": [target],
                "skipped": [],
                "errors": [],
            }

            result = apply(
                final_mapping=[{"path": target, "request": {"action": "replace", "path": "/tmp/src.txt"}}],
                database={},
                user_config={},
                dry_run=False,
            )

            self.assertTrue(result["ok"])
            self.assertFalse((contentid_dir / ".kmmbakignore").exists())


@pytest.mark.skip(reason="_generate_apply_preflight/orchestrate_apply removed in orchestrator refactor")
class TestApplyPreflight(TestCase):
    @patch("modmgr.orchestrator.check_backup_gate")
    @patch("modmgr.orchestrator.build_backup_dirs")
    def test_generate_apply_preflight_collects_gate_failures(
        self,
        mock_build_backup_dirs,
        mock_check_backup_gate,
    ) -> None:
        mock_build_backup_dirs.return_value = (
            {"/tmp/fixture/270150.abcd.kmmbackup/": ["/tmp/fixture/game/file.txt"]},
            [],
        )
        mock_check_backup_gate.return_value = ["E_BACKUP_INFO_MISSING: /tmp/fixture/270150.abcd.kmmbackup/"]

        manifest = _generate_apply_preflight(
            final_mapping=[{"path": "/tmp/fixture/game/file.txt", "request": {"action": "replace", "path": "/tmp/src.txt"}}],
            database={},
            user_config={},
        )

        self.assertFalse(manifest["ok"])
        self.assertEqual(len(manifest["backup_dirs"]), 1)
        self.assertFalse(manifest["backup_dirs"][0]["gate_pass"])
        self.assertEqual(manifest["backup_dirs"][0]["applicable_entries"], 1)
        self.assertTrue(any("W_BACKUP_GATE_FAILED" in w for w in manifest["warnings"]))

    @patch("modmgr.orchestrator.apply")
    @patch("modmgr.orchestrator._generate_apply_preflight")
    @patch("modmgr.orchestrator._resolve_database")
    @patch("modmgr.orchestrator._get_workspace_manager")
    @patch("modmgr.orchestrator.discover_user_config")
    def test_orchestrate_apply_returns_preflight_failure_without_running_apply(
        self,
        mock_discover_user_config,
        mock_get_workspace_manager,
        mock_resolve_database,
        mock_generate_apply_preflight,
        mock_apply,
    ) -> None:
        mock_discover_user_config.return_value = {"workspace_dir": "/tmp/ws"}
        wm = mock_get_workspace_manager.return_value
        wm.exists.return_value = True
        wm.has_mapping.return_value = True
        wm.read_mapping.return_value = {"final_mapping": [{"path": "/tmp/game/a.txt", "request": {"action": "replace", "path": "/tmp/src.txt"}}]}
        wm.read_meta.return_value = {"database_name": "demo"}
        mock_resolve_database.return_value = {}
        mock_generate_apply_preflight.return_value = {
            "ok": False,
            "backup_dirs": [],
            "errors": ["E_BACKUP_INFO_MISSING: /tmp/backup/"],
            "warnings": ["W_BACKUP_GATE_FAILED: /tmp/backup/: E_BACKUP_INFO_MISSING: /tmp/backup/"],
            "diagnostics": {},
            "timestamp": "2026-05-20T00:00:00+00:00",
        }

        result = orchestrate_apply("ws-1")

        self.assertFalse(result.ok)
        self.assertEqual(result.errors, ["E_BACKUP_INFO_MISSING: /tmp/backup/"])
        self.assertTrue(any("W_BACKUP_GATE_FAILED" in w for w in result.warnings))
        self.assertIsNotNone(result.apply_result)
        self.assertIn("preflight", result.apply_result["diagnostics"])
        mock_apply.assert_not_called()

    @patch("modmgr.orchestrator.apply")
    @patch("modmgr.orchestrator._generate_apply_preflight")
    @patch("modmgr.orchestrator._resolve_database")
    @patch("modmgr.orchestrator._get_workspace_manager")
    @patch("modmgr.orchestrator.discover_user_config")
    def test_orchestrate_apply_runs_apply_after_preflight_success(
        self,
        mock_discover_user_config,
        mock_get_workspace_manager,
        mock_resolve_database,
        mock_generate_apply_preflight,
        mock_apply,
    ) -> None:
        mock_discover_user_config.return_value = {"workspace_dir": "/tmp/ws"}
        wm = mock_get_workspace_manager.return_value
        wm.exists.return_value = True
        wm.has_mapping.return_value = True
        final_mapping = [{"path": "/tmp/game/a.txt", "request": {"action": "replace", "path": "/tmp/src.txt"}}]
        wm.read_mapping.return_value = {"final_mapping": final_mapping}
        wm.read_meta.return_value = {"database_name": "demo"}
        mock_resolve_database.return_value = {"game": []}
        mock_generate_apply_preflight.return_value = {
            "ok": True,
            "backup_dirs": [{"path": "/tmp/backup/", "gate_pass": True, "gate_errors": [], "applicable_entries": 1}],
            "errors": [],
            "warnings": [],
            "diagnostics": {},
            "timestamp": "2026-05-20T00:00:00+00:00",
        }
        mock_apply.return_value = {"ok": True, "applied": ["/tmp/game/a.txt"], "skipped": [], "errors": [], "warnings": [], "diagnostics": {}, "dry_run": False}

        result = orchestrate_apply("ws-1")

        self.assertTrue(result.ok)
        mock_apply.assert_called_once()
        self.assertIn("preflight", result.apply_result["diagnostics"])


@pytest.mark.skip(reason="run() removed in orchestrator refactor")
class TestRun(TestCase):
    """Tests for the full run() pipeline."""

    def test_run_fails_without_aggregated_rule_set(self) -> None:
        """Run pipeline without aggregated_rule_set should return failed PipelineResult."""
        result = run(
            database={},
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("E_NO_RULE_INPUT" in e for e in result.errors))

    def test_run_with_valid_aggregated_rule_set(self) -> None:
        """run() with a valid aggregated_rule_set should succeed (dry-run)."""
        result = run(
            database={"game": [], "mod": []},
            aggregated_rule_set={"schema_namespace": "KMM_RuleSet", "operation": []},
            user_config={"baksuffix": "kmmbackup"},
            dry_run=True,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])

    def test_run_no_rule_input_returns_explicit_error(self) -> None:
        """run() without aggregated_rule_set → explicit error."""
        result = run(
            database={},
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("E_NO_RULE_INPUT" in e for e in result.errors))


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
            aggregated_rule_set={},
            managed_entries={"game": {"270150": ["/fake/path/"]}},
        )
        # Should not throw; actual success depends on compute_mapping
        self.assertIsNotNone(result)

    def test_compute_managed_entries_none(self) -> None:
        """compute() with managed_entries=None should still work."""
        result = compute(
            database={},
            aggregated_rule_set={},
            managed_entries=None,
        )
        self.assertIsNotNone(result)


@pytest.mark.skip(reason="run() removed in orchestrator refactor")
class TestRunManagedEntries(TestCase):
    """Tests for run() with managed_entries."""

    def test_run_accepts_managed_entries(self) -> None:
        """run() should accept managed_entries without error."""
        result = run(
            database={},
            aggregated_rule_set={},
            managed_entries={"game": {"270150": ["/fake/path/"]}},
        )
        self.assertIsNotNone(result)

    def test_run_managed_entries_none(self) -> None:
        """run() with managed_entries=None should still work."""
        result = run(
            database={},
            aggregated_rule_set={},
            managed_entries=None,
        )
        self.assertIsNotNone(result)


class TestProgressCallback(TestCase):
    """Tests for progress callback invocation."""

    def test_progress_callback_invoked(self) -> None:
        """Progress callback should be called during compute."""
        calls: list[tuple] = []

        def callback(step: str, finished: int, total: int, message: str = "") -> None:
            calls.append((step, finished, total, message))

        result = compute(
            database={"game": [], "mod": []},
            aggregated_rule_set={"schema_namespace": "KMM_RuleSet", "operation": []},
            on_progress=callback,
        )

        # Callback should have been called at least for compute phase
        self.assertTrue(len(calls) > 0)
        # Should have "compute" step
        steps = [c[0] for c in calls]
        self.assertIn("compute", steps)
