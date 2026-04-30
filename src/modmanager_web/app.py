"""FastAPI application factory for ModManager Web API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    return app
