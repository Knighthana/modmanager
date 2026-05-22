"""Workspace routes — create, delete, list, decisions, forest, pipeline.

Design doc: ``repo_memo/DESIGN_WORKSPACE_MODEL.md``
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response, StreamingResponse
from hana_modmgr.bootstrap import discover_user_config
from hana_modmgr.core.workspacemanager import WorkspaceManager
from hana_modmgr.orchestrator import dispatch, compute_ws
from hana_modmgr.orchestrator.entry import Intent, TaskRequest
from hana_modmgr.path_resolver import expand_path

from ..adapters import adapt_dict_result, adapt_error, adapt_pipeline_result
from ..schemas import CreateWorkspaceRequest, SaveDecisionsRequest, RulesAggregateRequest, WorkspaceApplyRequest, WorkspaceBackupRequest, WorkspaceRestoreRequest
from ..sse import stream_with_progress
from hana_modmgr.rule_aggregator import aggregate as rule_aggregate
import hashlib
import json
from datetime import datetime, timezone

router = APIRouter()


# ── Helper ────────────────────────────────────────────────────────────────────


def _get_workspace_manager() -> WorkspaceManager:
    """Resolve the workspace root directory from user_config and return a ``WorkspaceManager``."""
    config = discover_user_config()
    ws_dir = config.get("workspace_dir") or _default_workspace_dir()
    return WorkspaceManager(expand_path(ws_dir))


def _default_workspace_dir() -> str:
    """Platform-appropriate default workspace directory."""
    home = Path.home()
    return str(home / ".cache" / "kmm" / "workspace")


# ── Workspace CRUD ─────────────────────────────────────────────────────────────


@router.post("/create")
async def create_workspace(req: CreateWorkspaceRequest):
    """Create a new workspace, binding it to *database_name*."""
    try:
        wm = _get_workspace_manager()
        workspace_id = wm.create(name=req.name, database_name=req.database_name)
        meta = wm.read_meta(workspace_id)
        return adapt_dict_result({"workspace_id": workspace_id, "meta": meta})
    except Exception as exc:
        return adapt_error(str(exc))


@router.post("/{workspace_id}/delete")
async def delete_workspace(workspace_id: str):
    """Delete a workspace and all its contents."""
    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")
        wm.delete(workspace_id)
        return adapt_dict_result({"deleted": workspace_id})
    except Exception as exc:
        return adapt_error(str(exc))


@router.get("/list")
async def list_workspaces():
    """List all workspaces, most recently updated first."""
    try:
        wm = _get_workspace_manager()
        items = wm.list_all()
        return adapt_dict_result({"workspaces": items})
    except Exception as exc:
        return adapt_error(str(exc))


@router.get("/{workspace_id}/meta")
async def get_workspace_meta(workspace_id: str):
    """Return metadata for a single workspace."""
    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")
        meta = wm.read_meta(workspace_id)
        return adapt_dict_result(meta)
    except Exception as exc:
        return adapt_error(str(exc))


# ── Decisions ──────────────────────────────────────────────────────────────────


@router.post("/{workspace_id}/decisions/save")
async def save_decisions(workspace_id: str, req: SaveDecisionsRequest):
    """Persist user decisions into the workspace."""
    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")
        decisions = {
            "schema_namespace": "KMM_WorkspaceDecisions",
            "schema_version": "knighthana@0.1.0",
            "managed_entries": req.managed_entries or {},
            "branch_decisions": req.branch_decisions or {},
        }
        wm.write_decisions(workspace_id, decisions)
        return adapt_dict_result({"saved": True})
    except Exception as exc:
        return adapt_error(str(exc))


@router.get("/{workspace_id}/decisions/load")
async def load_decisions(workspace_id: str):
    """Read user decisions from the workspace."""
    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")
        if not wm.has_decisions(workspace_id):
            return adapt_dict_result(
                {"managed_entries": {}, "branch_decisions": {}}
            )
        decisions = wm.read_decisions(workspace_id)
        return adapt_dict_result(decisions)
    except Exception as exc:
        return adapt_error(str(exc))


# ── Forest ─────────────────────────────────────────────────────────────────────


@router.get("/{workspace_id}/forest/svg")
async def get_forest_svg(workspace_id: str):
    """Return the cached forest SVG for the workspace."""
    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")
        if not wm.has_svg(workspace_id):
            return adapt_error("SVG not yet computed for this workspace")
        svg_content = wm.read_svg(workspace_id)
        return Response(content=svg_content, media_type="image/svg+xml")
    except Exception as exc:
        return adapt_error(str(exc))


@router.get("/{workspace_id}/forest/mapping")
async def get_forest_mapping(workspace_id: str):
    """Return the mapping result for the workspace."""
    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")
        if not wm.has_mapping(workspace_id):
            return adapt_error("mapping not yet computed for this workspace")
        mapping = wm.read_mapping(workspace_id)
        return adapt_dict_result(mapping)
    except Exception as exc:
        return adapt_error(str(exc))


# ── Rules (workspace-aware) ─────────────────────────────────────────────────


@router.post("/{workspace_id}/rules/aggregate")
async def workspace_aggregate_rules(workspace_id: str, req: RulesAggregateRequest):
    """Aggregate rules and store the result in the workspace."""

    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")

        if not req.paths:
            return adapt_error("paths list is required and must not be empty")

        result, errors, warnings = rule_aggregate(
            [expand_path(p) for p in req.paths],
            output_path=None,  # Don't write to external file
        )

        if errors:
            return {"ok": False, "data": None, "errors": errors, "warnings": warnings}

        # Write the aggregated rule set into the workspace
        wm.write_aggregated_rule(workspace_id, result)

        aggregated_hash = hashlib.sha256(
            json.dumps(result, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        return {
            "ok": True,
            "data": {
                **result,
                "aggregated_hash": aggregated_hash,
                "aggregated_at": datetime.now(timezone.utc).isoformat(),
            },
            "errors": [],
            "warnings": warnings,
        }
    except Exception as exc:
        return adapt_error(str(exc))


@router.get("/{workspace_id}/rules/aggregated")
async def workspace_read_aggregated(workspace_id: str):
    """Read the aggregated rule set from the workspace."""
    try:
        wm = _get_workspace_manager()
        if not wm.exists(workspace_id):
            return adapt_error(f"workspace '{workspace_id}' not found")
        if not wm.has_aggregated_rule(workspace_id):
            return adapt_error("no aggregated rule set in workspace")
        rule_set = wm.read_aggregated_rule(workspace_id)
        return adapt_dict_result(rule_set)
    except Exception as exc:
        return adapt_error(str(exc))


# ── Pipeline (workspace-aware) ───────────────────────────────────────────────


@router.post("/{workspace_id}/pipeline/compute")
async def workspace_compute(workspace_id: str):
    """Compute mapping inside a workspace context.

    Reads aggregated rules and decisions from the workspace directory,
    resolves the bound database, and computes.  Results (mapping, SVG,
    fingerprints) are written back to the workspace.

    SSE events:
      - ``progress`` — compute phase updates
      - ``result``   — ``PipelineResult`` in ``ApiResponse`` format
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        return compute_ws(
            workspace_id=workspace_id,
            on_progress=on_progress,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{workspace_id}/pipeline/run")
async def workspace_run(workspace_id: str):
    """Execute the full pipeline inside a workspace context.

    SSE events:
      - ``progress`` — phase updates for all stages
      - ``result``   — combined ``PipelineResult``
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        request = TaskRequest(
            identity="web",
            intent=Intent.RUN,
            resolver_type="workspace",
            resolver_args={"workspace_id": workspace_id},
            flags={"dry_run": False},
        )
        return dispatch(request, on_progress=on_progress)

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── Pipeline: backup / apply / restore (workspace-aware) ────────────────────


@router.post("/{workspace_id}/pipeline/backup")
async def workspace_backup(workspace_id: str, req: WorkspaceBackupRequest):
    """Run differential backup in workspace context.

    Reads mapping from the workspace, auto-derives backup_dir, and
    streams progress via SSE.

    SSE events:
      - ``progress`` — backup phase updates
      - ``result``   — backup result in ``ApiResponse`` format
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        dry_run = req.dry_run if hasattr(req, 'dry_run') else False
        request = TaskRequest(
            identity="web",
            intent=Intent.BACKUP,
            resolver_type="workspace",
            resolver_args={"workspace_id": workspace_id},
            flags={"dry_run": dry_run},
        )
        return dispatch(request, on_progress=on_progress)

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{workspace_id}/pipeline/apply")
async def workspace_apply(workspace_id: str, req: WorkspaceApplyRequest):
    """Apply final mapping to disk in workspace context.

    Reads mapping and stored backup_dir from the workspace, streams
    progress via SSE.

    SSE events:
      - ``progress`` — apply phase updates
      - ``result``   — apply result in ``ApiResponse`` format
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        dry_run = req.dry_run if hasattr(req, 'dry_run') else False
        request = TaskRequest(
            identity="web",
            intent=Intent.APPLY,
            resolver_type="workspace",
            resolver_args={"workspace_id": workspace_id},
            flags={"dry_run": dry_run},
        )
        return dispatch(request, on_progress=on_progress)

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{workspace_id}/pipeline/restore")
async def workspace_restore(workspace_id: str, req: WorkspaceRestoreRequest):
    """Restore files from backup in workspace context.

    Delegates to ``restore_ws()`` which loads workspace context and
    delegates to the ``restore()`` engine function.

    SSE events:
      - ``progress`` — per-file restore progress
      - ``result``   — restore result in ``ApiResponse`` format
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        force = req.force if hasattr(req, 'force') else False
        dry_run = req.dry_run if hasattr(req, 'dry_run') else False
        request = TaskRequest(
            identity="web",
            intent=Intent.RESTORE,
            resolver_type="workspace",
            resolver_args={"workspace_id": workspace_id},
            flags={"force": force, "dry_run": dry_run},
        )
        return dispatch(request, on_progress=on_progress)

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_pipeline_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
