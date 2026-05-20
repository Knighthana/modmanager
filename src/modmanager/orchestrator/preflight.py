"""Preflight module — gate checks for apply and restore.

Preflight is a Planner subordinate; it produces manifests that the
Planner uses to decide whether execution can proceed.

Design rule:
  - apply preflight: checks backup_dir existence and gate integrity
  - restore preflight: checks backup_dir existence only
  - backup and run do NOT require preflight
"""

from __future__ import annotations

from typing import Any

try:
    from modmanager.backup_ops import check_backup_gate
except ImportError:
    from ..backup_ops import check_backup_gate

from ._common import _utcnow
from .resolver import CleanContext


def run_apply_preflight(
    backup_dirs: dict[str, list[str]],
    context: CleanContext,
) -> dict[str, Any]:
    """Run apply preflight: check each backup_dir's gate.

    Returns a manifest with per-directory results.
    When manifest['ok'] is False, apply MUST NOT proceed.
    """
    errors: list[str] = []
    warnings: list[str] = []
    dir_results: list[dict[str, Any]] = []

    for backup_dir, entries in backup_dirs.items():
        gate_errors = check_backup_gate(backup_dir)
        gate_ok = len(gate_errors) == 0
        dir_results.append({
            "path": backup_dir,
            "gate_pass": gate_ok,
            "gate_errors": gate_errors,
            "applicable_entries": entries,
        })
        if not gate_ok:
            errors.extend(gate_errors)

    return {
        "ok": len(errors) == 0,
        "backup_dirs": dir_results,
        "errors": errors,
        "warnings": warnings,
        "timestamp": _utcnow(),
    }


def run_restore_preflight(
    backup_dirs: dict[str, list[str]],
    context: CleanContext,
) -> dict[str, Any]:
    """Run restore preflight: check each backup_dir exists on disk.

    Returns a manifest with per-directory existence results.
    When manifest['ok'] is False, restore MUST NOT proceed.
    """
    import os

    errors: list[str] = []
    dir_results: list[dict[str, Any]] = []

    for backup_dir, entries in backup_dirs.items():
        exists = os.path.isdir(backup_dir)
        gate_errors: list[str] = []
        if not exists:
            gate_errors.append(f"E_BACKUP_DIR_MISSING: {backup_dir}")
            errors.extend(gate_errors)

        dir_results.append({
            "path": backup_dir,
            "gate_pass": exists,
            "gate_errors": gate_errors,
            "applicable_entries": entries if exists else [],
        })

    return {
        "ok": len(errors) == 0,
        "backup_dirs": dir_results,
        "errors": errors,
        "warnings": [],
        "timestamp": _utcnow(),
    }
