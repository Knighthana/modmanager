"""bootstrap.py — Environment initialization for the mod manager.

Provides:
  - ``ProgressCallback`` protocol for progress reporting.
  - ``_detect_software_dir()`` — locate the software root directory.
  - ``discover_user_config()`` — single-level user_config.json discovery
    with first-use default creation.
  - ``generate_database()`` — generate or load Steam database (auto / manual).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Protocol

from .database_ops import discover_with_fallback
from .iojson import load_json_file, write_json_file
from .path_resolver import expand_path
from .paths import normalize_posix

__all__ = [
    "ProgressCallback",
    "discover_user_config",
    "generate_database",
]


# ── Progress callback protocol ────────────────────────────────────────────────


class ProgressCallback(Protocol):
    """Progress notification callback.

    Args:
        step: Stage identifier ("scan" | "aggregate" | "compute" | "backup" |
              "apply" | "restore").
        finished: Number of completed items.
        total: Total number of items (-1 means unknown).
        message: Optional description text.
    """

    def __call__(self, step: str, finished: int, total: int, message: str = "") -> None:
        ...


# ── Internal helpers ──────────────────────────────────────────────────────────


def _detect_software_dir() -> str:
    """Locate the software root directory.

    Starting from the package directory (containing this file), walk upward
    until a ``pyproject.toml`` file is found.  If found, that parent directory
    is returned (development mode).  Otherwise the package directory itself
    (``site-packages/modmanager/``) is returned (installed mode).

    Returns:
        Absolute path in POSIX style.
    """
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return normalize_posix(str(parent))
    return normalize_posix(str(current))


# ── Public API ────────────────────────────────────────────────────────────────


def discover_user_config(home_dir: str | None = None) -> dict:
    """Discover ``user_config.json`` via single-level search with first-use creation.

    Searches **only** the platform-default location:
      - Linux:   ``~/.config/kmm/user_config.json``
      - Windows: ``%APPDATA%/kmm/user_config.json``

    If the file exists and contains a valid JSON dict it is loaded and returned
    (``first_use=false``).  If the file does not exist (or contains invalid
    content), a default configuration is created at that location with an empty
    ``databases`` object (``first_use=true``) and returned.

    Args:
        home_dir:
            User home directory.  When ``None``, resolved from environment
            variables ``$HOME`` / ``%USERPROFILE%``, falling back to
            ``pathlib.Path.home()``.

    Returns:
        User config dictionary (always contains ``databases``, ``source_path``,
        and ``first_use`` keys).
    """
    if home_dir is None:
        home_dir = (
            os.environ.get("HOME")
            or os.environ.get("USERPROFILE")
            or str(Path.home())
        )

    # Platform-specific config directory
    if sys.platform == "win32":
        config_dir = Path(os.environ.get("APPDATA", str(Path(home_dir) / "AppData" / "Roaming")))
    else:
        config_dir = Path(home_dir) / ".config"

    config_path = config_dir / "kmm" / "user_config.json"

    # --- File exists, load it ---
    if config_path.exists():
        try:
            data = load_json_file(str(config_path))
            if isinstance(data, dict):
                data["source_path"] = str(config_path)
                data["first_use"] = False
                return data
        except Exception:
            pass
        # Invalid content — fall through to recreate

    # --- File does not exist or is invalid — create default ---
    config_path.parent.mkdir(parents=True, exist_ok=True)

    default_db_path = normalize_posix(
        str(Path(home_dir) / ".local" / "share" / "kmm" / "database.json")
    )
    default_config: dict[str, Any] = {
        "databases": {
            "default": {"path": default_db_path},
        },
        "source_path": str(config_path),
        "first_use": True,
    }

    write_json_file(str(config_path), default_config)
    return dict(default_config)


def generate_database(
    mode: str,
    *,
    paths: list[str] | None = None,
    greedy_parsing: bool = False,
    on_progress: ProgressCallback | None = None,
    database_name: str = "default",
) -> dict:
    """Generate or load the Steam database.

    The database path is determined from ``user_config.databases[database_name].path``.
    If the file exists at that path with a valid structure (at least a
    ``"steamlib"`` key containing a list), it is loaded and returned immediately
    — no scanning is performed.

    Otherwise the database is generated by scanning Steam libraries (``"auto"``
    mode) or from explicitly provided paths (``"manual"`` mode).  On success
    the result is written to the path from user config.

    Args:
        mode:
            ``"auto"`` — automatically discover Steam library paths.
            ``"manual"`` — use the explicit *paths* argument.
        paths:
            List of VDF file paths or ``steamapps`` directory paths (only used
            when ``mode="manual"``).
        working_pathstyle:
            ``"linux"`` or ``"windows"`` path style.
        greedy_parsing:
            When ``True``, scan all discovered mods regardless of game scoping.
        on_progress:
            Optional progress callback.
        database_name:
            Name of the database entry in ``user_config.databases``
            (default ``"default"``).

    Returns:
        Database dictionary compatible with ``engine.compute_mapping``.

    Raises:
        ValueError:
            If *mode* is not ``"auto"`` or ``"manual"``, or if
            ``mode="manual"`` but *paths* is empty or ``None``, or if
            ``database_name`` is not found in ``user_config.databases``.
    """
    # ── Resolve database path from user config ────────────────────────────
    config = discover_user_config()
    db_path = expand_path(config.get("databases", {}).get(database_name, {}).get("path", ""))
    if not db_path:
        raise ValueError(
            f"database '{database_name}' not found in user_config.databases"
        )

    # ── Auto-detect working path style from platform ───────────────────────
    working_pathstyle = "windows" if sys.platform == "win32" else "linux"

    # ── Validate mode ─────────────────────────────────────────────────────
    if mode not in ("auto", "manual"):
        raise ValueError(f"mode must be 'auto' or 'manual', got {mode!r}")

    if mode == "manual" and not paths:
        raise ValueError("manual mode requires at least one path")

    # ── Generate database ─────────────────────────────────────────────────
    if mode == "auto" and not paths:
        # Pure auto mode: no manual paths, no manual_only
        if on_progress is not None:
            on_progress("scan", 0, -1, "Discovering Steam libraries...")
        database = discover_with_fallback(
            working_pathstyle=working_pathstyle,
            greedy_parsing=greedy_parsing,
        )
        if on_progress is not None:
            on_progress("scan", 1, 1, "Steam discovery complete")
    elif mode == "manual":
        # Manual only: skip auto-discovery entirely
        from .path_resolver import resolve_directory_path
        resolved_paths = [resolve_directory_path(p, 'steamapps') for p in paths]
        manual_override_steamlibs = [
            {
                "path": p,
                "contains_libraryfolders_vdf": False,
                "game": [],
            }
            for p in resolved_paths
        ]
        if on_progress is not None:
            on_progress("scan", 0, -1, "Scanning provided library paths...")
        database = discover_with_fallback(
            working_pathstyle=working_pathstyle,
            manual_override_steamlibs=manual_override_steamlibs,
            greedy_parsing=greedy_parsing,
            manual_only=True,
        )
        if on_progress is not None:
            on_progress("scan", 1, 1, "Manual scan complete")
    else:
        # mode == "auto" with paths: combine auto + manual (manual_only=False)
        from .path_resolver import resolve_directory_path
        resolved_paths = [resolve_directory_path(p, 'steamapps') for p in paths]
        manual_override_steamlibs = [
            {
                "path": p,
                "contains_libraryfolders_vdf": False,
                "game": [],
            }
            for p in resolved_paths
        ]
        if on_progress is not None:
            on_progress("scan", 0, -1, "Discovering Steam libraries (auto + manual)...")
        database = discover_with_fallback(
            working_pathstyle=working_pathstyle,
            manual_override_steamlibs=manual_override_steamlibs,
            greedy_parsing=greedy_parsing,
            manual_only=False,
        )
        if on_progress is not None:
            on_progress("scan", 1, 1, "Combined scan complete")

    # ── Write result ───────────────────────────────────────────────────────
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    write_json_file(db_path, database)

    return database
