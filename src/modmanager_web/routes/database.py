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

    # ── 条件清除 E_DUPLICATE：仅当该类型重复全部被 managed 解决时才清除 ──
    from collections import Counter

    # 检查 game 重复是否已全部解决（每组恰好一个 managed=true）
    appid_counts = Counter(str(g.get("appid", "")) for g in games_raw)
    duplicate_appids = {a for a, c in appid_counts.items() if c > 1}
    appid_managed = Counter()
    for g in games_raw:
        if g.get("managed"):
            a = str(g.get("appid", ""))
            if a in duplicate_appids:
                appid_managed[a] += 1
    all_games_resolved = all(appid_managed.get(a, 0) == 1 for a in duplicate_appids)

    # 检查 mod 重复是否已全部解决
    mods_raw = db.get("mod", []) or []
    mid_counts = Counter(str(m.get("mixed_id", "")) for m in mods_raw)
    duplicate_mids = {m for m, c in mid_counts.items() if c > 1}
    mid_managed = Counter()
    for m in mods_raw:
        if m.get("managed"):
            mid = str(m.get("mixed_id", ""))
            if mid in duplicate_mids:
                mid_managed[mid] += 1
    all_mods_resolved = all(mid_managed.get(m, 0) == 1 for m in duplicate_mids)

    if all_games_resolved:
        if "errors" in db:
            db["errors"] = [e for e in db["errors"] if not str(e).startswith("E_DUPLICATE_APPID")]
        if "warnings" in db:
            db["warnings"] = [w for w in db["warnings"] if not str(w).startswith("E_DUPLICATE_APPID")]
    if all_mods_resolved:
        if "errors" in db:
            db["errors"] = [e for e in db["errors"] if not str(e).startswith("E_DUPLICATE_MIXED_ID")]
        if "warnings" in db:
            db["warnings"] = [w for w in db["warnings"] if not str(w).startswith("E_DUPLICATE_MIXED_ID")]

    # ── Write to file ─────────────────────────────────────────────────────
    try:
        write_json_file(req.output_path, db)
    except Exception as e:
        return adapt_error(f"Failed to write database: {e}")

    return {
        "ok": True,
        "data": {"path": req.output_path, "database": db},
        "errors": [],
        "warnings": [],
    }
