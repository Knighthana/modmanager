"""prep.py — Backup directory initialization primitive.

Creates the backup_dir directory structure, scans the source directory
to build the initial tree, and writes backupinfo.json.  Called by the
Planner when a new backup_dir needs to be created.

Knows about ignore rules.  Does NOT copy files — that is backup's job.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from .paths import normalize_posix


def prep_backup_dir(
    backup_dir: str,
    ignore_rules: Any,
    *,
    on_progress: Any = None,
) -> dict[str, Any]:
    """Create backup_dir structure, build initial tree, write backupinfo.json.

    Args:
        backup_dir: Target backup directory path.
        ignore_rules: IgnoreRuleSet collected by the Planner.
        on_progress: Optional progress callback.

    Returns:
        Initial backupinfo dict.  Every FileNode in the tree has
        ``isbackuped=False``, ``hashtype="invalid"``, ``hashvalue="0"``.
    """
    source_root = str(Path(backup_dir).parent)

    # ── Create directory ────────────────────────────────────────────
    os.makedirs(backup_dir, exist_ok=True)

    # ── Build initial tree ──────────────────────────────────────────
    _notify(on_progress, "prep", 0, 1, "Building initial tree...")
    tree = _build_initial_tree(source_root, ignore_rules)
    _notify(on_progress, "prep", 1, 1, "Tree built")

    # ── Write backupinfo.json ───────────────────────────────────────
    info: dict[str, Any] = {
        "schema_namespace": "KMM_BackupInfo",
        "tree_created_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "last_modified_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "schema_version": "knighthana@0.1.0",
        "tree": tree,
    }
    _write_json(Path(backup_dir) / "backupinfo.json", info)
    return info


# ── Internal helpers ────────────────────────────────────────────────────


def _build_initial_tree(source_root: str, ignore_rules: Any) -> dict[str, Any]:
    """Recursively scan *source_root*, apply ignore_rules, build tree.

    Every FileNode: isbackuped=False, hashtype="invalid", hashvalue="0".
    """
    root = Path(source_root)

    def _scan(path: Path) -> dict[str, Any]:
        if path.is_file():
            # Check ignore
            if ignore_rules is not None:
                try:
                    from .orchestrator.ignore_rules import should_ignore
                    if should_ignore(str(path), ignore_rules):
                        return None
                except Exception:
                    pass
            return {
                "name": path.name,
                "type": "file",
                "isbackuped": False,
                "hashtype": "invalid",
                "hashvalue": "0",
            }

        children: list[dict[str, Any]] = []
        try:
            for child in sorted(path.iterdir()):
                if child.name == "backupinfo.json":
                    continue
                if child.name.endswith(".kmmbackup"):
                    continue
                node = _scan(child)
                if node is not None:
                    children.append(node)
        except PermissionError:
            pass
        return {"name": path.name, "type": "dir", "children": children}

    return _scan(root)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomic write of JSON data to *path*."""
    import json
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _notify(on_progress: Any, step: str, finished: int, total: int, message: str = "") -> None:
    if on_progress:
        on_progress(step, finished, total, message)
