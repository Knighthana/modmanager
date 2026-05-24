"""Config routes — ``POST /api/config/discover`` and ``POST /api/config/save``."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends
from modmgr.bootstrap import discover_user_config
from modmgr.userconfig_ops import userconfig_save

from ..adapters import adapt_dict_result, adapt_error
from ..dependencies import resolve_config_index
from ..schemas import DiscoverUserConfigRequest, SaveConfigRequest

router = APIRouter()


@router.post("/discover")
async def discover_config(req: DiscoverUserConfigRequest, ci_path: str = Depends(resolve_config_index)):
    """Discover user_config.json and return it together with the file path.

    Returns an ``ApiResponse`` with ``{"config": ..., "config_index": ...}``.
    """
    try:
        config, config_index = discover_user_config(config_index=ci_path)
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
async def save_config(req: SaveConfigRequest, ci_path: str = Depends(resolve_config_index)):
    """Save a user_config dict to the target location.

    Uses ``config_index`` from the request header (returned by a prior
    ``/discover`` call) to locate the file, then delegates persistence to
    ``userconfig_save()``.
    """
    try:
        # Load existing full config — frontend only sends changed fields
        from modmgr.iojson import load_json_file
        try:
            existing = load_json_file(ci_path)
        except Exception:
            existing = {}

        # Merge frontend changes on top of existing
        merged = {**existing, **req.config}
        normalized_config = _normalize_rule_sources(merged)
        userconfig_save(ci_path, normalized_config)
        return adapt_dict_result({"saved": {"type": "path", "string": ci_path}})
    except Exception as exc:
        return adapt_error(str(exc))
