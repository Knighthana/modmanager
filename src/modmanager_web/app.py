"""FastAPI application factory for ModManager Web API."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import config, database, pipeline


def create_app() -> FastAPI:
    """Build and return a configured FastAPI application instance."""
    app = FastAPI(
        title="ModManager Web API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS — open for local development; tighten for production if needed.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
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

    # ── Static file mount + SPA fallback (only when build artefact exists) ──
    static_dir = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if static_dir.exists() and (static_dir / "index.html").exists():
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
