"""orchestrator.py — Unified pipeline orchestration for mod management.

Provides:
  - ``ProgressCallback`` protocol for progress reporting.
  - ``PipelineResult`` dataclass to hold pipeline execution results.
  - ``dispatch``  — unified entry point for all pipeline operations.
  - ``Intent``    — enum of supported intents.
  - ``TaskRequest`` — canonical request for the dispatch pipeline.
"""

from __future__ import annotations

from ._common import PipelineResult, ProgressCallback
from .compute_pipeline import compute, compute_ws
from .entry import Intent, TaskRequest
from .resolver import CleanContext, WorkspaceResolver, FilePathResolver, RawDictResolver
from .fileops import execute

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
        # ── 1. Select resolver ──────────────────────────────────────
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

        # ── 2. Resolve → CleanContext ───────────────────────────────
        if on_progress:
            on_progress("prepare", 0, 6, "Resolving context...")
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

        # ── 3. Build data dict → fileops.execute ────────────────────
        data = {
            "database": context.database,
            "user_config": context.user_config,
            "final_mapping": context.final_mapping,
        }
        return execute(
            request, data, request.intent, request.flags,
            on_progress=on_progress,
        )

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



__all__ = [
    "ProgressCallback",
    "PipelineResult",
    "dispatch",
    "Intent",
    "TaskRequest",
]
