"""Backups routes — ``POST /api/backups/list`` and ``POST /api/backups/inspect`` (read-only).

These endpoints browse backup *artefacts* already on disk.  The actual
backup *execution* belongs in ``/api/pipeline/backup``.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

from modmanager.backup_ops import load_backup_info, detect_dirty_state, inspect_conflict

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import BackupListRequest, BackupInspectRequest

router = APIRouter()

BACKUP_PREFIX = "kmmbackup_"


@router.post("/list")
async def backups_list(req: BackupListRequest):
    """List all ``kmmbackup_*`` sub-directories under *dir*.

    Returns an ``ApiResponse`` with ``{ backups: [{ name, path, file_count,
    created_at }] }``.
    """
    scan_dir = req.dir
    if not scan_dir:
        return adapt_error("dir is required")

    try:
        entries = os.listdir(scan_dir)
    except FileNotFoundError:
        return adapt_error(f"directory not found: {scan_dir}")
    except NotADirectoryError:
        return adapt_error(f"not a directory: {scan_dir}")
    except PermissionError:
        return adapt_error(f"permission denied: {scan_dir}")
    except OSError as exc:
        return adapt_error(f"cannot list directory: {scan_dir}: {exc}")

    backups: list[dict] = []
    for name in sorted(entries):
        if not name.startswith(BACKUP_PREFIX):
            continue
        full_path = str(Path(scan_dir) / name)
        try:
            st = os.stat(full_path)
            if not os.path.isdir(full_path):
                continue
            # Count files in the backup directory (excluding backupinfo.json)
            file_count = 0
            for root, dirs, files in os.walk(full_path):
                for f in files:
                    if f == "backupinfo.json":
                        continue
                    file_count += 1
            backups.append({
                "name": name,
                "path": full_path,
                "file_count": file_count,
                "created_at": st.st_ctime,
            })
        except OSError:
            continue

    return adapt_dict_result({"backups": backups})


@router.post("/inspect")
async def backups_inspect(req: BackupInspectRequest):
    """Inspect a specific backup directory for detailed status.

    Reuses ``load_backup_info``, ``detect_dirty_state``, and
    ``inspect_conflict`` from the backup_ops module.

    Returns an ``ApiResponse`` with ``{ path, file_count, files,
    dirty, conflicts }``.
    """
    backup_path = req.path
    if not backup_path:
        return adapt_error("path is required")

    p = Path(backup_path)
    if not p.exists():
        return adapt_error(f"backup directory not found: {backup_path}")
    if not p.is_dir():
        return adapt_error(f"not a directory: {backup_path}")

    try:
        # Load backup info
        info = load_backup_info(backup_path)
        tree = info.get("filefoldertree") if isinstance(info, dict) else None

        # Detect dirty state
        dirty_state = detect_dirty_state(backup_path)

        # Inspect conflicts (without final_mapping — just structural checks)
        conflict_result = inspect_conflict(backup_path)

        # Collect file listing from tree
        files: list[dict] = []

        def _collect(node: dict, prefix: str = "") -> None:
            name = str(node.get("name", ""))
            node_type = str(node.get("type", ""))
            current = f"{prefix}/{name}" if prefix and name else (name or prefix)
            if node_type == "file":
                rel = current.lstrip("/")
                files.append({
                    "relpath": rel,
                    "size": 0,  # not stored in tree metadata
                    "hash": str(node.get("hashvalue", "")),
                })
            for child in node.get("children", []):
                if isinstance(child, dict):
                    _collect(child, current)

        if isinstance(tree, dict):
            _collect(tree)

        # Count actual files on disk
        file_count = 0
        for root, dirs, fnames in os.walk(str(p)):
            for f in fnames:
                if f == "backupinfo.json":
                    continue
                file_count += 1

        return adapt_dict_result({
            "path": backup_path,
            "file_count": file_count,
            "files": files,
            "dirty": dirty_state,
            "conflicts": conflict_result,
        })
    except Exception as exc:
        return adapt_error(f"error inspecting backup: {exc}")
