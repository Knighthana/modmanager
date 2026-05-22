"""Shared types and helpers for the orchestrator package."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from ..core.workspacemanager import WorkspaceManager
from ..iojson import load_json_file
from ..path_resolver import expand_path


# ── Progress callback protocol ────────────────────────────────────────


class ProgressCallback(Protocol):
    """Progress notification callback.

    Args:
        step: Stage identifier ("scan" | "aggregate" | "compute" | "backup" |
              "apply" | "restore").
        finished: Number of completed items.
        total: Total number of items (-1 means unknown).
        message: Optional description text.
    """

    def __call__(self, step: str, finished: int, total: int, message: str = "") -> None:
        ...


# ── Data structures ───────────────────────────────────────────────────


@dataclass
class PipelineResult:
    """Holds the result of a pipeline execution.

    Attributes:
        ok: Whether the pipeline completed without errors.
        errors: Accumulated error messages.
        warnings: Accumulated warning messages.
        trees: Mapping trees from ``compute_mapping``.
        final_mapping: Final resolved mapping list.
        mapping_result: Raw result dict from ``compute_mapping``.
        backup_result: Result dict from ``run_differential_backup`` (if run).
        apply_result: Result dict from ``apply_final_mapping`` (if run).
    """

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    trees: list[dict[str, Any]] = field(default_factory=list)
    final_mapping: list[dict[str, Any]] = field(default_factory=list)
    mapping_result: dict[str, Any] = field(default_factory=dict)
    backup_result: dict[str, Any] | None = None
    apply_result: dict[str, Any] | None = None
    restore_result: dict[str, Any] | None = None
    backup_dir: str | None = None


# ── Workspace helpers ─────────────────────────────────────────────────


def _get_workspace_manager(user_config: dict[str, Any] | None = None) -> WorkspaceManager:
    """Resolve workspace root directory from user_config or default.

    Default workspace directory (platform-specific):
      - Linux:   ``~/.cache/kmm/workspace/``
      - Windows: ``%LOCALAPPDATA%/kmm/workspace/``
      - macOS:   ``~/Library/Caches/kmm/workspace/``
    """
    cfg = user_config or {}
    ws_dir = cfg.get("workspace_dir") or _default_workspace_dir()
    return WorkspaceManager(expand_path(ws_dir))


def _default_workspace_dir() -> str:
    """Platform-default workspace root directory."""
    home = str(Path.home())
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", f"{home}/AppData/Local")
        return str(Path(local_appdata) / "kmm" / "workspace")
    elif sys.platform == "darwin":
        return str(Path(home) / "Library" / "Caches" / "kmm" / "workspace")
    else:
        return str(Path(home) / ".cache" / "kmm" / "workspace")


def _resolve_database(database_name: str, user_config: dict[str, Any]) -> dict[str, Any]:
    """Load a database dict from its name in user_config."""
    databases = user_config.get("databases", {})
    if database_name not in databases:
        raise ValueError(f"database '{database_name}' not found in user_config.databases")
    db_path = expand_path(databases[database_name]["path"])
    return load_json_file(db_path)


# ── Hashing / timestamp helpers ───────────────────────────────────────


def _sha256_dict(data: dict[str, Any]) -> str:
    """SHA256 hash of a dict (sorted keys, canonical JSON)."""
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _utcnow() -> str:
    """ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()
