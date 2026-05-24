"""FastAPI dependencies shared across routes."""

import json

from fastapi import Header, HTTPException


def resolve_config_index(
    x_userconfig_index: str = Header(..., alias="X-UserConfig-Index"),
) -> str:
    """Extract and resolve the config_index file path from the HTTP header.

    Returns the 'string' field from the index object, suitable for
    passing to discover_user_config(config_index=...).
    """
    try:
        obj = json.loads(x_userconfig_index)
        path = obj.get("string", "")
        if not path:
            raise HTTPException(status_code=400, detail="X-UserConfig-Index header has empty 'string' field")
        return path
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid X-UserConfig-Index header")
