"""Adapters — convert orchestrator / bootstrap results into ApiResponse dicts.

All functions in this module produce plain dicts (not Pydantic models) so
they can be serialised directly via ``json.dumps`` inside SSE events.
"""

from __future__ import annotations

from typing import Any

from modmanager.orchestrator import PipelineResult


def adapt_pipeline_result(pr: PipelineResult) -> dict:
    """Convert a ``PipelineResult`` into an ``ApiResponse``-shaped dict."""
    data: dict[str, Any] = {
        "trees": pr.trees,
        "final_mapping": pr.final_mapping,
        "mapping_result": pr.mapping_result,
    }

    # ── Include backup_result fields when present ──────────────────────
    if pr.backup_result:
        data["backed_up"] = pr.backup_result.get("backed_up", [])
        data["backup_skipped"] = pr.backup_result.get("skipped", [])
        data["backup_errors"] = pr.backup_result.get("errors", [])
        if pr.backup_result.get("dry_run"):
            data["dry_run"] = True

    # ── Include apply_result fields when present ───────────────────────
    if pr.apply_result:
        data["applied"] = pr.apply_result.get("applied", [])
        data["apply_skipped"] = pr.apply_result.get("skipped", [])
        data["apply_errors"] = pr.apply_result.get("errors", [])
        data["apply_warnings"] = pr.apply_result.get("warnings", [])
        data["apply_diagnostics"] = pr.apply_result.get("diagnostics", {})
        if pr.apply_result.get("dry_run"):
            data["dry_run"] = True

    # ── Stats summary ──────────────────────────────────────────────────
    stats: dict[str, int] = {}
    if pr.backup_result:
        stats["backed_up"] = len(pr.backup_result.get("backed_up", []))
        stats["backup_skipped"] = len(pr.backup_result.get("skipped", []))
    if pr.apply_result:
        stats["applied"] = len(pr.apply_result.get("applied", []))
        stats["apply_skipped"] = len(pr.apply_result.get("skipped", []))
    if stats:
        data["stats"] = stats

    # ── Include restore_result fields when present ──────────────────────
    if pr.restore_result:
        data["restored"] = pr.restore_result.get("restored", [])
        data["skipped"] = pr.restore_result.get("skipped", [])
        if pr.restore_result.get("force"):
            data["force"] = True
        data["restore_errors"] = pr.restore_result.get("errors", [])

    if pr.backup_dir:
        data["backup_dir"] = pr.backup_dir

    return {
        "ok": pr.ok,
        "data": data,
        "errors": pr.errors,
        "warnings": pr.warnings,
    }


def adapt_backup_result(result: dict) -> dict:
    """Convert the dict returned by ``orchestrator.backup()`` into an
    ``ApiResponse``-shaped dict."""
    return {
        "ok": result.get("ok", False),
        "data": {
            "backed_up": result.get("backed_up", []),
            "skipped": result.get("skipped", []),
        },
        "errors": result.get("errors", []),
        "warnings": [],
    }


def adapt_apply_result(result: dict) -> dict:
    """Convert the dict returned by ``orchestrator.apply()`` into an
    ``ApiResponse``-shaped dict."""
    return {
        "ok": result.get("ok", False),
        "data": {
            "applied": result.get("applied", []),
            "skipped": result.get("skipped", []),
        },
        "errors": result.get("errors", []),
        "warnings": [],
    }


def adapt_dict_result(data: dict) -> dict:
    """适配 discover_user_config / generate_database 的返回。"""
    return {
        "ok": True,
        "data": data,
        "errors": data.get("errors", []),
        "warnings": data.get("warnings", []),
    }


def adapt_restore_result(result: dict) -> dict:
    """Convert the dict returned by ``restore_from_backup()`` into an
    ``ApiResponse``-shaped dict."""
    data: dict[str, Any] = {
        "restored": result.get("restored", []),
        "skipped": result.get("skipped", []),
        "orphans": result.get("orphans", []),
    }
    if result.get("dry_run"):
        data["dry_run"] = True
    return {
        "ok": result.get("ok", False),
        "data": data,
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
    }


def adapt_error(message: str) -> dict:
    """Build an ``ApiResponse``-shaped dict for an error condition."""
    return {
        "ok": False,
        "data": None,
        "errors": [message],
        "warnings": [],
    }
