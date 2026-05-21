"""backup_dir_builder.py — Automatic backup directory path derivation.

Provides functions to build a backup directory path from final_mapping,
database, and user_config, including workshop/custom backup ID generation
and .kmmignore rule loading.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .backup_ops import get_game_backup_id, get_workshop_timestamphex
from .paths import normalize_posix


def get_custom_backup_id(source_paths: list[str]) -> str:
    """对自定义 mod（无 ACF），取所有源文件的最新 mtime 转为 hex。

    遍历 source_paths，取 max(mtime) → hex。
    若路径均为空或不存在 → 返回当前时间的 hex。

    Returns:
        mtime 的小写 hex 字符串
    """
    max_mtime: int = 0
    now = int(time.time())

    for sp in source_paths:
        p = Path(sp)
        if p.exists():
            try:
                mtime = int(p.stat().st_mtime)
                if mtime > max_mtime:
                    max_mtime = mtime
            except OSError:
                continue

    if max_mtime == 0:
        return format(now, "x")

    return format(max_mtime, "x")


def build_backup_dirs(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
) -> tuple[dict[str, list[str]], list[str]]:
    """为 final_mapping 中的每个 app / contentid 构建各自的 backup_dir。

    每个 contentid 独立备份：在各自的根目录下创建 backup dir，
    backup_id 从对应的 ACF 文件获取。

    Args:
        final_mapping: mapping 条目列表，每项含 "path" 键
        database: 含 "game" 列表
        user_config: 含 "baksuffix" 等

    Returns:
        ({backup_dir: [file_paths]}, warnings)
        - backup_dir → 属于该目录的文件绝对路径列表
        - warnings: 稳定性检查中被跳过的 contentid 警告信息
    """
    baksuffix = str(user_config.get("baksuffix", "kmmbackup"))

    # ── 1. 收集所有目标路径 ──────────────────────────────────────────
    targets: list[str] = []
    for entry in final_mapping:
        p = entry.get("path")
        if p:
            targets.append(normalize_posix(str(p)))

    if not targets:
        raise ValueError("E_BACKUP_DIR_BUILD_NO_APPID: final_mapping has no paths")

    # ── 2. 构建 game_entries 索引 ─────────────────────────────────────
    games = database.get("game", [])
    game_entries: list[dict[str, Any]] = []
    for g in games:
        if not isinstance(g, dict):
            continue
        appid = str(g.get("appid", ""))
        if not appid:
            continue
        basepath = str(g.get("basepath", ""))
        modpath = str(g.get("modpath", ""))
        if basepath:
            basepath = normalize_posix(basepath)
        if modpath:
            modpath = normalize_posix(modpath)
        game_entries.append({
            "appid": appid,
            "basepath": basepath,
            "modpath": modpath,
        })

    # ── 3. 对每个 target，找到匹配的 game entry，分类 ──────────────────
    # app_hits: {appid: {basepath, files: [paths], steamapps_path}}
    # content_hits: {(appid, contentid): {modpath, contentid, files: [paths], steamapps_path}}
    from collections import defaultdict

    app_hits: dict[str, dict] = {}
    content_hits: dict[tuple[str, str], dict] = {}
    warnings: list[str] = []

    for target in targets:
        matched = False
        for ge in game_entries:
            # Check basepath (game app, modid==0)
            if ge["basepath"] and target.startswith(ge["basepath"]):
                appid = ge["appid"]
                if appid not in app_hits:
                    steamapps = normalize_posix(str(Path(ge["basepath"]).parent.parent))
                    app_hits[appid] = {
                        "basepath": ge["basepath"],
                        "files": [],
                        "steamapps_path": steamapps,
                    }
                app_hits[appid]["files"].append(target)
                matched = True
                break

            # Check modpath (workshop contentid)
            if ge["modpath"] and target.startswith(ge["modpath"]):
                # Extract contentid from path: .../content/{appid}/{contentid}/...
                appid = ge["appid"]
                rel = target[len(ge["modpath"]):].lstrip("/")
                parts = rel.split("/")
                contentid = parts[0] if parts else ""
                if contentid:
                    key = (appid, contentid)
                    if key not in content_hits:
                        steamapps = normalize_posix(str(Path(ge["modpath"]).parent.parent.parent))
                        content_hits[key] = {
                            "modpath": ge["modpath"],
                            "contentid": contentid,
                            "files": [],
                            "steamapps_path": steamapps,
                        }
                    content_hits[key]["files"].append(target)
                    matched = True
                    break

        if not matched:
            warnings.append(f"W_BACKUP_DIR_BUILD_NO_MATCH: {target}")

    # ── 4. 构建 backup_dirs ───────────────────────────────────────────
    result: dict[str, list[str]] = {}

    # App backups
    for appid, info in app_hits.items():
        ok, hex_id, err = get_game_backup_id(info["steamapps_path"], appid)
        if not ok:
            warnings.append(err)
            continue
        backup_dir = normalize_posix(
            f"{info['basepath']}/{appid}.{hex_id}.{baksuffix}/"
        )
        result[backup_dir] = info["files"]

    # Content backups
    for (appid, contentid), info in content_hits.items():
        ok, hex_id, err = get_workshop_timestamphex(
            info["steamapps_path"], appid, contentid
        )
        if not ok:
            warnings.append(err)
            continue
        backup_dir = normalize_posix(
            f"{info['modpath']}/{contentid}/{contentid}.{hex_id}.{baksuffix}/"
        )
        result[backup_dir] = info["files"]

    if not result:
        raise ValueError("E_BACKUP_DIR_BUILD_NO_APPID: no stable app/contentid found for backup")

    return result, warnings


# Keep old function as compatibility wrapper
def build_backup_dir(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
) -> str:
    """兼容旧接口：调用 build_backup_dirs 并返回第一个 backup_dir。"""
    dirs, _warnings = build_backup_dirs(final_mapping, database, user_config)
    return next(iter(dirs.keys()))


def load_dir_suffixes(user_config: dict[str, Any]) -> list[str]:
    """合并硬编码底线 + user_config.ignore，去重返回目录名后缀列表。

    硬编码底线 ``".kmmbackup"`` 始终在列表中。
    user_config.ignore 中的条目自动补前导 ``.``（若缺失）。
    """
    suffixes = [".kmmbackup"]
    config_ignore = user_config.get("ignore")
    if isinstance(config_ignore, list):
        for item in config_ignore:
            if isinstance(item, str) and item.strip():
                s = item.strip()
                if not s.startswith("."):
                    s = "." + s
                if s not in suffixes:
                    suffixes.append(s)
    return suffixes


__all__ = [
    "get_custom_backup_id",
    "get_workshop_timestamphex",
    "build_backup_dir",
    "build_backup_dirs",
    "load_dir_suffixes",
]
