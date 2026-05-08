"""Config routes — ``POST /api/config/discover`` and ``POST /api/config/save``."""

from __future__ import annotations

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


@router.post("/save")
async def save_config(req: SaveConfigRequest):
    """Save a user_config dict to a file.

    Returns an ``ApiResponse`` with the saved path on success.
    """
    try:
        output_path = str(Path(req.output_path).expanduser().resolve())
        write_json_file(output_path, req.config)
        return adapt_dict_result({"saved": output_path})
    except Exception as exc:
        return adapt_error(str(exc))
