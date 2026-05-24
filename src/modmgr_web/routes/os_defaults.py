"""OS defaults route — ``GET /api/os/defaults``."""

from __future__ import annotations

from fastapi import APIRouter
from modmgr.osplatform import defaultvalue as os_defaults, platform as detect_platform

from ..adapters import adapt_dict_result

router = APIRouter()


@router.get("/defaults")
async def os_defaults_endpoint():
    """Return platform default values for frontend initialisation.

    No state, no dependency on user_config.
    """
    return adapt_dict_result({
        "platform": detect_platform(),
        "userconfig_index": os_defaults.userconfig_index_get(),
    })
