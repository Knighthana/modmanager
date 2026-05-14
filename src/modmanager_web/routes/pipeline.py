"""Pipeline routes — compute / backup / apply / run / restore.

All endpoints return SSE streams with progress updates.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from modmanager.backup_dir_builder import build_backup_dir
from modmanager.backup_ops import restore_from_backup
from modmanager.bootstrap import discover_user_config
from modmanager.iojson import load_json_file
from modmanager.orchestrator import (
    compute as orch_compute,
    backup as orch_backup,
    apply as orch_apply,
    run as orch_run,
)

from ..adapters import adapt_pipeline_result, adapt_backup_result, adapt_apply_result, adapt_restore_result, adapt_dict_result, adapt_error
from ..schemas import ComputeRequest, BackupRequest, ApplyRequest, RunRequest, VisualizeRequest, RestoreRequest
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
        user_config = discover_user_config()
        db_path = _resolve_database_path(req.database_name, user_config)
        db = load_json_file(db_path)

        return orch_compute(
            database=db,
            aggregated_rule_set=req.aggregated_rule_set,
            action_orders=req.action_orders,
            branch_decisions=req.branch_decisions,
            managed_entries=req.managed_entries,
            on_progress=on_progress,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/backup")
async def pipeline_backup(req: BackupRequest):
    """Run differential backup for mapped files.

    SSE events:
      - ``progress`` — backup phase updates
      - ``result``   — backup result in ``ApiResponse`` format
      - ``error``    — exception information
    """

    # Resolve database and user_config from database_name
    user_config = discover_user_config()
    db_path = _resolve_database_path(req.database_name, user_config)
    database = load_json_file(db_path)

    resolved_backup_dir = req.backup_dir
    if resolved_backup_dir is None:
        final_mapping = req.mapping_result.get("final_mapping", [])
        if not final_mapping:
            return adapt_error("final_mapping is empty; cannot derive backup_dir")
        try:
            resolved_backup_dir = build_backup_dir(final_mapping, database, user_config)
        except ValueError as exc:
            return adapt_error(str(exc))

    def do_work(*, on_progress):
        return orch_backup(
            mapping_result=req.mapping_result,
            backup_dir=resolved_backup_dir,
            on_progress=on_progress,
        )

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
    from modmanager.forest_visual import visualize_payload

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


@router.post("/apply")
async def pipeline_apply(req: ApplyRequest):
    """Apply the final mapping to disk.

    SSE events:
      - ``progress`` — apply phase updates
      - ``result``   — apply result in ``ApiResponse`` format
      - ``error``    — exception information
    """

    # Resolve database and user_config from database_name
    user_config = discover_user_config()
    db_path = _resolve_database_path(req.database_name, user_config)
    database = load_json_file(db_path)

    resolved_backup_dir = req.backup_dir
    if resolved_backup_dir is None:
        if not req.final_mapping:
            return adapt_error("final_mapping is empty; cannot derive backup_dir")
        try:
            resolved_backup_dir = build_backup_dir(req.final_mapping, database, user_config)
        except ValueError as exc:
            return adapt_error(str(exc))

    def do_work(*, on_progress):
        return orch_apply(
            final_mapping=req.final_mapping,
            backup_dir=resolved_backup_dir,
            dry_run=req.dry_run,
            on_progress=on_progress,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


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
        user_config = discover_user_config()
        db_path = _resolve_database_path(req.database_name, user_config)
        db = load_json_file(db_path)

        return orch_run(
            database=db,
            aggregated_rule_set=req.aggregated_rule_set,
            backup_dir=req.backup_dir,
            action_orders=req.action_orders,
            branch_decisions=req.branch_decisions,
            managed_entries=req.managed_entries,
            dry_run=req.dry_run,
            on_progress=on_progress,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
