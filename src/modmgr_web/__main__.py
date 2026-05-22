"""Entry point for ``python -m modmgr_web`` and the ``modmgr-web`` script.

Starts a uvicorn server on ``127.0.0.1:8000``.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Launch the modmgr Web API server."""
    try:
        import uvicorn
        from .app import create_app
    except ImportError as exc:
        print(
            "modmgr_web requires the optional web dependencies. "
            "Install with `pip install modmgr[web]`.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    app = create_app()
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
