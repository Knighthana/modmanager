"""Config routes — ``POST /api/config/discover`` and ``POST /api/config/save``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from modmanager.bootstrap import discover_user_config
from modmanager.iojson import write_json_file

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import DiscoverUserConfigRequest, SaveConfigRequest

router = APIRouter()


@router.post("/discover")
async def discover_config(req: DiscoverUserConfigRequest):
    """Discover and merge user_config.json from the three-tier search paths.

    Returns the merged config dict wrapped in an ``ApiResponse`` envelope.
    """
    try:
        config = discover_user_config(home_dir=req.home_dir)
        return adapt_dict_result(config)
    except FileNotFoundError as exc:
        return adapt_error(str(exc))


def _normalize_rule_sources(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize ``rule_sources`` paths in *config*.

    If a rule source path is an existing directory and does not end with ``/``,
    append ``/``.  This ensures downstream consumers can distinguish directory
    paths from file paths.
    """
    rule_sources = config.get("rule_sources")
    if not isinstance(rule_sources, list):
        return config

    normalized: list[Any] = []
    for item in rule_sources:
        if isinstance(item, str):
            if os.path.isdir(item) and not item.endswith("/"):
                item = item + "/"
        normalized.append(item)
    config["rule_sources"] = normalized
    return config


@router.post("/save")
async def save_config(req: SaveConfigRequest):
    """Save a user_config dict to the platform default location.

    The target path is determined by ``discover_user_config()`` which returns
    the config with its ``source_path``.  Returns an ``ApiResponse`` with
    the saved path on success.
    """
    try:
        normalized_config = _normalize_rule_sources(req.config)
        # Use discover_user_config to obtain the config path
        existing = discover_user_config()
        output_path = existing.get("source_path", "")
        if not output_path:
            # Fallback to platform default
            home = os.path.expanduser("~")
            output_path = str(Path(home) / ".config" / "kmm" / "user_config.json")
        write_json_file(output_path, normalized_config)
        return adapt_dict_result({"saved": output_path})
    except Exception as exc:
        return adapt_error(str(exc))
