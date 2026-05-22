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


def get_workshop_timeupdated(steamapps_path: str, appid: str, contentid: str | None = None) -> str:
    """从 appworkshop_{appid}.acf 读取 timeupdated 字段并返回字符串。

    ACF 文件位于 ``steamapps_path/workshop/`` 子目录下。

    若传入 contentid，则优先在 WorkshopItemsInstalled 和 WorkshopItemDetails
    中查找指定 contentid 的 timeupdated，找到即返回（不降级到其他策略）。

    若 contentid 为 None，使用原有策略（按优先级）:
    1. ``AppWorkshop.TimeLastUpdated`` 顶层时间戳
    2. ``AppWorkshop.WorkshopItemsInstalled.*.timeupdated``
    3. ``AppWorkshop.WorkshopItemDetails.*.timeupdated`` 取最大值

    若文件不存在或所有字段缺失 → 返回 "0"。

    Returns:
        timeupdated 的字符串（数字字符串），或 "0"
    """
    acf_path = Path(steamapps_path) / "workshop" / f"appworkshop_{appid}.acf"
    if not acf_path.exists():
        return "0"

    try:
        with open(acf_path, "r", encoding="utf-8") as f:
            data = vdf.load(f)
    except Exception:
        return "0"

    if not isinstance(data, dict):
        return "0"

    # Unwrap the top-level "AppWorkshop" key
    app_ws = data.get("AppWorkshop")
    if isinstance(app_ws, dict):
        ws_data = app_ws
    else:
        ws_data = data

    # If a specific contentid is requested, do targeted lookup first
    if contentid is not None:
        # WorkshopItemsInstalled -> contentid -> timeupdated
        try:
            installed = ws_data.get("WorkshopItemsInstalled")
            if isinstance(installed, dict):
                app_entry = installed.get(contentid)
                if isinstance(app_entry, dict):
                    tu = app_entry.get("timeupdated")
                    if tu is not None:
                        return str(tu)
        except (ValueError, TypeError):
            pass

        # WorkshopItemDetails -> contentid -> timeupdated (fallback)
        try:
            details = ws_data.get("WorkshopItemDetails")
            if isinstance(details, dict):
                entry = details.get(contentid)
                if isinstance(entry, dict):
                    tu = entry.get("timeupdated")
                    if tu is not None:
                        return str(tu)
        except (ValueError, TypeError):
            pass

        return "0"

    # ── contentid is None: use legacy multi-source strategy ──────────────
    timestamps: list[int] = []

    # 1. WorkshopItemsInstalled -> <appid> -> timeupdated
    try:
        installed = ws_data.get("WorkshopItemsInstalled")
        if isinstance(installed, dict):
            app_entry = installed.get(appid)
            if isinstance(app_entry, dict):
                tu = app_entry.get("timeupdated")
                if tu is not None:
                    timestamps.append(int(str(tu)))
    except (ValueError, TypeError):
        pass

    # 2. WorkshopItemDetails -> <index> -> timeupdated
    try:
        details = ws_data.get("WorkshopItemDetails")
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

    # 3. Fallback: top-level TimeLastUpdated (e.g. "1778139487")
    try:
        tlu = ws_data.get("TimeLastUpdated")
        if tlu is not None:
            return str(int(str(tlu)))
    except (ValueError, TypeError):
        pass

    return "0"


def get_workshop_latest_timeupdated(steamapps_path: str, appid: str, contentid: str) -> str:
    """从 appworkshop_{appid}.acf 读取特定 contentid 的 latest_timeupdated。

    读取 ``steamapps_path/workshop/appworkshop_{appid}.acf``，
    解包 AppWorkshop，查 WorkshopItemDetails.{contentid}.latest_timeupdated。

    Returns:
        latest_timeupdated 的字符串，或 "0"
    """
    acf_path = Path(steamapps_path) / "workshop" / f"appworkshop_{appid}.acf"
    if not acf_path.exists():
        return "0"

    try:
        with open(acf_path, "r", encoding="utf-8") as f:
            data = vdf.load(f)
    except Exception:
        return "0"

    if not isinstance(data, dict):
        return "0"

    app_ws = data.get("AppWorkshop")
    if not isinstance(app_ws, dict):
        return "0"

    details = app_ws.get("WorkshopItemDetails")
    if not isinstance(details, dict):
        return "0"

    entry = details.get(contentid)
    if not isinstance(entry, dict):
        return "0"

    ltu = entry.get("latest_timeupdated")
    if ltu is None:
        return "0"

    return str(ltu)


__all__ = [
    "parse_appmanifest_acf",
    "parse_appworkshop_acf",
    "find_appmanifest_acf_files",
    "find_appworkshop_acf_files",
    "get_workshop_timeupdated",
    "get_workshop_latest_timeupdated",
]
