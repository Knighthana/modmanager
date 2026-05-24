"""FastAPI application factory for ModManager Web API."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import config, database, pipeline, rules, backups, workspace
from .routes import os_defaults as os_defaults_router


def create_app() -> FastAPI:
    """Build and return a configured FastAPI application instance."""
    app = FastAPI(
        title="ModManager Web API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Determine build output early — used for both CORS and static-file mounting.
    # Priority: 1. Source-tree frontend/dist/ (dev), 2. Packaged static/ (pip install)
    static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if not (static_dir.exists() and (static_dir / "index.html").exists()):
        static_dir = Path(__file__).parent / "static"
    prod_build = static_dir.exists() and (static_dir / "index.html").exists()

    # CORS — only needed in development (Vite dev server).
    # In production the frontend is served from the same origin, so no CORS required.
    # Tauri2 migration: set KMM_CORS_ORIGINS=tauri://localhost,https://tauri.localhost
    if not prod_build:
        dev_origins_env = os.environ.get(
            "KMM_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
        origins = [o.strip() for o in dev_origins_env.split(",") if o.strip()]
        if origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=origins,
                allow_methods=["POST", "GET"],
                allow_headers=["Content-Type", "X-UserConfig-Index"],
            )

    # ── Built-in endpoints ────────────────────────────────────────────────
    @app.get("/api/health")
    async def health():
        from .adapters import adapt_dict_result

        return adapt_dict_result(
            {"version": "0.1.0", "package": "modmanager_web"}
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(database.router, prefix="/api/database", tags=["database"])
    app.include_router(pipeline.router, prefix="/api/pipeline", tags=["pipeline"])
    app.include_router(rules.router, prefix="/api/rules", tags=["rules"])
    app.include_router(backups.router, prefix="/api/backups", tags=["backups"])
    app.include_router(workspace.router, prefix="/api/workspace", tags=["workspace"])
    app.include_router(os_defaults_router.router, prefix="/api/os", tags=["os"])

    # ── Static file mount + SPA fallback (only when build artefact exists) ──
    if prod_build:
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount(
                "/assets",
                StaticFiles(directory=str(assets_dir)),
                name="assets",
            )

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str):
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            return FileResponse(str(static_dir / "index.html"))

    return app
