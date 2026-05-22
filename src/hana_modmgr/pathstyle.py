"""Path-style detection and conversion utilities.

Supported styles:

* ``PathStyle.LINUX``   — POSIX paths, e.g. ``/mnt/d/Games/steamapps/``
* ``PathStyle.WINDOWS`` — Windows paths, e.g. ``D:\\Games\\steamapps\\``
                          or mixed-separator ``D:/Games/steamapps/``

WSL conventions are used for cross-style conversion:

* Linux  → Windows:  ``/mnt/c/foo/bar``  →  ``C:\\foo\\bar``
* Windows → Linux:  ``C:\\foo\\bar``     →  ``/mnt/c/foo/bar``
"""

from __future__ import annotations

import re
from enum import Enum


class PathStyle(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"


# Matches  C:\  C:/  c:\  c:/  (drive-letter prefix)
_WIN_ABS = re.compile(r"^([A-Za-z])[:/\\]")
# Matches  /mnt/<drive>/  (WSL mount prefix)
_WSL_MOUNT = re.compile(r"^/mnt/([a-z])/?(.*)", re.DOTALL)


def detect_pathstyle(path: str) -> PathStyle:
    """Return the style of *path* based on its prefix.

    UNC paths (``\\\\server\\share``) are treated as Windows.
    Everything else defaults to Linux.
    """
    if _WIN_ABS.match(path) or path.startswith("\\\\"):
        return PathStyle.WINDOWS
    return PathStyle.LINUX


def convert_path(path: str, to_style: PathStyle) -> str:
    """Convert *path* to *to_style*.

    If *path* is already in the target style, it is returned unchanged
    (after light normalisation of separators).

    Only WSL-convention ``/mnt/<drive>/…`` mounts are supported for the
    Linux → Windows direction.  Paths that cannot be converted are returned
    as-is with no error raised; callers that need strict conversion should
    check ``detect_pathstyle(result) == to_style`` afterwards.
    """
    from_style = detect_pathstyle(path)
    if from_style == to_style:
        # normalise separators in-place without changing style
        if to_style == PathStyle.WINDOWS:
            return path.replace("/", "\\")
        return path.replace("\\", "/")

    if from_style == PathStyle.WINDOWS and to_style == PathStyle.LINUX:
        return _win_to_linux(path)
    return _linux_to_win(path)


def normalize(path: str, to_style: PathStyle, *, from_style: PathStyle | None = None) -> str:
    """Convert *path* to *to_style*.

    If *from_style* is given, the path is converted directly without auto-detection.
    If *from_style* is ``None`` (default), the path style is auto-detected via
    :func:`detect_pathstyle`.

    This is the primary single-call entry point.  Usage example::

        norm = normalize(raw_path, working_style)
    """
    if from_style is not None:
        # Direct conversion — caller knows the source style
        if from_style == PathStyle.WINDOWS and to_style == PathStyle.LINUX:
            return _win_to_linux(path)
        elif from_style == PathStyle.LINUX and to_style == PathStyle.WINDOWS:
            return _linux_to_win(path)
        else:
            return path  # same style, no conversion needed
    return convert_path(path, to_style)


# ── internal helpers ──────────────────────────────────────────────────────────

def _win_to_linux(path: str) -> str:
    """``C:\\foo\\bar`` or ``C:/foo/bar`` → ``/mnt/c/foo/bar``."""
    unified = path.replace("\\", "/")
    m = re.match(r"^([A-Za-z]):/?(.*)", unified)
    if not m:
        return path
    drive = m.group(1).lower()
    rest = m.group(2).strip("/")
    return f"/mnt/{drive}/{rest}" if rest else f"/mnt/{drive}"


def _linux_to_win(path: str) -> str:
    """``/mnt/c/foo/bar`` → ``C:\\foo\\bar``."""
    m = _WSL_MOUNT.match(path)
    if not m:
        return path
    drive = m.group(1).upper()
    rest = m.group(2).strip("/").replace("/", "\\")
    return f"{drive}:\\{rest}" if rest else f"{drive}:\\"


__all__ = ["PathStyle", "detect_pathstyle", "convert_path", "normalize"]
