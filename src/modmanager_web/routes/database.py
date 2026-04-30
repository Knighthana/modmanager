"""Database routes — ``POST /api/database/generate``."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from modmanager_cli.bootstrap import generate_database

from ..adapters import adapt_dict_result
from ..schemas import GenerateDatabaseRequest
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
