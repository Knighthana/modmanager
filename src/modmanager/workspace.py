"""workspace.py — Read, write, merge workspace.json with atomic semantics.

The workspace file stores user branch decisions and last computation results
for the current session.  It lives at a platform-specific default path:

  - Linux:   ``~/.local/share/kmm/workspace.json``
  - Windows: ``%localappdata%/kmm/workspace.json``

Public API
----------
- ``get_workspace_path()``        — platform-default workspace path
- ``load_workspace(path=None)``   — read or create default
- ``save_workspace(data, path)``  — atomic write (tmp + replace)
- ``merge_workspace(data, section, path)`` — read → merge section → write → return
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "DEFAULT_WORKSPACE",
    "get_workspace_path",
    "load_workspace",
    "save_workspace",
    "merge_workspace",
]

# ── Default workspace structure ───────────────────────────────────────────────

DEFAULT_WORKSPACE: dict[str, Any] = {
    "session_updated": None,
    "inputs": {
        "database_path": "",
        "rule_paths": [],
        "aggregated_rule_path": "",
        "user_config_path": "",
        "discovery_mode": "auto",
        "discovery_manual_paths": [],
    },
    "decisions": {
        "branch_decisions": {},
    },
    "results": {
        "last_compute": {
            "trees_count": 0,
            "mapping_count": 0,
            "warnings": [],
            "errors": [],
            "stats": {},
            "inputs_hash": "",
            "timestamp": None,
        },
    },
}

VALID_SECTIONS = frozenset({"inputs", "decisions", "results"})


# ── Helpers ────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 with microsecond precision and
    ``Z`` suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _ensure_dir(path: Path) -> None:
    """Create parent directories of *path* if they do not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)


def _atomic_write(data: dict[str, Any], path: Path) -> None:
    """Write *data* as pretty-printed JSON to *path* atomically.

    A unique temporary file is created via ``tempfile.mkstemp`` in the same
    directory.  Once the write succeeds ``os.replace()`` moves it to the
    target path.  If the process crashes mid-write the original file (if any)
    is never truncated.

    Using a unique temp file name (rather than a fixed ``.tmp`` sibling) makes
    this safe for concurrent callers — each writer gets a distinct temp file.
    """
    fd, tmp_path_str = tempfile.mkstemp(
        suffix=".tmp",
        prefix=path.name + ".",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path_str, str(path))
    except BaseException:
        # Clean up the temp file on any error so we never leave debris.
        try:
            os.unlink(tmp_path_str)
        except OSError:
            pass
        raise


def _load_raw(path: Path) -> dict[str, Any] | None:
    """Return parsed JSON content of *path*, or ``None`` if the file does not
    exist or contains invalid JSON (in which case the file is backed up as
    ``.bak``)."""
    if not path.exists():
        return None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
        # File exists but top-level value is not a dict — treat as corrupt.
        _backup_corrupt(path)
        return None
    except (json.JSONDecodeError, ValueError, OSError):
        _backup_corrupt(path)
        return None


def _backup_corrupt(path: Path) -> None:
    """Rename the corrupt file to ``<name>.bak``, appending a timestamp to
    avoid overwriting a previous backup."""
    ts = _now_iso().replace(":", "-")  # colon is invalid on Windows paths
    bak = path.with_suffix(f".{ts}.bak")
    try:
        os.replace(str(path), str(bak))
    except OSError:
        pass  # Best-effort; nothing we can do if backup also fails.


# ── Public API ─────────────────────────────────────────────────────────────────


def get_workspace_path() -> Path:
    """Return the platform-default workspace.json path.

    Linux:
        ``~/.local/share/kmm/workspace.json``
    Windows:
        ``%localappdata%/kmm/workspace.json``

    The parent directory is **not** created by this function (it is created
    on first write by :func:`load_workspace` / :func:`save_workspace`).
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or str(Path.home())
        base = Path(home) / ".local" / "share"
    return base / "kmm" / "workspace.json"


def load_workspace(path: str | Path | None = None) -> dict[str, Any]:
    """Read workspace.json and return the parsed dictionary.

    If the file does not exist, a default structure is created, written to
    disk (including parent directory creation), and returned.

    If the file contains invalid JSON, it is backed up as ``<name>.<ts>.bak``
    and a fresh default structure is returned (and written to disk).

    Args:
        path:
            Explicit path to ``workspace.json``.  When ``None``, the
            platform-default path (see :func:`get_workspace_path`) is used.

    Returns:
        Workspace dictionary (always a valid structure).
    """
    target = Path(path) if path is not None else get_workspace_path()
    raw = _load_raw(target)

    if raw is not None:
        return raw

    # File missing or corrupt — create default and persist it.
    _ensure_dir(target)
    default = dict(DEFAULT_WORKSPACE)  # shallow copy is sufficient here
    _atomic_write(default, target)
    return default


def save_workspace(data: dict[str, Any], path: str | Path | None = None) -> None:
    """Atomically write *data* to workspace.json.

    The ``session_updated`` field is always overwritten with the current UTC
    timestamp.

    Args:
        data:
            Full workspace dictionary to persist.
        path:
            Explicit path.  When ``None``, the platform-default path is used.

    Raises:
        OSError:
            If the directory cannot be created or the write fails.
    """
    target = Path(path) if path is not None else get_workspace_path()
    _ensure_dir(target)

    data = dict(data)  # shallow copy so we do not mutate the caller's dict
    data["session_updated"] = _now_iso()

    _atomic_write(data, target)


def merge_workspace(
    data: dict[str, Any],
    section: str,
    path: str | Path | None = None,
) -> dict[str, Any]:
    """Load workspace, merge *data* into *section*, persist atomically, and
    return the complete workspace.

    This is a **partial / shallow merge**: only the keys present in *data*
    are updated within the target *section*; existing keys that are not
    mentioned in *data* are preserved unchanged.

    Args:
        data:
            Fields to merge into the target *section*.
        section:
            One of ``"inputs"``, ``"decisions"``, or ``"results"``.
        path:
            Explicit path to workspace.json.  When ``None``, the
            platform-default path is used.

    Returns:
        The full workspace dictionary after the merge.

    Raises:
        ValueError:
            If *section* is not one of the valid section names.
    """
    if section not in VALID_SECTIONS:
        raise ValueError(
            f"merge_workspace section must be one of {sorted(VALID_SECTIONS)}, "
            f"got {section!r}"
        )

    workspace = load_workspace(path)
    workspace[section].update(data)
    save_workspace(workspace, path)
    return workspace
