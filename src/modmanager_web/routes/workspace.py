"""Workspace routes — status / save-inputs / save-decisions / save-results.

All endpoints wrap workspace.json operations with the standard ``ApiResponse``
envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from modmanager.workspace import load_workspace, merge_workspace

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import SaveDecisionsRequest, SaveInputsRequest, SaveResultsRequest

router = APIRouter()


@router.get("/status")
async def workspace_status():
    """Return the full workspace.json content.

    Returns an ``ApiResponse`` with the complete workspace dict.
    """
    try:
        workspace = load_workspace()
        return adapt_dict_result(workspace)
    except Exception as exc:
        return adapt_error(str(exc))


@router.post("/save-inputs")
async def workspace_save_inputs(req: SaveInputsRequest):
    """Merge provided fields into the ``inputs`` section of workspace.json.

    Accepts optional workspace input fields. Only provided keys are updated;
    existing keys are preserved unchanged.
    """
    try:
        data = {}
        for field in (
            "database_path",
            "rule_paths",
            "aggregated_rule_path",
            "user_config_path",
            "discovery_mode",
            "discovery_manual_paths",
        ):
            val = getattr(req, field, None)
            if val is not None:
                data[field] = val

        workspace = merge_workspace(data, "inputs")
        return adapt_dict_result(workspace)
    except Exception as exc:
        return adapt_error(str(exc))


@router.post("/save-decisions")
async def workspace_save_decisions(req: SaveDecisionsRequest):
    """Merge branch_decisions into the ``decisions`` section of workspace.json.

    Accepts ``{ branch_decisions: { ... } }`` — replaces the entire
    branch_decisions dict.
    """
    try:
        data = {}
        if req.branch_decisions is not None:
            data["branch_decisions"] = req.branch_decisions

        workspace = merge_workspace(data, "decisions")
        return adapt_dict_result(workspace)
    except Exception as exc:
        return adapt_error(str(exc))


@router.post("/save-results")
async def workspace_save_results(req: SaveResultsRequest):
    """Merge computation results into the ``results`` section of workspace.json.

    Only provided fields are merged into ``results.last_compute``.
    """
    try:
        data = {}
        last_compute = {}
        for field in (
            "trees_count",
            "mapping_count",
            "warnings",
            "errors",
            "stats",
            "inputs_hash",
        ):
            val = getattr(req, field, None)
            if val is not None:
                last_compute[field] = val

        if last_compute:
            data["last_compute"] = last_compute

        workspace = merge_workspace(data, "results")
        return adapt_dict_result(workspace)
    except Exception as exc:
        return adapt_error(str(exc))
