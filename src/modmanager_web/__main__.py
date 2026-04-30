"""Entry point for ``python -m modmanager_web`` and the ``modmanager-web`` script.

Starts a uvicorn server on ``127.0.0.1:8000``.
"""

from __future__ import annotations

import uvicorn

from .app import create_app


def main() -> None:
    """Launch the ModManager Web API server."""
    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
