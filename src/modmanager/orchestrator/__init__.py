"""orchestrator.py — Unified pipeline orchestration for mod management.

Provides:
  - ``ProgressCallback`` protocol for progress reporting.
  - ``PipelineResult`` dataclass to hold pipeline execution results.
  - ``dispatch``  — unified entry point for all pipeline operations.
  - ``Intent``    — enum of supported intents.
  - ``TaskRequest`` — canonical request for the dispatch pipeline.
"""

from __future__ import annotations

from ._common import (
    PipelineResult,
    ProgressCallback,
    _get_workspace_manager,
    _resolve_database,
)
from .compute_pipeline import compute, compute_ws
from .entry import Intent, TaskRequest
from ..backup_ops import run_differential_backup

from ..apply_ops import apply_entries
from ..restore_ops import restore_entries
from .resolver import CleanContext, WorkspaceResolver, FilePathResolver, RawDictResolver
from .planner_fileops import plan_fileops

# ── Unified dispatch ────────────────────────────────────────────────────


def dispatch(request: TaskRequest, *, on_progress=None) -> PipelineResult:
    """Unified orchestrator entry point.

    All callers (Web API routes, CLI) route through this single function.
    The orchestrator inspects ``request.intent`` and delegates to the
    appropriate pipeline.

    Args:
        request: Canonical TaskRequest from the Entry layer.
        on_progress: Optional ProgressCallback.

    Returns:
        PipelineResult with execution outcome.
    """
    if request.intent == Intent.COMPUTE_MAPPING:
        return _dispatch_compute(request, on_progress)

    if request.intent in (Intent.BACKUP, Intent.APPLY, Intent.RESTORE, Intent.RUN):
        return _dispatch_fileops(request, on_progress)

    return PipelineResult(
        ok=False,
        errors=[f"E_BAD_INTENT: unknown intent {request.intent}"],
        warnings=[],
        trees=[],
        final_mapping=[],
        mapping_result={},
    )


def _dispatch_compute(request: TaskRequest, on_progress) -> PipelineResult:
    """Delegate compute intent to the compute pipeline.

    Extracts compute parameters from resolver_args and calls compute().
    """
    return compute(
        database=request.resolver_args.get("database", {}),
        aggregated_rule_set=request.resolver_args.get("aggregated_rule_set"),
        action_orders=request.resolver_args.get("action_orders"),
        branch_decisions=request.resolver_args.get("branch_decisions"),
        managed_entries=request.resolver_args.get("managed_entries"),
        on_progress=on_progress,
    )


def _dispatch_fileops(request: TaskRequest, on_progress) -> PipelineResult:
    """Full Resolver → Planner → Primitive pipeline for file operations."""
    _notify(on_progress, "prepare", 0, 1, "Resolving context...")
    # ── 1. Select resolver ─────────────────────────────────────────
    resolver_type = request.resolver_type
    if resolver_type == "workspace":
        resolver = WorkspaceResolver()
    elif resolver_type == "file_paths":
        resolver = FilePathResolver()
    elif resolver_type == "raw_dict":
        resolver = RawDictResolver()
    else:
        return PipelineResult(
            ok=False,
            errors=[f"E_BAD_RESOLVER_TYPE: {resolver_type}"],
            warnings=[],
            trees=[],
            final_mapping=[],
            mapping_result={},
        )

    # ── 2. Resolve → CleanContext ──────────────────────────────────
    try:
        context: CleanContext = resolver.resolve(request)
    except Exception as exc:
        return PipelineResult(
            ok=False,
            errors=[f"E_RESOLVE_FAILED: {exc}"],
            warnings=[],
            trees=[],
            final_mapping=[],
            mapping_result={},
        )

    # ── 3. Plan ────────────────────────────────────────────────────
    plan = plan_fileops(request, context)

    # ── 4. Preflight gate ──────────────────────────────────────────
    if plan.preflight_ok is False:
        return PipelineResult(
            ok=False,
            errors=plan.preflight_manifest.get("errors", []),
            warnings=plan.warnings,
            trees=[],
            final_mapping=context.final_mapping,
            mapping_result={},
            backup_result={
                "ok": False,
                "backed_up": [],
                "skipped": [],
                "errors": plan.preflight_manifest.get("errors", []),
                "dry_run": plan.dry_run,
            } if request.intent == Intent.APPLY else None,
            apply_result={
                "ok": False,
                "applied": [],
                "skipped": [],
                "errors": plan.preflight_manifest.get("errors", []),
                "warnings": plan.warnings,
                "diagnostics": plan.preflight_manifest,
                "dry_run": plan.dry_run,
            } if request.intent == Intent.APPLY else None,
        )

    # ── 5. Execute primitive ───────────────────────────────────────
    if request.intent == Intent.BACKUP:
        return _execute_backup_plan(plan, context, on_progress)
    elif request.intent == Intent.APPLY:
        return _execute_apply_plan(plan, context, on_progress)
    elif request.intent == Intent.RESTORE:
        return _execute_restore_plan(plan, context, on_progress)
    elif request.intent == Intent.RUN:
        return _execute_run_plan(plan, context, request, on_progress)

    return PipelineResult(
        ok=False,
        errors=[f"E_BAD_INTENT: {request.intent}"],
        warnings=plan.warnings,
        trees=[],
        final_mapping=context.final_mapping,
        mapping_result={},
    )


