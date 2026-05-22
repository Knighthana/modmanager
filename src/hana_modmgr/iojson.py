from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_file(path: str | Path) -> Any:
    """Read and parse JSON from a file."""
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def write_json_file(path: str | Path, data: Any, *, ensure_ascii: bool = False, indent: int = 2) -> None:
    """Serialize JSON to file and append trailing newline."""
    p = Path(path)
    payload = json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
    p.write_text(payload + "\n", encoding="utf-8")


def dumps_pretty(data: Any, *, ensure_ascii: bool = False, indent: int = 2) -> str:
    """Serialize JSON for stdout or logging."""
    return json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)


__all__ = ["load_json_file", "write_json_file", "dumps_pretty"]
