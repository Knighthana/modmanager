"""Pydantic request/response models for the Web API.

All models follow the design in DESIGN_PHASE2_WEB_API.md §6.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Generic response wrapper ──────────────────────────────────────────────


class ApiResponse(BaseModel):
    """Standard API response envelope for non-SSE endpoints."""

    ok: bool
    data: dict[str, Any] | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Config endpoints ──────────────────────────────────────────────────────


class DiscoverUserConfigRequest(BaseModel):
    """Request body for ``POST /api/config/discover``."""

    home_dir: str | None = None


class SaveConfigRequest(BaseModel):
    """Request body for ``POST /api/config/save``."""

    config: dict[str, Any]


# ── Database endpoints ────────────────────────────────────────────────────


class ReadDatabaseRequest(BaseModel):
    """Request body for ``POST /api/database/read``."""

    database_name: str = "default"


class GenerateDatabaseRequest(BaseModel):
    """Request body for ``POST /api/database/generate``."""

    mode: str = "auto"  # "auto" | "manual"
    paths: list[str] | None = None
    greedy_parsing: bool = False
    database_name: str = "default"


class SaveDatabaseRequest(BaseModel):
    """Request body for ``POST /api/database/save``.

    Receives the full database dict (without managed fields)
    and writes to the path from user_config.databases[database_name].
    """

    database: dict[str, Any]
    database_name: str = "default"


# ── Pipeline endpoints ────────────────────────────────────────────────────


class ComputeRequest(BaseModel):
    """Request body for ``POST /api/pipeline/compute``."""

    database_name: str = "default"
    aggregated_rule_set: dict | None = None
    action_orders: dict[str, int] | None = None
    branch_decisions: dict[str, str] | None = None
    managed_entries: dict | None = None


class BackupRequest(BaseModel):
    """Request body for ``POST /api/pipeline/backup``."""

    mapping_result: dict[str, Any]
    backup_dir: str | None = None
    database_name: str = "default"


class ApplyRequest(BaseModel):
    """Request body for ``POST /api/pipeline/apply``."""

    final_mapping: list[dict[str, Any]]
    backup_dir: str | None = None
    database_name: str = "default"
    dry_run: bool = False


class RunRequest(BaseModel):
    """Request body for ``POST /api/pipeline/run``."""

    database_name: str = "default"
    aggregated_rule_set: dict | None = None
    backup_dir: str | None = None
    action_orders: dict[str, int] | None = None
    branch_decisions: dict[str, str] | None = None
    managed_entries: dict | None = None
    dry_run: bool = False


class VisualizeRequest(BaseModel):
    """Request body for ``POST /api/pipeline/visualize``."""

    trees: list[dict[str, Any]] = Field(default_factory=list)
    mapping_result: dict[str, Any] | None = None
    format: str = "svg"
    show_m1_details: bool = True


# ── Rules endpoints ────────────────────────────────────────────────────────


class RulesScanRequest(BaseModel):
    """Request body for ``POST /api/rules/scan``."""

    dir: str


class RulesReadRequest(BaseModel):
    """Request body for ``POST /api/rules/read``."""

    path: str


class RulesAggregateRequest(BaseModel):
    """Request body for ``POST /api/rules/aggregate``."""

    paths: list[str]


class RulesAffectedEntriesRequest(BaseModel):
    """Request body for ``POST /api/rules/affected-entries``."""

    aggregated_rule_path: str = ""
    aggregated_rule_set: dict | None = None
    database_name: str = "default"


# ── Backups endpoints ─────────────────────────────────────────────────────


class BackupListRequest(BaseModel):
    """Request body for ``POST /api/backups/list``."""

    dir: str


class BackupInspectRequest(BaseModel):
    """Request body for ``POST /api/backups/inspect``."""

    path: str


class RestoreRequest(BaseModel):
    """Request body for ``POST /api/pipeline/restore``."""

    backup_dir: str
    target_files: list[str] | None = None