def _execute_backup_plan(plan, context, on_progress) -> PipelineResult:
    """Execute backup using plan.backup_dirs."""
    backed_up: list[dict] = []
    skipped: list[dict] = []
    errors: list[str] = []

    total_dirs = len(plan.entries_by_backup_dir)
    _notify(on_progress, "backup", 0, max(total_dirs, 1), "Starting backup...")

    for i, (backup_dir, dir_entries) in enumerate(plan.entries_by_backup_dir.items()):
        _notify(on_progress, "backup", i + 1, total_dirs, f"Backing up {backup_dir}")
        files_to_backup = plan.backup_dirs.get(backup_dir, [])
        dir_result = run_differential_backup(
            backup_dir,
            files_to_backup,
            dry_run=plan.dry_run,
            on_progress=on_progress,
        )
        backed_up.extend(dir_result.get("backed_up", []))
        skipped.extend(dir_result.get("skipped", []))
        errors.extend(dir_result.get("errors", []))

    _notify(on_progress, "backup", total_dirs, total_dirs, "Backup complete")

    return PipelineResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=plan.warnings,
        trees=[],
        final_mapping=context.final_mapping,
        mapping_result={},
        backup_result={
            "ok": len(errors) == 0,
            "backed_up": backed_up,
            "skipped": skipped,
            "errors": errors,
            "dry_run": plan.dry_run,
        },
    )


def _execute_apply_plan(plan, context, on_progress) -> PipelineResult:
    """Execute apply using apply_ops.apply_entries."""
    total = sum(len(v) for v in plan.entries_by_backup_dir.values())
    _notify(on_progress, "apply", 0, max(total, 1), "Starting apply...")
    result = apply_entries(
        plan.entries_by_backup_dir,
        dry_run=plan.dry_run,
        on_progress=on_progress,
    )

    return PipelineResult(
        ok=result["ok"],
        errors=result["errors"],
        warnings=list(set(result["warnings"] + plan.warnings)),
        trees=[],
        final_mapping=context.final_mapping,
        mapping_result={},
        apply_result=result,
    )


def _execute_restore_plan(plan, context, on_progress) -> PipelineResult:
    """Execute restore using restore_ops.restore_entries."""
    total = sum(len(v) for v in plan.entries_by_backup_dir.values())
    _notify(on_progress, "restore", 0, max(total, 1), "Starting restore...")

    # Pre-load backupinfos (Planner responsibility, but loaded here for now)
    backupinfos: dict[str, dict] = {}
    try:
        from ..backup_ops import load_backup_info
        for backup_dir in plan.backup_dirs:
            try:
                backupinfos[backup_dir] = load_backup_info(backup_dir)
            except Exception:
                pass
    except ImportError:
        pass

    result = restore_entries(
        plan.entries_by_backup_dir,
        backupinfos,
        force=plan.force,
        on_progress=on_progress,
    )

    return PipelineResult(
        ok=result["ok"],
        errors=result["errors"],
        warnings=plan.warnings,
        trees=[],
        final_mapping=context.final_mapping,
        mapping_result={},
        restore_result=result,
    )


def _execute_run_plan(plan, context, request, on_progress) -> PipelineResult:
    """Execute full run: backup + apply (no preflight, by design)."""
    # Backup phase
    backup_result = _execute_backup_plan(plan, context, on_progress)
    if not backup_result.ok:
        return backup_result

    # Apply phase
    apply_result = _execute_apply_plan(plan, context, on_progress)

    return PipelineResult(
        ok=apply_result.ok,
        errors=backup_result.errors + apply_result.errors,
        warnings=list(set(backup_result.warnings + apply_result.warnings)),
        trees=[],
        final_mapping=context.final_mapping,
        mapping_result={},
        backup_result=backup_result.backup_result,
        apply_result=apply_result.apply_result,
    )


def _notify(on_progress, step, finished, total, message=""):
    """Send progress if callback is set."""
    if on_progress:
        on_progress(step, finished, total, message)


__all__ = [
    "ProgressCallback",
    "PipelineResult",
    "dispatch",
    "Intent",
    "TaskRequest",
]
