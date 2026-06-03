"""Shared helpers for fileops package."""

from __future__ import annotations

from typing import Any


def _notify(on_progress: Any, step: str, finished: int, total: int, message: str = "") -> None:
    """Send progress if callback is set."""
    if on_progress:
        on_progress(step, finished, total, message)
