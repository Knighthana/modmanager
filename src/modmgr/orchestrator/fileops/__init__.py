"""fileops package — execute primitives for file operations.

Absorbed from ``_dispatch_fileops`` (previously in ``orchestrator/__init__``).

Provides:
  - ``execute`` — unified entry point: plan → preflight gate → primitive.
  - ``_execute_backup_plan``
  - ``_execute_apply_plan``
  - ``_execute_restore_plan``
  - ``_execute_run_plan``
"""

from __future__ import annotations

from typing import Any

from .._common import PipelineResult, ProgressCallback
from ..entry import Intent
from ..resolver import CleanContext
from ...apply_ops import apply_entries
from ...backup_ops import load_backup_info, run_differential_backup
from ...prep import prep_backup_dir
from ...restore_ops import restore_entries
from ._common import _notify
from .planner.planner import FileOpsPlan, plan_fileops


def execute(
    request: Any,  # TaskRequest
    data: dict,
    intent: Intent,
    flags: dict,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Plan → preflight gate → execute primitive.

    Absorbed from the inner logic of ``_dispatch_fileops``.
    Resolver selection + resolve remain in ``dispatch()``.

    Args:
        request: TaskRequest (passed through to plan_fileops).
        data: Pre-resolved data dict with keys ``final_mapping``,
            ``database``, ``user_config``.
        intent: Request intent (BACKUP/APPLY/RESTORE/RUN).
        flags: Request flags dict.
        on_progress: Optional progress callback.

    Returns:
        PipelineResult with execution outcome.
    """
    # Wrap data into CleanContext (interim — Phase D1 will remove CleanContext)
    context = CleanContext(
        final_mapping=data["final_mapping"],
        database=data["database"],
        user_config=data["user_config"],
    )

    # ── Plan ──────────────────────────────────────────────────────────
    plan = plan_fileops(request, context, on_progress=on_progress)

    # ── Preflight gate ────────────────────────────────────────────────
    _notify(on_progress, "prepare", 5, 6, "Running preflight checks...")
    if plan.preflight_ok is False:
        return PipelineResult(
            ok=False,
            errors=plan.preflight_manifest.get("errors", []),
            warnings=[],
            trees=[],
            final_mapping=[],
            mapping_result={},
            backup_result=(
                {
                    "ok": False,
                    "backed_up": [],
                    "skipped": [],
                    "errors": plan.preflight_manifest.get("errors", []),
                    "dry_run": plan.dry_run,
                }
                if intent == Intent.APPLY
                else None
            ),
            apply_result=(
                {
                    "ok": False,
                    "applied": [],
                    "skipped": [],
                    "errors": plan.preflight_manifest.get("errors", []),
                    "warnings": [],
                    "diagnostics": plan.preflight_manifest,
                    "dry_run": plan.dry_run,
                }
                if intent == Intent.APPLY
                else None
            ),
        )

    _notify(on_progress, "prepare", 6, 6, "Ready")

    # ── Build initial tree if needed (prep) ────────────────────────────
    if intent == Intent.BACKUP and plan.needs_tree_build and not plan.dry_run:
        for backup_dir in plan.backup_dirs:
            prep_backup_dir(backup_dir, plan.ignore_rules)

    # ── Execute primitive ─────────────────────────────────────────────
    if intent == Intent.BACKUP:
        return _execute_backup_plan(
            plan.entries_by_backup_dir,
            plan.backup_dirs,
            plan.dry_run,
            on_progress,
        )
    elif intent == Intent.APPLY:
        return _execute_apply_plan(
            plan.entries_by_backup_dir,
            plan.dry_run,
            plan.warnings,
            on_progress,
        )
    elif intent == Intent.RESTORE:
        return _execute_restore_plan(
            plan.entries_by_backup_dir,
            plan.backup_dirs,
            plan.dry_run,
            plan.force,
            on_progress,
        )
    elif intent == Intent.RUN:
        return _execute_run_plan(plan, context, request, on_progress)

    return PipelineResult(
        ok=False,
        errors=[f"E_BAD_INTENT: {intent}"],
        warnings=[],
        trees=[],
        final_mapping=[],
        mapping_result={},
    )


def _execute_backup_plan(
    entries_by_backup_dir: dict,
    backup_dirs: dict,
    dry_run: bool,
    on_progress: Any,
) -> PipelineResult:
    """Execute backup using run_differential_backup."""
    backed_up: list[dict] = []
    skipped: list[dict] = []
    errors: list[str] = []

    total_dirs = len(entries_by_backup_dir)
    _notify(on_progress, "backup", 0, max(total_dirs, 1), "Starting backup...")

    for i, (backup_dir, dir_entries) in enumerate(entries_by_backup_dir.items()):
        _notify(on_progress, "backup", i + 1, total_dirs, f"Backing up {backup_dir}")
        files_to_backup = backup_dirs.get(backup_dir, [])
        # Load existing tree or build initial tree
        tree: dict | None = None
        info = load_backup_info(backup_dir)
        tree = info.get("tree") if info else None
        dir_result = run_differential_backup(
            backup_dir,
            files_to_backup,
            dry_run=dry_run,
            on_progress=on_progress,
            tree=tree,
        )
        backed_up.extend(dir_result.get("backed_up", []))
        skipped.extend(dir_result.get("skipped", []))
        errors.extend(dir_result.get("errors", []))

    _notify(on_progress, "backup", total_dirs, total_dirs, "Backup complete")

    return PipelineResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=[],
        trees=[],
        final_mapping=[],
        mapping_result={},
        backup_result={
            "ok": len(errors) == 0,
            "backed_up": backed_up,
            "skipped": skipped,
            "errors": errors,
            "dry_run": dry_run,
        },
    )


def _execute_apply_plan(
    entries_by_backup_dir: dict,
    dry_run: bool,
    plan_warnings: list[str],
    on_progress: Any,
) -> PipelineResult:
    """Execute apply using apply_ops.apply_entries."""
    total = sum(len(v) for v in entries_by_backup_dir.values())
    _notify(on_progress, "apply", 0, max(total, 1), "Starting apply...")
    result = apply_entries(
        entries_by_backup_dir,
        dry_run=dry_run,
        on_progress=on_progress,
    )

    return PipelineResult(
        ok=result["ok"],
        errors=result["errors"],
        warnings=list(set(result["warnings"] + [])),
        trees=[],
        final_mapping=[],
        mapping_result={},
        apply_result=result,
    )


def _execute_restore_plan(
    entries_by_backup_dir: dict,
    backup_dirs: dict,
    dry_run: bool,
    force: bool,
    on_progress: Any,
) -> PipelineResult:
    """Execute restore using restore_ops.restore_entries."""
    total = sum(len(v) for v in entries_by_backup_dir.values())
    _notify(on_progress, "restore", 0, max(total, 1), "Starting restore...")

    # Pre-load backupinfos
    backupinfos: dict[str, dict] = {}
    try:
        for backup_dir in backup_dirs:
            try:
                backupinfos[backup_dir] = load_backup_info(backup_dir)
            except Exception:
                pass
    except ImportError:
        pass

    result = restore_entries(
        entries_by_backup_dir,
        backupinfos,
        force=force,
        dry_run=dry_run,
        on_progress=on_progress,
    )

    return PipelineResult(
        ok=result["ok"],
        errors=result["errors"],
        warnings=[],
        trees=[],
        final_mapping=[],
        mapping_result={},
        restore_result=result,
    )


def _execute_run_plan(
    plan: FileOpsPlan,
    context: CleanContext,
    request: Any,
    on_progress: Any,
) -> PipelineResult:
    """Execute full run: backup + apply (no preflight, by design)."""
    # Backup phase
    backup_result = _execute_backup_plan(
        plan.entries_by_backup_dir,
        plan.backup_dirs,
        plan.dry_run,
        on_progress,
    )
    if not backup_result.ok:
        return backup_result

    # Apply phase
    apply_result = _execute_apply_plan(
        plan.entries_by_backup_dir,
        plan.dry_run,
        plan.warnings,
        on_progress,
    )

    return PipelineResult(
        ok=apply_result.ok,
        errors=backup_result.errors + apply_result.errors,
        warnings=list(set(backup_result.warnings + apply_result.warnings)),
        trees=[],
        final_mapping=[],
        mapping_result={},
        backup_result=backup_result.backup_result,
        apply_result=apply_result.apply_result,
    )
