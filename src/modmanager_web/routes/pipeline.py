"""Pipeline routes — compute / backup / apply / run.

All endpoints return SSE streams with progress updates.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from modmanager.backup_dir_builder import build_backup_dir
from modmanager.iojson import load_json_file
from modmanager.orchestrator import (
    compute as orch_compute,
    backup as orch_backup,
    apply as orch_apply,
    run as orch_run,
)

from ..adapters import adapt_pipeline_result, adapt_backup_result, adapt_apply_result, adapt_dict_result, adapt_error
from ..schemas import ComputeRequest, BackupRequest, ApplyRequest, RunRequest, VisualizeRequest
from ..sse import stream_with_progress

router = APIRouter()


@router.post("/compute")
async def pipeline_compute(req: ComputeRequest):
    """Aggregate rules and compute file mapping.

    SSE events:
      - ``progress`` — aggregate/compute phase updates
      - ``result``   — ``PipelineResult`` in ``ApiResponse`` format
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        return orch_compute(
            database=req.database,
            kmm_rule_paths=req.kmm_rule_paths,
            user_config_path=req.user_config_path,
            action_orders=req.action_orders,
            branch_decisions=req.branch_decisions,
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

    resolved_backup_dir = req.backup_dir
    if resolved_backup_dir is None:
        if not req.database or not req.user_config_path:
            return adapt_error("backup_dir is required when database/user_config_path are not provided")
        try:
            user_config = load_json_file(req.user_config_path)
        except Exception as exc:
            return adapt_error(f"failed to load user_config: {exc}")
        final_mapping = req.mapping_result.get("final_mapping", [])
        if not final_mapping:
            return adapt_error("final_mapping is empty; cannot derive backup_dir")
        try:
            resolved_backup_dir = build_backup_dir(final_mapping, req.database, user_config)
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

    resolved_backup_dir = req.backup_dir
    if resolved_backup_dir is None:
        if not req.database or not req.user_config_path:
            return adapt_error("backup_dir is required when database/user_config_path are not provided")
        try:
            user_config = load_json_file(req.user_config_path)
        except Exception as exc:
            return adapt_error(f"failed to load user_config: {exc}")
        if not req.final_mapping:
            return adapt_error("final_mapping is empty; cannot derive backup_dir")
        try:
            resolved_backup_dir = build_backup_dir(req.final_mapping, req.database, user_config)
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
        stream_with_progress(do_work, result_adapter=adapt_apply_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/run")
async def pipeline_run(req: RunRequest):
    """Execute the full pipeline: aggregate → compute → backup → apply.

    SSE events:
      - ``progress`` — phase updates for all four stages
      - ``result``   — combined ``PipelineResult`` in ``ApiResponse`` format
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        return orch_run(
            database=req.database,
            kmm_rule_paths=req.kmm_rule_paths,
            user_config_path=req.user_config_path,
            backup_dir=req.backup_dir,
            action_orders=req.action_orders,
            branch_decisions=req.branch_decisions,
            dry_run=req.dry_run,
            on_progress=on_progress,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
