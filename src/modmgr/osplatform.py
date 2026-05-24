"""OS detection and default values — single authority for platform knowledge."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


def _normalize(path: str) -> str:
    """Normalize a path to POSIX style — avoids circular import with paths.py."""
    from .paths import normalize_posix
    return normalize_posix(path)


def platform() -> str:
    """Return 'linux', 'windows', 'darwin', or 'wsl'."""
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "darwin"
    # Linux — check for WSL
    try:
        with open("/proc/version", "r") as f:
            content = f.read().lower()
            if "microsoft" in content or "wsl" in content:
                return "wsl"
    except (FileNotFoundError, PermissionError):
        pass
    return "linux"


class _DefaultValues:
    """Private default values. External access via get methods only."""
    
    def _home(self) -> str:
        return os.environ.get("HOME") or os.environ.get("USERPROFILE") or str(Path.home())
    
    def userconfig_index_get(self) -> dict[str, str]:
        p = platform()
        home = self._home()
        if p in ("linux", "wsl"):
            return {"type": "path", "string": _normalize(str(Path(home) / ".config" / "kmm" / "user_config.json"))}
        elif p == "windows":
            appdata = os.environ.get("APPDATA", str(Path(home) / "AppData" / "Roaming"))
            return {"type": "path", "string": _normalize(str(Path(appdata) / "kmm" / "user_config.json"))}
        else:
            return {"type": "path", "string": _normalize(str(Path(home) / "Library" / "Preferences" / "kmm" / "user_config.json"))}
    
    def workspace_dir_get(self) -> str:
        p = platform()
        home = self._home()
        if p in ("linux", "wsl"):
            return _normalize(str(Path(home) / ".cache" / "kmm" / "workspace"))
        elif p == "windows":
            local = os.environ.get("LOCALAPPDATA", str(Path(home) / "AppData" / "Local"))
            return _normalize(str(Path(local) / "kmm" / "workspace"))
        else:
            return _normalize(str(Path(home) / "Library" / "Caches" / "kmm" / "workspace"))
    
    def database_path_get(self) -> str:
        p = platform()
        home = self._home()
        if p in ("linux", "wsl"):
            return _normalize(str(Path(home) / ".local" / "share" / "kmm" / "database.json"))
        elif p == "windows":
            local = os.environ.get("LOCALAPPDATA", str(Path(home) / "AppData" / "Local"))
            return _normalize(str(Path(local) / "kmm" / "database" / "database.json"))
        else:
            return _normalize(str(Path(home) / "Library" / "Application Support" / "kmm" / "database.json"))
    
    def working_pathstyle_get(self) -> str:
        p = platform()
        if p in ("linux", "wsl", "darwin"):
            return "linux"
        return "windows"


defaultvalue = _DefaultValues()


__all__ = ["platform", "defaultvalue"]
