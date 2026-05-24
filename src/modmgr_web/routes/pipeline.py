"""Pipeline routes — compute / visualize / run / restore.

All endpoints return SSE streams with progress updates.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from modmgr.backup_ops import restore_from_backup
from modmgr.bootstrap import discover_user_config
from modmgr.iojson import load_json_file
from modmgr.orchestrator import dispatch
from modmgr.orchestrator.entry import Intent, TaskRequest

from ..adapters import adapt_pipeline_result, adapt_restore_result, adapt_dict_result, adapt_error
from ..schemas import ComputeRequest, RunRequest, VisualizeRequest, RestoreRequest
from ..sse import stream_with_progress
from .database import _resolve_database_path

router = APIRouter()


@router.post("/compute")
async def pipeline_compute(req: ComputeRequest):
    """Compute file mapping from a pre-aggregated rule set dict.

    SSE events:
      - ``progress`` — compute phase updates
      - ``result``   -- ``PipelineResult`` in ``ApiResponse`` format
      - ``error``    -- exception information
    """

    # ── Pre-check: aggregated_rule_set is required ─────────────────────
    if not req.aggregated_rule_set:
        return adapt_error("E_NO_RULE_INPUT: aggregated_rule_set is required")

    def do_work(*, on_progress):
        # Resolve database from database_name
        user_config, _ = discover_user_config()
        db_path = _resolve_database_path(req.database_name, user_config)
        db = load_json_file(db_path)

        request = TaskRequest(
            identity="web",
            intent=Intent.COMPUTE_MAPPING,
            resolver_type="raw_dict",
            resolver_args={
                "database": db,
                "aggregated_rule_set": req.aggregated_rule_set,
                "action_orders": req.action_orders,
                "branch_decisions": req.branch_decisions,
                "managed_entries": req.managed_entries,
            },
        )
        return dispatch(request, on_progress=on_progress)

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/visualize")
async def pipeline_visualize(req: VisualizeRequest):
    """Convert trees JSON to SVG/ASCII/DOT visualization.

    Returns a plain JSON ``ApiResponse`` with the rendered output.
    """
    from modmgr.forest_visual import visualize_payload

    if not req.trees and req.mapping_result:
        # Fall back to extracting trees from mapping_result
        trees = req.mapping_result.get("trees", [])
    else:
        trees = req.trees

    try:
        rendered = visualize_payload(
            {"trees": trees},
            req.format,
            show_m1_details=req.show_m1_details,
        )
        return adapt_dict_result({"rendered": rendered, "format": req.format})
    except Exception as exc:
        return adapt_error(str(exc))


@router.post("/restore")
async def pipeline_restore(req: RestoreRequest):
    """Restore files from a backup directory to their original locations.

    This is the **inverse** of ``apply`` — it copies files from the backup
    back to their original paths.  It is implemented as a standalone endpoint
    (not coupled with ``apply``) per DESIGN_P4_GUI_GAP_CLOSURE.md §3.4.

    SSE events:
      - ``progress`` — per-file restore progress
      - ``result``   — restore result in ``ApiResponse`` format
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        return restore_from_backup(
            backup_dir=req.backup_dir,
            target_files=req.target_files,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_restore_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/run")
async def pipeline_run(req: RunRequest):
    """Execute the full pipeline: compute → backup → apply.

    SSE events:
      - ``progress`` — phase updates for all four stages
      - ``result``   — combined ``PipelineResult`` in ``ApiResponse`` format
      - ``error``    — exception information
    """

    # ── Pre-check: aggregated_rule_set is required ─────────────────────
    if not req.aggregated_rule_set:
        return adapt_error("E_NO_RULE_INPUT: aggregated_rule_set is required")

    def do_work(*, on_progress):
        # Resolve database from database_name
        user_config, _ = discover_user_config()
        db_path = _resolve_database_path(req.database_name, user_config)
        db = load_json_file(db_path)

        request = TaskRequest(
            identity="web",
            intent=Intent.RUN,
            resolver_type="raw_dict",
            resolver_args={
                "database": db,
                "aggregated_rule_set": req.aggregated_rule_set,
                "action_orders": req.action_orders,
                "branch_decisions": req.branch_decisions,
                "managed_entries": req.managed_entries,
                "user_config": user_config,
            },
            flags={"dry_run": req.dry_run},
        )
        return dispatch(request, on_progress=on_progress)

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
