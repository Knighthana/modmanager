"""Tests for .kmmignore copy/restore functions.

Verifies that ``_copy_kmmignore_to_backup`` and
``_copy_kmmignore_from_backup`` correctly preserve and restore
.kmmignore files between source directories and backup directories,
both as standalone functions and integrated in the orchestrator pipeline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from modmgr.orchestrator import (
    PipelineResult,
    _copy_kmmignore_to_backup,
    _copy_kmmignore_from_backup,
    _dispatch_fileops,
)
from modmgr.orchestrator.entry import Intent, TaskRequest
from modmgr.orchestrator.ignore_rules import IgnoreRuleSet
from modmgr.orchestrator.planner_fileops import FileOpsPlan


# ── Helpers ──────────────────────────────────────────────────────────


def _make_backup_dirs_entry(
    source_root: Path, backup_dir_name: str = "270150.abc.kmmbackup"
) -> tuple[Path, dict[str, list[str]]]:
    """Create a source_root with a child backup_dir, return (backup_dir, backup_dirs_dict)."""
    backup_dir = source_root / backup_dir_name
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir, {str(backup_dir) + "/": ["some/file.txt"]}


# ── Backup tests ─────────────────────────────────────────────────────


class TestKmmignoreCopyBackup:
    """Tests for _copy_kmmignore_to_backup()."""

    def test_kmmignore_copied_from_source_root(self, tmp_path: Path) -> None:
        """Source root has .kmmignore -> backup_dir gets a copy."""
        source_root = tmp_path / "content" / "270150"
        source_root.mkdir(parents=True)
        content = "# my ignore rules\n*.log\n"
        (source_root / ".kmmignore").write_text(content)

        backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)

        _copy_kmmignore_to_backup(backup_dirs)

        dest = backup_dir / ".kmmignore"
        assert dest.is_file(), f".kmmignore should exist at {dest}"
        assert dest.read_text() == content

    def test_kmmignore_copied_from_subdir(self, tmp_path: Path) -> None:
        """Parent/ancestor directory has .kmmignore -> backup_dir gets a copy."""
        source_root = tmp_path / "workspace" / "content" / "270150"
        source_root.mkdir(parents=True)

        # Place .kmmignore one level above source_root
        parent = source_root.parent  # workspace/content/
        content = "ignore_me=yes\n"
        (parent / ".kmmignore").write_text(content)

        backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)

        _copy_kmmignore_to_backup(backup_dirs)

        # The function walks UP from source_root; the .kmmignore in the
        # parent directory is found and copied into backup_dir
        found = list(backup_dir.rglob(".kmmignore"))
        assert len(found) >= 1, ".kmmignore should exist somewhere under backup_dir"

    def test_no_kmmignore_no_copy(self, tmp_path: Path) -> None:
        """No .kmmignore files -> no error, nothing copied."""
        source_root = tmp_path / "content" / "270150"
        source_root.mkdir(parents=True)

        backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)

        _copy_kmmignore_to_backup(backup_dirs)

        found = list(backup_dir.rglob(".kmmignore"))
        assert len(found) == 0


# ── Restore tests ────────────────────────────────────────────────────


class TestKmmignoreCopyRestore:
    """Tests for _copy_kmmignore_from_backup()."""

    def test_kmmignore_restored_from_backup(self, tmp_path: Path) -> None:
        """backup_dir has .kmmignore -> restored to source root."""
        source_root = tmp_path / "content" / "270150"
        source_root.mkdir(parents=True)

        backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)
        content = "# restored rules\n*.log\n"
        (backup_dir / ".kmmignore").write_text(content)

        _copy_kmmignore_from_backup(backup_dirs)

        dest = source_root / ".kmmignore"
        assert dest.is_file(), f".kmmignore should be restored to {dest}"
        assert dest.read_text() == content

    def test_no_kmmignore_no_restore(self, tmp_path: Path) -> None:
        """No .kmmignore in backup -> no error, no change to source."""
        source_root = tmp_path / "content" / "270150"
        source_root.mkdir(parents=True)

        # Create a pre-existing file in source_root to verify it's unchanged
        existing = source_root / "existing.txt"
        existing.write_text("preserved")

        backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)

        _copy_kmmignore_from_backup(backup_dirs)

        # No .kmmignore should appear in source_root
        assert not (source_root / ".kmmignore").exists()
        # Existing file should be untouched
        assert existing.read_text() == "preserved"


# ── Integration tests via _dispatch_fileops ─────────────────────────


@pytest.fixture
def _patch_plan_and_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fixture that patches plan_fileops and execute functions in the orchestrator module.

    The caller should set ``monkeypatch.setattr(orch, '_the_flag', <plan>)``
    to inject the desired FileOpsPlan.
    """
    # This fixture is intentionally a no-op; consumers use monkeypatch directly.
    # Defined here for docstring only.
    return


