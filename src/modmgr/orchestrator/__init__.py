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
from .compute_pipeline import compute
from .data_port import DestDescriptor, SourceDescriptor, fetch, push
from .entry import Intent, TaskRequest
from .resolver import FilePathResolver, RawDictResolver, WorkspaceResolver
from .fileops import execute

# ── Unified dispatch ────────────────────────────────────────────────────


def dispatch(request: TaskRequest, *, on_progress=None) -> PipelineResult:
    """Unified orchestrator entry point.

    All callers (Web API routes, CLI) route through this single function.
    Flow: Resolver.resolve → DataPort.fetch → Engine/Planner → DataPort.push

    Args:
        request: Canonical TaskRequest from the Entry layer.
        on_progress: Optional ProgressCallback.

    Returns:
        PipelineResult with execution outcome.
    """
    # ── 1. Select resolver ──────────────────────────────────────────
    resolver = _select_resolver(request)

    # ── 2. Resolve → SourceDescriptor ───────────────────────────────
    if on_progress:
        on_progress("prepare", 0, 6, "Resolving context...")
    try:
        fetch_desc: SourceDescriptor = resolver.resolve(request)
    except Exception as exc:
        return PipelineResult(
            ok=False,
            errors=[f"E_RESOLVE_FAILED: {exc}"],
            warnings=[],
            trees=[],
            final_mapping=[],
            mapping_result={},
        )

    # ── 3. Fetch → clean dict ───────────────────────────────────────
    if on_progress:
        on_progress("prepare", 1, 6, "Reading data...")
    try:
        data = fetch(fetch_desc, request.intent)
    except Exception as exc:
        return PipelineResult(
            ok=False,
            errors=[f"E_FETCH_FAILED: {exc}"],
            warnings=[],
            trees=[],
            final_mapping=[],
            mapping_result={},
        )

    # ── 4. Dispatch by intent ───────────────────────────────────────
    if request.intent == Intent.COMPUTE_MAPPING:
        result_dict = compute(data, on_progress=on_progress)
        # Attach fingerprint source so DataPort.push() can compute hashes
        mapping_result = result_dict.get("mapping_result", {})
        if isinstance(mapping_result, dict):
            mapping_result["_fingerprint_inputs"] = {
                "aggregated_rule_set": data.get("aggregated_rule_set", {}),
                "database": data.get("database", {}),
            }
        result = PipelineResult(
            ok=not result_dict.get("errors"),
            errors=result_dict.get("errors", []),
            warnings=result_dict.get("warnings", []),
            trees=result_dict.get("trees", []),
            final_mapping=result_dict.get("final_mapping", []),
            mapping_result=mapping_result,
        )
    elif request.intent in (Intent.BACKUP, Intent.APPLY, Intent.RESTORE, Intent.RUN):
        result = execute(
            request, data, request.intent, request.flags,
            on_progress=on_progress,
        )
    else:
        return PipelineResult(
            ok=False,
            errors=[f"E_BAD_INTENT: unknown intent {request.intent}"],
            warnings=[],
            trees=[],
            final_mapping=[],
            mapping_result={},
        )

    # ── 5. Push (if output destination specified) ───────────────────
    if request.output_type != "none":
        dest_desc = DestDescriptor(
            output_type=request.output_type,
            workspace_id=request.output_args.get("workspace_id"),
            config_index=request.output_args.get("config_index", ""),
        )
        try:
            push(dest_desc, request.intent, result)
        except Exception:
            pass  # push failures are non-fatal

    return result


def _select_resolver(request: TaskRequest):
    """Select the appropriate resolver by request.resolver_type."""
    resolver_type = request.resolver_type
    if resolver_type == "workspace":
        return WorkspaceResolver()
    elif resolver_type == "file_paths":
        return FilePathResolver()
    elif resolver_type == "raw_dict":
        return RawDictResolver()
    else:
        raise ValueError(f"E_BAD_RESOLVER_TYPE: {resolver_type}")


__all__ = [
    "ProgressCallback",
    "PipelineResult",
    "dispatch",
    "Intent",
    "TaskRequest",
]
