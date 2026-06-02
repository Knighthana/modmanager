"""bootstrap.py — Environment initialization for the mod manager.

Provides:
  - ``ProgressCallback`` protocol for progress reporting.
  - ``_detect_software_dir()`` — locate the software root directory.
  - ``discover_user_config()`` — discover user_config.json at an explicit path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .iojson import load_json_file
from .paths import normalize_posix

__all__ = [
    "ProgressCallback",
    "discover_user_config",
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
    (``site-packages/modmgr/``) is returned (installed mode).

    Returns:
        Absolute path in POSIX style.
    """
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return normalize_posix(str(parent))
    return normalize_posix(str(current))


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

    The returned ``config_dict`` does **not** contain ``config_index`` key.

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



