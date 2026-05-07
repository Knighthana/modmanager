"""Database routes — ``POST /api/database/generate``."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from modmanager.bootstrap import generate_database

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import GenerateDatabaseRequest, LoadDatabaseRequest
from ..sse import stream_with_progress

router = APIRouter()


@router.post("/generate")
async def generate(req: GenerateDatabaseRequest):
    """Generate or load the Steam database via SSE stream.

    SSE events:
      - ``progress`` — scanning progress updates
      - ``result``   — the database dict wrapped in ``ApiResponse``
      - ``error``    — exception information
    """

    def do_work(*, on_progress):
        return generate_database(
            mode=req.mode,
            paths=req.paths,
            working_pathstyle=req.working_pathstyle,
            greedy_parsing=req.greedy_parsing,
            on_progress=on_progress,
            cache_path=req.cache_path,
        )

    return StreamingResponse(
        stream_with_progress(do_work, result_adapter=adapt_dict_result),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/load")
async def load_database(req: LoadDatabaseRequest):
    """Load a database.json file from a user-specified path.

    Returns the database dict wrapped in ApiResponse.
    Uses path_resolver to handle fuzzy user input.
    """
    from modmanager.path_resolver import resolve_file_path
    from modmanager.iojson import load_json_file

    try:
        resolved = resolve_file_path(req.path, "database.json")
        data = load_json_file(resolved)
        return adapt_dict_result(data)
    except FileNotFoundError as e:
        return adapt_error(str(e))
    except Exception as e:
        return adapt_error(f"Failed to load database: {e}")
