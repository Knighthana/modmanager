"""Rules routes — ``POST /api/rules/scan`` and ``POST /api/rules/read`` (read-only).

Both endpoints operate on the local file system and return simple JSON
responses wrapped in the standard ``ApiResponse`` envelope.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import RulesScanRequest, RulesReadRequest

router = APIRouter()


@router.post("/scan")
async def rules_scan(req: RulesScanRequest):
    """List ``.json`` files in *dir* (non-recursive).

    Returns an ``ApiResponse`` with ``{ files: [{ name, path, size }] }``.
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
    file_path = req.path
    if not file_path:
        return adapt_error("path is required")

    p = Path(file_path)
    if not p.exists():
        return adapt_error(f"file not found: {file_path}")
    if not p.is_file():
        return adapt_error(f"not a file: {file_path}")

    try:
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
