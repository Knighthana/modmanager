"""Database routes — ``POST /api/database/generate``, ``/save``, ``/load``."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from modmanager.bootstrap import generate_database
from modmanager.iojson import write_json_file

from ..adapters import adapt_dict_result, adapt_error
from ..schemas import GenerateDatabaseRequest, LoadDatabaseRequest, SaveDatabaseRequest
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


@router.post("/save")
async def save_database(req: SaveDatabaseRequest):
    """Save database after validating managed-field constraints.

    Validates:
      - For games: at most one ``managed: true`` per ``appid`` group.
      - For mods: at most one ``managed: true`` per ``mixed_id`` group.

    On success writes the database dict to ``output_path`` and returns ok.
    On validation failure returns the list of errors (flat, no counting).
    """
    errors: list[str] = []
    db = req.database

    # ── Validate games ────────────────────────────────────────────────────
    games_raw: list[dict[str, Any]] = db.get("game", []) or []
    appid_managed_true: dict[str, int] = {}
    for i, g in enumerate(games_raw):
        if g.get("managed"):
            appid = str(g.get("appid", ""))
            if appid in appid_managed_true:
                errors.append(
                    f"E_DUPLICATE_APPID: game[{i}] appid={appid} 的 managed=true 与 "
                    f"game[{appid_managed_true[appid]}] 冲突，同一 appid 最多一个 managed=true"
                )
            else:
                appid_managed_true[appid] = i

    # ── Validate mods ─────────────────────────────────────────────────────
    mods_raw: list[dict[str, Any]] = db.get("mod", []) or []
    mixed_id_managed_true: dict[str, int] = {}
    for i, m in enumerate(mods_raw):
        if m.get("managed"):
            mixed_id = str(m.get("mixed_id", ""))
            if not mixed_id:
                continue
            if mixed_id in mixed_id_managed_true:
                errors.append(
                    f"E_DUPLICATE_MIXED_ID: mod[{i}] mixed_id={mixed_id} 的 managed=true 与 "
                    f"mod[{mixed_id_managed_true[mixed_id]}] 冲突，同一 mixed_id 最多一个 managed=true"
                )
            else:
                mixed_id_managed_true[mixed_id] = i

    if errors:
        return {
            "ok": False,
            "data": None,
            "errors": errors,
            "warnings": [],
        }

    # ── Write to file ─────────────────────────────────────────────────────
    try:
        write_json_file(req.output_path, db)
    except Exception as e:
        return adapt_error(f"Failed to write database: {e}")

    return {
        "ok": True,
        "data": {"path": req.output_path},
        "errors": [],
        "warnings": [],
    }
