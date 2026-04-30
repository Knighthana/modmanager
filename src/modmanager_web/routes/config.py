"""Config routes — ``POST /api/config/discover``."""

from __future__ import annotations

from fastapi import APIRouter
from modmanager.bootstrap import discover_user_config

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import DiscoverUserConfigRequest

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
