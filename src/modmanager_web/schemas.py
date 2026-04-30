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


# ── Database endpoints ────────────────────────────────────────────────────


class GenerateDatabaseRequest(BaseModel):
    """Request body for ``POST /api/database/generate``."""

    mode: str = "auto"  # "auto" | "manual"
    paths: list[str] | None = None
    working_pathstyle: str = "linux"
    greedy_parsing: bool = False
    cache_path: str | None = None


# ── Pipeline endpoints ────────────────────────────────────────────────────


class ComputeRequest(BaseModel):
    """Request body for ``POST /api/pipeline/compute``."""

    database: dict[str, Any]
    kmm_rule_paths: list[str]
    user_config_path: str
    action_orders: dict[str, int] | None = None
    branch_decisions: dict[str, str] | None = None


class BackupRequest(BaseModel):
    """Request body for ``POST /api/pipeline/backup``."""

    mapping_result: dict[str, Any]
    backup_dir: str


class ApplyRequest(BaseModel):
    """Request body for ``POST /api/pipeline/apply``."""

    final_mapping: list[dict[str, Any]]
    backup_dir: str
    dry_run: bool = False


class RunRequest(BaseModel):
    """Request body for ``POST /api/pipeline/run``."""

    database: dict[str, Any]
    kmm_rule_paths: list[str]
    user_config_path: str
    backup_dir: str
    action_orders: dict[str, int] | None = None
    branch_decisions: dict[str, str] | None = None
    dry_run: bool = False
