"""Database routes — ``POST /api/database/generate``, ``/save``, ``/read``."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from hana_modmgr.bootstrap import discover_user_config, generate_database
from hana_modmgr.iojson import load_json_file, write_json_file
from hana_modmgr.path_resolver import expand_path

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import GenerateDatabaseRequest, ReadDatabaseRequest, SaveDatabaseRequest
from ..sse import stream_with_progress

router = APIRouter()


# ── Helper ────────────────────────────────────────────────────────────────────


def _resolve_database_path(database_name: str, user_config: dict) -> str:
    """Resolve the on-disk path for *database_name* from *user_config*."""
    db = user_config.get("databases", {}).get(database_name)
    if not db:
        raise ValueError(
            f"database '{database_name}' not found in user_config.databases"
        )
    return expand_path(db["path"])


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/generate")
async def generate(req: GenerateDatabaseRequest):
    """Generate or load the Steam database via SSE stream.

    SSE events:
      - ``progress`` — scanning progress updates
      - ``result``   — the database dict wrapped in ``ApiResponse``
      - ``error``    — exception information

    Note: The returned database does not contain managed/warnings/errors fields —
    those are handled at the workspace level.
    """

    def do_work(*, on_progress):
        return generate_database(
            mode=req.mode,
            paths=req.paths,
            greedy_parsing=req.greedy_parsing,
            on_progress=on_progress,
            database_name=req.database_name,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_dict_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/read")
async def read_database(req: ReadDatabaseRequest):
    """Load a database.json by *database_name* from user config.

    Returns the database dict wrapped in ApiResponse.
    """
    try:
        user_config = discover_user_config()
        resolved = _resolve_database_path(req.database_name, user_config)
        data = load_json_file(resolved)
        return adapt_dict_result(data)
    except FileNotFoundError as e:
        return adapt_error(str(e))
    except Exception as e:
        return adapt_error(f"Failed to load database: {e}")


@router.post("/save")
async def save_database(req: SaveDatabaseRequest):
    """Save database dict to disk using *database_name* from user config.

    Receives the full database dict (without managed fields) and writes
    to the path resolved from user_config.databases[database_name].
    """
    try:
        user_config = discover_user_config()
        resolved = _resolve_database_path(req.database_name, user_config)
        write_json_file(resolved, req.database)
    except Exception as e:
        return adapt_error(f"Failed to write database: {e}")

    return {
        "ok": True,
        "data": {"path": resolved, "database": req.database},
        "errors": [],
        "warnings": [],
    }
