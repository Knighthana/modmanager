"""apply_ops.py — Pure apply primitive.

Executes file-to-file apply operations according to a pre-computed plan.
Does NOT derive backup_dirs, does NOT handle directories, does NOT make decisions.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable

# ── Public API ──────────────────────────────────────────────────────────


def apply_entries(
    entries_by_backup_dir: dict[str, list[dict[str, Any]]],
    *,
    dry_run: bool = False,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Execute file-to-file apply.

    Args:
        entries_by_backup_dir: {backup_dir_path: [{path, request}, ...]}
        dry_run: If True, simulate without modifying files.
        on_progress: Optional progress callback.

    Returns:
        dict with keys: ok, applied, skipped, errors, warnings, diagnostics, dry_run
    """
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    diagnostics: dict[str, Any] = {}

    total = sum(len(v) for v in entries_by_backup_dir.values())
    finished = 0

    for backup_dir, entries in entries_by_backup_dir.items():
        _notify(on_progress, "apply", finished, total, f"Applying in {backup_dir}")

        for entry in entries:
            target_path = entry["path"]
            request = entry.get("request")

            if request is None:
                skipped.append({"path": target_path, "reason": "no source (vacuous node)"})
                finished += 1
                continue

            action = request["action"]
            source_path = request["path"]

            # ── File-to-file guard ─────────────────────────────────
            if not _is_file_path(target_path):
                errors.append(f"E_APPLY_NOT_FILE: target path is not a file: {target_path}")
                finished += 1
                continue

            try:
                if action == "delete":
                    if not dry_run:
                        _assert_is_file(target_path, action)
                        os.remove(target_path)
                    applied.append({
                        "action": "delete",
                        "target": target_path,
                        "size": 0,
                        "mtime": 0,
                        "is_dir": False,
                    })

                elif action in ("replace", "create"):
                    if not source_path or source_path == "!":
                        errors.append(f"E_APPLY_MISSING_SOURCE: no source for {action} on {target_path}")
                        finished += 1
                        continue

                    if not dry_run:
                        _assert_is_file(source_path, action)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.copy2(source_path, target_path)

                    st = os.stat(source_path) if os.path.exists(source_path) else None
                    applied.append({
                        "action": action,
                        "source": source_path,
                        "target": target_path,
                        "size": st.st_size if st else 0,
                        "mtime": st.st_mtime if st else 0,
                        "is_dir": False,
                    })

                else:
                    skipped.append({"path": target_path, "action": action, "reason": "unknown action"})

            except FileNotFoundError as exc:
                errors.append(f"E_APPLY_MISSING_SOURCE: {source_path}: {exc}")
            except PermissionError as exc:
                errors.append(f"E_APPLY_PERMISSION: {target_path}: {exc}")
            except OSError as exc:
                errors.append(f"E_APPLY_FAILED: {target_path}: {exc}")

            finished += 1
            _notify(on_progress, "apply", finished, total)

    if not applied and not errors:
        warnings.append("W_APPLY_NO_EFFECT: no entries were applied")

    return {
        "ok": len(errors) == 0,
        "applied": applied,
        "skipped": skipped,
        "errors": errors,
        "warnings": warnings,
        "diagnostics": diagnostics,
        "dry_run": dry_run,
    }


# ── Internal helpers ────────────────────────────────────────────────────


def _is_file_path(path: str) -> bool:
    """True if path does NOT end with '/' (file semantics)."""
    return not path.endswith("/")


def _assert_is_file(path: str, action: str) -> None:
    """Raise if path is a directory (apply is file-to-file only)."""
    if os.path.isdir(path):
        raise IsADirectoryError(f"E_APPLY_DIRECTORY_NOT_ALLOWED: {action} target is a directory: {path}")


def _notify(
    on_progress: Callable[..., None] | None,
    step: str,
    finished: int,
    total: int,
    message: str = "",
) -> None:
    if on_progress:
        on_progress(step, finished, total, message)
