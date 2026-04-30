"""VDF file format parser for Steam libraryfolders.vdf.

VDF (Valve Data Format) is a key-value text format used by Steam.
Example structure:
    "LibraryFolders"
    {
        "0" { "path" "..." "label" "" "contentid" "..." }
        "1" { "path" "..." "label" "" "contentid" "..." }
        ...
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import vdf


def parse_libraryfolders_vdf(vdf_path: str) -> dict[str, Any]:
    """
    Parse libraryfolders.vdf to extract library paths and games.

    Args:
        vdf_path: Path to libraryfolders.vdf file

    Returns:
        {
          "libraries": [
            {
              "path": "/mnt/c/Program Files/Steam/steamapps/",
              "games": ["228980", "270150", ...],
              "contentid": "..."
            },
            ...
          ]
        }

    Algorithm:
        1. Read VDF file (text format)
        2. Parse into key-value structure
        3. Extract "LibraryFolders" section
        4. For each numbered entry (0, 1, 2...):
            - Get "path" value
            - Get "games" section (list of app IDs)
        5. Determine pathstyle (Windows vs Linux)
        6. Return structured data

    Raises:
        FileNotFoundError: If vdf_path does not exist
        ValueError: If VDF format is invalid
    """
    vdf_file = Path(vdf_path)
    if not vdf_file.exists():
        raise FileNotFoundError(f"VDF file not found: {vdf_path}")

    try:
        with open(vdf_file, "r", encoding="utf-8") as f:
            data = vdf.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse VDF file: {e}")

    libraries = []
    # Steam VDF root key varies by version: "LibraryFolders" (older) or "libraryfolders" (newer)
    library_folders = data.get("LibraryFolders") or data.get("libraryfolders") or {}

    # Sort by numeric keys to maintain order
    sorted_keys = sorted(
        [k for k in library_folders.keys() if k.isdigit()],
        key=int
    )

    for key in sorted_keys:
        entry = library_folders[key]
        if isinstance(entry, dict) and "path" in entry:
            lib_info = {
                "path": entry["path"],
                "contentid": entry.get("contentid", ""),
            }

            # Real VDF (Steam ≥ 2021) uses 'apps'; older/test fixtures may use 'games'
            apps_raw = entry.get("apps") or entry.get("games")
            if isinstance(apps_raw, dict):
                lib_info["games"] = list(apps_raw.keys())
            else:
                lib_info["games"] = []

            libraries.append(lib_info)

    # Determine pathstyle based on first library path
    pathstyle = "windows"
    if libraries and "\\" not in libraries[0]["path"]:
        pathstyle = "linux"

    return {
        "libraries": libraries,
        "steamlib_pathstyle": pathstyle
    }


def find_libraryfolders_vdf_paths() -> list[str]:
    """
    Find libraryfolders.vdf file(s) on the system.

    Common locations:
        - Windows: C:\\Program Files (x86)\\Steam\\steamapps\\libraryfolders.vdf
        - Linux: ~/.steam/root/steamapps/libraryfolders.vdf
        - WSL: /mnt/c/Program Files (x86)/Steam/steamapps/libraryfolders.vdf

    Returns:
        List of found libraryfolders.vdf paths (usually 0 or 1, max 1 for primary)
    """
    raise NotImplementedError("To be implemented in M1.1")
