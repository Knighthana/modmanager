"""bootstrap.py — Environment initialization for the mod manager.

Provides:
  - ``ProgressCallback`` protocol for progress reporting.
  - ``_detect_software_dir()`` — locate the software root directory.
  - ``discover_user_config()`` — discover user_config.json at an explicit path.
  - ``generate_database()`` — generate or load Steam database (auto / manual).
"""

from __future__ import annotations

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


# ── Steam.exe helper ─────────────────────────────────────────────────────────────


def _derive_steamapps_from_steam_exe(steam_exe_path: str) -> list[str]:
    """Derive steamapps paths from a steam.exe location.

    Per DESIGN_BOOTSTRAP.md §2.1:
      1. SteamRoot = directory containing steam.exe
      2. Check SteamRoot/steamapps/libraryfolders.vdf (newer Steam)
      3. Otherwise check SteamRoot/config/libraryfolders.vdf (older Steam)
      4. Parse VDF to expand all library paths
      5. SteamRoot/steamapps/ itself is always included as default library

    Returns:
        List of steamapps directory paths.
    Raises:
        ValueError: if steam.exe path is invalid or VDF cannot be found/parsed.
    """
    steam_root = Path(steam_exe_path).parent

    if not steam_root.is_dir():
        raise ValueError(f"Steam root directory not found: {steam_root}")

    # Try to locate libraryfolders.vdf
    vdf_paths = [
        steam_root / "steamapps" / "libraryfolders.vdf",  # newer Steam
        steam_root / "config" / "libraryfolders.vdf",      # older Steam
    ]

    libraries: list[str] = []
    vdf_found = False

    for vdf_path in vdf_paths:
        if vdf_path.is_file():
            try:
                from .vdf_parser import parse_libraryfolders_vdf
                parsed = parse_libraryfolders_vdf(str(vdf_path))
                for lib in parsed.get("libraries", []):
                    lib_path = lib.get("path", "")
                    if lib_path:
                        # VDF stores the Steam root dir, append steamapps/
                        sp = str(Path(lib_path) / "steamapps")
                        libraries.append(normalize_posix(sp))
                vdf_found = True
            except Exception:
                pass  # Continue trying next vdf path

    if not vdf_found:
        raise ValueError(
            f"Cannot find libraryfolders.vdf in {steam_root}/steamapps/ or {steam_root}/config/"
        )

    # Always include SteamRoot/steamapps/ itself
    default_steamapps = str(steam_root / "steamapps")
    if normalize_posix(default_steamapps) not in libraries:
        libraries.insert(0, normalize_posix(default_steamapps))

    return libraries


# ── Public API ────────────────────────────────────────────────────────────────


def discover_user_config(config_index: str) -> tuple[dict[str, Any], str]:
    """Discover user_config at *config_index* (mandatory).

    *config_index* must be provided by the caller — bootstrap does **not**
    perform any platform-default path discovery.

    Behaviour:

    1. File exists + complete (all REQUIRED_KEYS present, valid
       schema_namespace) → return ``(loaded_dict, path)``.
    2. File exists + incomplete (missing keys)
       → call ``userconfig_init(path)`` → return ``(patched_dict, path)``.
    3. File does not exist
       → call ``userconfig_init(path)`` → return ``(created_dict, path)``.
    4. File exists but invalid (wrong namespace, corrupt JSON)
       → raise ``ValueError`` with the reason.

    The returned ``config_dict`` does **not** contain ``source_path`` or
    ``first_use`` keys.

    Args:
        config_index:
            Explicit path to ``user_config.json``.  **Required** — a
            ``ValueError`` is raised when falsy.

    Returns:
        ``(config_dict, config_index)`` tuple where *config_index* is the
        absolute file path of the discovered or created file.

    Raises:
        ValueError:
            If *config_index* is ``None`` or empty, or if the file exists but
            has wrong ``schema_namespace`` or contains corrupt / non-dict JSON.
    """
    from .userconfig_ops import DEFAULTS, REQUIRED_KEYS, userconfig_init

    if not config_index:
        raise ValueError("config_index is required — caller must provide the path to user_config.json")

    config_path = Path(config_index)

    # ── Case 3: file does not exist → create via userconfig_init ─────────
    if not config_path.exists():
        config_dict = userconfig_init(config_index)
        return (config_dict, config_index)

    # ── File exists — load it ─────────────────────────────────────────────
    try:
        data = load_json_file(str(config_path))
    except Exception as exc:
        raise ValueError(f"Invalid JSON in user config: {config_index}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"User config must be a dict: {config_index}")

    # Validate schema_namespace
    expected_namespace = DEFAULTS.get("schema_namespace", "KMM_UserConfig")
    if data.get("schema_namespace") != expected_namespace:
        raise ValueError(
            f"Wrong schema_namespace in user config: {config_index} "
            f"(expected {expected_namespace!r})"
        )

    # ── Case 1: complete — all REQUIRED_KEYS present ─────────────────────
    if all(key in data for key in REQUIRED_KEYS):
        return (data, config_index)

    # ── Case 2: incomplete → patch via userconfig_init ───────────────────
    config_dict = userconfig_init(config_index)
    return (config_dict, config_index)


def generate_database(
    mode: str,
    *,
    config_index: str,
    paths: list[str] | None = None,
    steam_exe_path: str | None = None,
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
        config_index:
            Path to ``user_config.json`` — forwarded to ``discover_user_config()``.
        paths:
            List of VDF file paths or ``steamapps`` directory paths (only used
            when ``mode="manual"``).
        steam_exe_path:
            Windows steam.exe path for VDF derivation (optional). When
            provided, steamapps paths are derived via ``_derive_steamapps_from_steam_exe``
            and merged into *paths*.
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
    import sys

    # ── Resolve database path from user config ────────────────────────────
    config, _ = discover_user_config(config_index=config_index)
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

    # ── Derive Steam libs from steam.exe if provided ─────────────────────
    if steam_exe_path:
        derived_paths = _derive_steamapps_from_steam_exe(steam_exe_path)
        if paths is None:
            paths = derived_paths
        else:
            paths = list(paths) + derived_paths

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
