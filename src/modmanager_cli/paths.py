from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .pathstyle import PathStyle, normalize


def normalize_posix(path: str) -> str:
    """Normalize a path to Linux-style separators and trim trailing slash."""
    normalized = normalize(path, PathStyle.LINUX)
    # Some upstream inputs may contain doubled separators (e.g. escaped
    # Windows literals). Collapse them to keep internal keys deterministic.
    normalized = re.sub(r"/+", "/", normalized)
    return normalized.rstrip("/")


def split_mixed_id(mixed_id: str) -> tuple[str, str] | None:
    """Split appid:modid, returning None when the format is invalid."""
    if ":" not in mixed_id:
        return None
    appid, modid = mixed_id.split(":", 1)
    if not appid or not modid:
        return None
    return appid, modid


def is_numeric_modid(mixed_id: str) -> bool:
    """Return True when modid part of appid:modid is numeric."""
    parts = split_mixed_id(mixed_id)
    return bool(parts and parts[1].isdigit())


def build_game_index(database: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index database['game'] by appid."""
    return {g.get("appid", ""): g for g in database.get("game", []) if isinstance(g, dict)}


def mod_root_from_mixed_id(
    mixed_id: str,
    game_index: dict[str, dict[str, Any]],
) -> str | None:
    """Resolve a mixed_id to absolute root path.

    For modid == 0 returns game basepath, otherwise modpath/modid.
    """
    parts = split_mixed_id(mixed_id)
    if not parts:
        return None
    appid, modid = parts
    game = game_index.get(appid)
    if not game:
        return None
    if modid == "0":
        base = game.get("basepath")
        return normalize_posix(base) if isinstance(base, str) and base not in {"", "!unknown"} else None
    modpath = game.get("modpath")
    if not isinstance(modpath, str) or modpath in {"", "!unknown"}:
        return None
    return normalize_posix(f"{modpath}/{modid}")


def path_for_mixed_id(
    mixed_id: str,
    game_index: dict[str, dict[str, Any]],
    relative_path: str = "",
) -> str | None:
    """Resolve absolute path for a mixed_id with optional relative suffix."""
    root = mod_root_from_mixed_id(mixed_id, game_index)
    if not root:
        return None
    if not relative_path:
        return root
    return normalize_posix(str(Path(root) / normalize_posix(relative_path)))


__all__ = [
    "normalize_posix",
    "split_mixed_id",
    "is_numeric_modid",
    "build_game_index",
    "mod_root_from_mixed_id",
    "path_for_mixed_id",
]