class TestKmmignoreIntegration:
    """Tests that verify .kmmignore preservation through _dispatch_fileops."""

    def _run_with_mocked_plan(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        intent: Intent,
        plan_builder,
    ) -> None:
        """Helper: patch plan_fileops + execute, then call _dispatch_fileops."""
        import modmgr.orchestrator as orch

        plan = plan_builder(tmp_path)
        monkeypatch.setattr(orch, "plan_fileops", lambda *a, **kw: plan)

        if intent == Intent.BACKUP:
            monkeypatch.setattr(
                orch,
                "_execute_backup_plan",
                lambda *a, **kw: PipelineResult(ok=True),
            )
        elif intent == Intent.RESTORE:
            monkeypatch.setattr(
                orch,
                "_execute_restore_plan",
                lambda *a, **kw: PipelineResult(ok=True),
            )

        request = TaskRequest(
            identity="web",
            intent=intent,
            resolver_type="raw_dict",
            resolver_args={
                "final_mapping": [],
                "database": {"game": []},
                "user_config": {"baksuffix": "kmmbackup"},
            },
        )

        result = _dispatch_fileops(request, None)
        assert result.ok, f"_dispatch_fileops failed: {result.errors}"

    # ── Backup integration ─────────────────────────────────────

    def test_backup_copies_kmmignore(self, tmp_path: Path, monkeypatch) -> None:
        """Backup intent through _dispatch_fileops -> .kmmignore copied to backup_dir."""

        def build_plan(tmp: Path) -> FileOpsPlan:
            source_root = tmp / "content" / "270150"
            source_root.mkdir(parents=True)
            (source_root / ".kmmignore").write_text("*.log\n")

            backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)
            return FileOpsPlan(
                intent=Intent.BACKUP,
                backup_dirs=backup_dirs,
                entries_by_backup_dir={},
                ignore_rules=IgnoreRuleSet(),
                dry_run=False,
                preflight_ok=None,
            )

        self._run_with_mocked_plan(tmp_path, monkeypatch, Intent.BACKUP, build_plan)

        # Verify .kmmignore was copied into backup_dir
        backup_dir = tmp_path / "content" / "270150" / "270150.abc.kmmbackup"
        assert (backup_dir / ".kmmignore").is_file()

    def test_backup_no_kmmignore_no_copy(self, tmp_path: Path, monkeypatch) -> None:
        """Backup intent with no .kmmignore -> no copy, no error."""

        def build_plan(tmp: Path) -> FileOpsPlan:
            source_root = tmp / "content" / "270150"
            source_root.mkdir(parents=True)
            backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)
            return FileOpsPlan(
                intent=Intent.BACKUP,
                backup_dirs=backup_dirs,
                entries_by_backup_dir={},
                ignore_rules=IgnoreRuleSet(),
                dry_run=False,
                preflight_ok=None,
            )

        self._run_with_mocked_plan(tmp_path, monkeypatch, Intent.BACKUP, build_plan)

        backup_dir = tmp_path / "content" / "270150" / "270150.abc.kmmbackup"
        assert not (backup_dir / ".kmmignore").exists()

    # ── Restore integration ────────────────────────────────────

    def test_restore_recovers_kmmignore(self, tmp_path: Path, monkeypatch) -> None:
        """Restore intent through _dispatch_fileops -> .kmmignore restored to source."""

        def build_plan(tmp: Path) -> FileOpsPlan:
            source_root = tmp / "content" / "270150"
            source_root.mkdir(parents=True)
            backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)
            (backup_dir / ".kmmignore").write_text("*.log\nrestored")
            return FileOpsPlan(
                intent=Intent.RESTORE,
                backup_dirs=backup_dirs,
                entries_by_backup_dir={},
                ignore_rules=IgnoreRuleSet(),
                dry_run=False,
                preflight_ok=None,
            )

        self._run_with_mocked_plan(tmp_path, monkeypatch, Intent.RESTORE, build_plan)

        source_root = tmp_path / "content" / "270150"
        assert (source_root / ".kmmignore").is_file()
        assert (source_root / ".kmmignore").read_text() == "*.log\nrestored"

    def test_restore_no_kmmignore_no_change(self, tmp_path: Path, monkeypatch) -> None:
        """Restore intent with no .kmmignore in backup -> source unchanged."""

        def build_plan(tmp: Path) -> FileOpsPlan:
            source_root = tmp / "content" / "270150"
            source_root.mkdir(parents=True)
            backup_dir, backup_dirs = _make_backup_dirs_entry(source_root)
            return FileOpsPlan(
                intent=Intent.RESTORE,
                backup_dirs=backup_dirs,
                entries_by_backup_dir={},
                ignore_rules=IgnoreRuleSet(),
                dry_run=False,
                preflight_ok=None,
            )

        self._run_with_mocked_plan(tmp_path, monkeypatch, Intent.RESTORE, build_plan)

        source_root = tmp_path / "content" / "270150"
        assert not (source_root / ".kmmignore").exists()
