"""modmanager_web — FastAPI web layer for ModManager.

This package provides a pure HTTP layer over the shared orchestrator
service layer (``modmanager_cli.orchestrator``).  No business logic lives
here — only parameter reception, format adaptation, and SSE streaming.
"""

from .app import create_app

__all__ = ["create_app"]
