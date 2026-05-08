"""Rules routes — ``POST /api/rules/scan`` and ``POST /api/rules/read`` (read-only).

Both endpoints operate on the local file system and return simple JSON
responses wrapped in the standard ``ApiResponse`` envelope.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

from modmanager.path_resolver import resolve_directory_path, resolve_file_path

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import RulesScanRequest, RulesReadRequest

router = APIRouter()


@router.post("/scan")
async def rules_scan(req: RulesScanRequest):
    """List ``.json`` files in *dir* (non-recursive).

    Returns an ``ApiResponse`` with ``{ files: [{ name, path, size }] }``.
    """
    if not req.dir:
        return adapt_error("dir is required")

    try:
        scan_dir = resolve_directory_path(req.dir, Path(req.dir.rstrip("/")).name)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        return adapt_error(str(exc))

    try:
        entries = os.listdir(scan_dir)
    except PermissionError:
        return adapt_error(f"permission denied: {scan_dir}")
    except OSError as exc:
        return adapt_error(f"cannot list directory: {scan_dir}: {exc}")

    files: list[dict] = []
    for name in sorted(entries):
        if not name.endswith(".json"):
            continue
        full_path = str(Path(scan_dir) / name)
        try:
            st = os.stat(full_path)
            files.append({
                "name": name,
                "path": full_path,
                "size": st.st_size,
            })
        except OSError:
            # Skip files we cannot stat (permission, broken symlink, etc.)
            continue

    return adapt_dict_result({"files": files})


@router.post("/read")
async def rules_read(req: RulesReadRequest):
    """Read the raw text content of a file at *path*.

    Returns an ``ApiResponse`` with ``{ content, name, path, size }``.
    Returns ``ok: false`` if the file does not exist or cannot be read.
    """
    if not req.path:
        return adapt_error("path is required")

    try:
        file_path = resolve_file_path(req.path, Path(req.path).name)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        return adapt_error(str(exc))

    try:
        p = Path(file_path)
        content = p.read_text(encoding="utf-8")
        st = p.stat()
        return adapt_dict_result({
            "content": content,
            "name": p.name,
            "path": str(p),
            "size": st.st_size,
        })
    except (OSError, UnicodeDecodeError) as exc:
        return adapt_error(f"cannot read file: {file_path}: {exc}")
