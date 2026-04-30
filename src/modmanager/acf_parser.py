"""ACF file format parser for Steam workshop mods.

ACF (Valve Application Configuration Format) is similar to VDF.
Used for appmanifest_*.acf (game metadata) and appworkshop_*.acf (workshop mods).

Example appmanifest structure:
    "AppState"
    {
        "appid" "270150"
        "name" "Running with Rifles"
        "StateFlags" "4"
        "LastUpdated" "..."
        ...
    }

Example appworkshop structure:
    "WorkshopItemDetails"
    {
        "0" { "publishedfileid" "2606099273" ... }
        "1" { "publishedfileid" "3428584891" ... }
        ...
    }
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import vdf


def parse_appmanifest_acf(acf_path: str) -> dict[str, Any]:
    """
    Parse appmanifest_*.acf to get game information.

    Args:
        acf_path: Path to appmanifest_*.acf file

    Returns:
        {
          "appid": "270150",
          "name": "Running with Rifles",
          "installdir": "Running with Rifles",
          ...
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If ACF format is invalid
    """
    acf_file = Path(acf_path)
    if not acf_file.exists():
        raise FileNotFoundError(f"ACF file not found: {acf_path}")

    try:
        with open(acf_file, "r", encoding="utf-8") as f:
            data = vdf.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse ACF file: {e}")

    app_state = data.get("AppState", {})
    if isinstance(app_state, dict):
        return dict(app_state)
    else:
        return {}


def parse_appworkshop_acf(acf_path: str) -> list[dict[str, Any]]:
    """
    Parse appworkshop_*.acf to get workshop mod information.

    Args:
        acf_path: Path to appworkshop_*.acf file (e.g., appworkshop_270150.acf)

    Returns:
        List of mod metadata:
        [
          {
            "publishedfileid": "2606099273",
            "installed": True,
            "workingbuild": "...",
            ...
          },
          ...
        ]

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If ACF format is invalid
    """
    acf_file = Path(acf_path)
    if not acf_file.exists():
        raise FileNotFoundError(f"ACF file not found: {acf_path}")

    try:
        with open(acf_file, "r", encoding="utf-8") as f:
            data = vdf.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse ACF file: {e}")

    items = []
    workshop_items = data.get("WorkshopItemDetails", {})

    if isinstance(workshop_items, dict):
        # Sort by numeric keys
        sorted_keys = sorted(
            [k for k in workshop_items.keys() if k.isdigit()],
            key=int
        )

        for key in sorted_keys:
            entry = workshop_items[key]
            if isinstance(entry, dict):
                items.append(dict(entry))

    return items


def find_appmanifest_acf_files(steamapps_path: str) -> dict[str, str]:
    """
    Find all appmanifest_*.acf files in steamapps directory.

    Args:
        steamapps_path: Path to steamapps/ directory

    Returns:
        Dict: {appid: path_to_appmanifest_acf}
        Example: {"270150": "/path/to/appmanifest_270150.acf", ...}
    """
    raise NotImplementedError("To be implemented in M1.1")


def find_appworkshop_acf_files(steamapps_path: str) -> dict[str, str]:
    """
    Find all appworkshop_*.acf files in steamapps directory.

    Args:
        steamapps_path: Path to steamapps/ directory

    Returns:
        Dict: {appid: path_to_appworkshop_acf}
        Example: {"270150": "/path/to/appworkshop_270150.acf", ...}
    """
    raise NotImplementedError("To be implemented in M1.1")
