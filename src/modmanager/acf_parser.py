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


def get_workshop_timeupdated(steamapps_path: str, appid: str) -> str:
    """从 appworkshop_{appid}.acf 读取 timeupdated 字段并返回字符串。

    appworkshop ACF 的结构（实际格式可能因 Steam 版本而异，需兼容两种）：
    格式A（键值对在顶层）:
      "WorkshopItemsInstalled" {
          "<appid>" {
              "timeupdated" "1234567890"
          }
      }
    格式B（键值对嵌套在子项中）:
      "WorkshopItemDetails" {
          "0" {
              "publishedfileid" "..."
              "timeupdated" "1234567890"
          }
      }

    需要检查这两种结构。若文件不存在或 timeupdated 缺失 → 返回 "0"。

    Returns:
        timeupdated 的字符串（数字字符串），或 "0"
    """
    acf_path = Path(steamapps_path) / f"appworkshop_{appid}.acf"
    if not acf_path.exists():
        return "0"

    try:
        with open(acf_path, "r", encoding="utf-8") as f:
            data = vdf.load(f)
    except Exception:
        return "0"

    if not isinstance(data, dict):
        return "0"

    timestamps: list[int] = []

    # 格式A：WorkshopItemsInstalled -> <appid> -> timeupdated
    try:
        installed = data.get("WorkshopItemsInstalled")
        if isinstance(installed, dict):
            app_entry = installed.get(appid)
            if isinstance(app_entry, dict):
                tu = app_entry.get("timeupdated")
                if tu is not None:
                    timestamps.append(int(str(tu)))
    except (ValueError, TypeError):
        pass

    # 格式B：WorkshopItemDetails -> <index> -> timeupdated
    try:
        details = data.get("WorkshopItemDetails")
        if isinstance(details, dict):
            for _key, entry in details.items():
                if isinstance(entry, dict):
                    tu = entry.get("timeupdated")
                    if tu is not None:
                        timestamps.append(int(str(tu)))
    except (ValueError, TypeError):
        pass

    if timestamps:
        return str(max(timestamps))
    return "0"


__all__ = [
    "parse_appmanifest_acf",
    "parse_appworkshop_acf",
    "find_appmanifest_acf_files",
    "find_appworkshop_acf_files",
    "get_workshop_timeupdated",
]
