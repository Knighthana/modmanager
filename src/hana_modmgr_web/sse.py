"""SSE (Server-Sent Events) progress bridge.

Bridges synchronous ``ProgressCallback``-based work into an async
``StreamingResponse`` via an ``asyncio.Queue`` and a thread pool.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .adapters import adapt_pipeline_result, adapt_error

# Module-level thread pool — shared across all SSE streams.
_executor = ThreadPoolExecutor(max_workers=4)


async def stream_with_progress(
    sync_work: Callable[..., Any],
    *,
    result_adapter: Callable[[Any], dict] = adapt_pipeline_result,
) -> AsyncGenerator[str, None]:
    """Execute *sync_work* in a background thread and yield SSE events.

    The callable receives a single keyword argument ``on_progress`` which it
    should invoke to report progress.  Its return value is adapted via
    *result_adapter* and emitted as an ``event: result``.

    SSE event types emitted:
      - ``progress`` — progress update (step, finished, total, message)
      - ``result``   — final result (adapted via *result_adapter*)
      - ``error``    — unhandled exception

    Yields:
        Strings in ``event: <type>\\ndata: <json>\\n\\n`` format.
    """
    queue: asyncio.Queue[dict] = asyncio.Queue()
    # Capture the running event loop at async scope — this is the *correct*
    # loop that ``call_soon_threadsafe`` must target.  Calling
    # ``asyncio.get_event_loop()`` from a background thread would return a
    # different loop, breaking the bridge.
    loop = asyncio.get_event_loop()

    def progress_cb(
        step: str, finished: int, total: int, message: str = ""
    ) -> None:
        loop.call_soon_threadsafe(
            queue.put_nowait,
            {
                "type": "progress",
                "step": step,
                "finished": finished,
                "total": total,
                "message": message,
            },
        )

    def worker() -> None:
        try:
            result = sync_work(on_progress=progress_cb)
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "result", "payload": result}
            )
        except Exception as exc:
            loop.call_soon_threadsafe(
                queue.put_nowait, {"type": "error", "message": str(exc)}
            )

    loop.run_in_executor(_executor, worker)

    try:
        while True:
            item = await queue.get()
            if item["type"] == "progress":
                yield f"event: progress\ndata: {json.dumps(item)}\n\n"
            elif item["type"] == "result":
                adapted = result_adapter(item["payload"])
                yield f"event: result\ndata: {json.dumps(adapted)}\n\n"
                return
            elif item["type"] == "error":
                error_body = adapt_error(item["message"])
                yield f"event: error\ndata: {json.dumps(error_body)}\n\n"
                return
    except asyncio.CancelledError:
        # Client disconnected — background thread cannot be safely
        # cancelled, let it finish silently.
        pass
