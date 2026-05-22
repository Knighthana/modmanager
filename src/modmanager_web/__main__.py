"""Entry point for ``python -m modmanager_web`` and the ``modmanager-web`` script.

Starts a uvicorn server on ``127.0.0.1:8000``.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the ModManager Web API server."""
    try:
        import uvicorn
        from .app import create_app
    except ImportError as exc:
        print(
            "modmanager_web requires the optional web dependencies. "
            "Install with `pip install modmanager[web]` or use the GitHub source tree.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
