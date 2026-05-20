"""Planner layer for file operations (backup / apply / restore / run).

Consumes a CleanContext and TaskRequest, derives operational parameters
(backup_dirs, ignore rules), decides whether preflight is needed, and
produces a FileOpsPlan ready for primitive execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..backup_dir_builder import build_backup_dirs
from ._common import _utcnow
from .entry import Intent, TaskRequest
from .preflight import run_apply_preflight, run_restore_preflight
from .resolver import CleanContext


@dataclass
class FileOpsPlan:
    """Execution plan produced by Planner, consumed by primitives.

    Every field is fully resolved; primitives execute without
    further derivation or decision-making.
    """
    intent: Intent
    backup_dirs: dict[str, list[str]] = field(default_factory=dict)
    entries_by_backup_dir: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    ignore_patterns: list[str] = field(default_factory=list)
    dry_run: bool = False
    force: bool = False
    preflight_ok: bool | None = None
    preflight_manifest: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)


def plan_fileops(request: TaskRequest, context: CleanContext) -> FileOpsPlan:
    """Derive a FileOpsPlan from request intent and clean context.

    Steps:
    1. Derive backup_dirs from final_mapping + database + user_config
    2. Collect ignore rules (backup intent only)
    3. Determine preflight requirement by intent
    4. Run preflight if required
    5. Assemble and return the plan
    """
    # ── 1. Derive backup dirs ────────────────────────────────────────
    backup_dirs, dir_warnings = build_backup_dirs(
        context.final_mapping,
        context.database,
        context.user_config,
    )
    warnings: list[str] = list(dir_warnings)

    # Group final_mapping entries by backup_dir
    entries_by_backup_dir: dict[str, list[dict[str, Any]]] = {}
    for entry in context.final_mapping:
        target_path = entry.get("path", "")
        for backup_dir in backup_dirs:
            if target_path in backup_dirs[backup_dir]:
                entries_by_backup_dir.setdefault(backup_dir, []).append(entry)
                break

    # ── 2. Ignore rules (backup only) ────────────────────────────────
    ignore_patterns: list[str] = []
    if request.intent == Intent.BACKUP:
        ignore_patterns = _collect_bakignore(context.user_config)

    # ── 3. Preflight decision ────────────────────────────────────────
    preflight_ok: bool | None = None
    preflight_manifest: dict[str, Any] | None = None

    needs_preflight = request.intent in (Intent.APPLY, Intent.RESTORE)

    if needs_preflight:
        if request.intent == Intent.APPLY:
            manifest = run_apply_preflight(backup_dirs, context)
        else:
            manifest = run_restore_preflight(backup_dirs, context)

        preflight_ok = manifest["ok"]
        preflight_manifest = manifest
        if not preflight_ok:
            warnings.append("W_PREFLIGHT_FAILED: preflight gate check failed")

    # ── 4. Assemble plan ─────────────────────────────────────────────
    return FileOpsPlan(
        intent=request.intent,
        backup_dirs=backup_dirs,
        entries_by_backup_dir=entries_by_backup_dir,
        ignore_patterns=ignore_patterns,
        dry_run=request.flags.get("dry_run", False),
        force=request.flags.get("force", False),
        preflight_ok=preflight_ok,
        preflight_manifest=preflight_manifest,
        warnings=warnings,
    )


def _collect_bakignore(user_config: dict[str, Any]) -> list[str]:
    """Collect bakignore patterns from user_config."""
    return list(user_config.get("bakignore", []))
