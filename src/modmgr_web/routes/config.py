"""Config routes — ``POST /api/config/discover`` and ``POST /api/config/save``."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter
from modmgr.bootstrap import discover_user_config
from modmgr.userconfig_ops import userconfig_save

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import DiscoverUserConfigRequest, SaveConfigRequest

router = APIRouter()


@router.post("/discover")
async def discover_config(req: DiscoverUserConfigRequest):
    """Discover user_config.json and return it together with the file path.

    Returns an ``ApiResponse`` with ``{"config": ..., "config_index": ...}``.
    """
    try:
        config, config_index = discover_user_config(config_index=req.config_index)
        return adapt_dict_result({"config": config, "config_index": config_index})
    except (ValueError, FileNotFoundError) as exc:
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
    """Save a user_config dict to the target location.

    Uses ``config_index`` from the request body (returned by a prior
    ``/discover`` call) to locate the file, then delegates persistence to
    ``userconfig_save()``.
    """
    try:
        normalized_config = _normalize_rule_sources(req.config)
        userconfig_save(req.config_index, normalized_config)
        return adapt_dict_result({"saved": req.config_index})
    except Exception as exc:
        return adapt_error(str(exc))
