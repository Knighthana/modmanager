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
from .ignore_rules import IgnoreRuleSet, collect_rules, should_ignore
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
    ignore_rules: IgnoreRuleSet = field(default_factory=IgnoreRuleSet)
    needs_tree_build: bool = False
    dry_run: bool = False
    force: bool = False
    preflight_ok: bool | None = None
    preflight_manifest: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)


def plan_fileops(
    request: TaskRequest,
    context: CleanContext,
    *,
    on_progress: Any = None,
) -> FileOpsPlan:
    """Derive a FileOpsPlan from request intent and clean context.

    Steps:
    1. Derive backup_dirs from final_mapping + database + user_config
    2. Group entries by backup_dir
    3. Collect ignore rules and filter
    4. Determine preflight requirement by intent
    5. Run preflight if required
    6. Assemble and return the plan
    """
    # ── 1. Derive backup dirs ────────────────────────────────────────
    _notify(on_progress, "prepare", 0, 4, "Deriving backup directories...")
    backup_dirs, dir_warnings = build_backup_dirs(
        context.final_mapping,
        context.database,
        context.user_config,
    )
    warnings: list[str] = list(dir_warnings)

    # Determine if any backup_dir needs initial tree build
    needs_tree_build = False
    if request.intent == Intent.BACKUP:
        for backup_dir in backup_dirs:
            try:
                from modmgr.backup_ops import load_backup_info as _lbi
                info = _lbi(backup_dir)
                tree = info.get("tree") if info else None
                if not tree or not tree.get("children"):
                    needs_tree_build = True
                    break
            except Exception:
                needs_tree_build = True
                break

    # Group final_mapping entries by backup_dir
    _notify(on_progress, "prepare", 1, 4, "Grouping entries by backup directory...")
    entries_by_backup_dir: dict[str, list[dict[str, Any]]] = {}
    for entry in context.final_mapping:
        target_path = entry.get("path", "")
        for backup_dir in backup_dirs:
            if target_path in backup_dirs[backup_dir]:
                entries_by_backup_dir.setdefault(backup_dir, []).append(entry)
                break

    # ── 2. Ignore rules (all intents) ────────────────────────────────
    _notify(on_progress, "prepare", 2, 4, "Collecting ignore rules...")
    ignore_rules = _collect_ignore_rules(context)

    # ── 3. Filter ignored entries ────────────────────────────────────
    _notify(on_progress, "prepare", 3, 4, "Filtering ignored entries...")
    filtered_count = 0
    for backup_dir in list(backup_dirs.keys()):
        before = len(backup_dirs[backup_dir])
        backup_dirs[backup_dir] = [
            p for p in backup_dirs[backup_dir]
            if not should_ignore(p, ignore_rules)
        ]
        filtered_count += before - len(backup_dirs[backup_dir])
    # Also filter entries_by_backup_dir
    for backup_dir in list(entries_by_backup_dir.keys()):
        entries_by_backup_dir[backup_dir] = [
            e for e in entries_by_backup_dir[backup_dir]
            if not should_ignore(e.get("path", ""), ignore_rules)
        ]
    if filtered_count:
        warnings.append(f"W_IGNORE_FILTERED: {filtered_count} entry(ies) excluded by ignore rules")

    # ── 4. Preflight decision ────────────────────────────────────────
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

    # ── 5. Assemble plan ─────────────────────────────────────────────
    return FileOpsPlan(
        intent=request.intent,
        backup_dirs=backup_dirs,
        entries_by_backup_dir=entries_by_backup_dir,
        ignore_rules=ignore_rules,
        needs_tree_build=needs_tree_build,
        dry_run=request.flags.get("dry_run", False),
        force=request.flags.get("force", False),
        preflight_ok=preflight_ok,
        preflight_manifest=preflight_manifest,
        warnings=warnings,
    )


def _collect_ignore_rules(context: CleanContext) -> IgnoreRuleSet:
    """Collect ignore rules from all three layers via ignore_rules module.

    Only scans directories that are ancestors of files in final_mapping,
    avoiding expensive full-tree walks of large game directories.
    """
    source_roots = _derive_source_roots(context)
    relevant_paths = [e.get("path", "") for e in context.final_mapping if e.get("path")]
    return collect_rules(context.user_config, source_roots, relevant_paths=relevant_paths)


def _derive_source_roots(context: CleanContext) -> list[str]:
    """Derive source root directories from database game entries."""
    roots: list[str] = []
    for game in context.database.get("game", []):
        bp = game.get("basepath", "")
        if bp:
            roots.append(bp)
    return roots


def _notify(on_progress: Any, step: str, finished: int, total: int, message: str = "") -> None:
    if on_progress:
        on_progress(step, finished, total, message)
