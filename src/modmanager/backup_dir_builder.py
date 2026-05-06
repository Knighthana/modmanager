"""backup_dir_builder.py — Automatic backup directory path derivation.

Provides functions to build a backup directory path from final_mapping,
database, and user_config, including workshop/custom backup ID generation
and .kmmbakignore rule loading.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from .backup_ops import get_game_backup_id, get_workshop_backup_id
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


def build_backup_dir(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
) -> str:
    """自动推导 backup_dir 路径。

    算法：
    1. 读取 bakprefix（默认 "kmmbackup_"）
    2. 收集 final_mapping 中所有目标路径（entry["path"]）
    3. 对每个目标路径，在 database["game"] 中匹配：
       - 若目标路径以 game["basepath"] 开头 → 标记为 common 区域
       - 若目标路径以 game["modpath"] 开头 → 标记为 workshop 区域
    4. 统计各 appid 命中的目标数，选最多的
    5. 根据区域选 backup_id 源：
       - common → get_game_backup_id(steamlib_path, appid)
       - workshop → get_workshop_backup_id(steamapps_path, appid)
    6. 拼接路径（绝对路径）：
       - common: basepath目录 + "/" + bakprefix + appid + "_" + hex + "/"
       - workshop: modpath目录下 + "/" + bakprefix + appid + "_" + hex + "/"
    7. 若无法匹配 appid → raise ValueError("E_BACKUP_DIR_BUILD_NO_APPID")

    Args:
        final_mapping: final_mapping 列表，每项含 "path" 键
        database: 含 "game" 列表，每项含 "appid", "basepath", "modpath"
        user_config: 用户配置，可含 "bakprefix"

    Returns:
        备份目录的绝对路径字符串

    Raises:
        ValueError: 无法匹配 appid
    """
    bakprefix = str(user_config.get("bakprefix", "kmmbackup_"))

    # 2. 收集所有目标路径
    targets: list[str] = []
    for entry in final_mapping:
        p = entry.get("path")
        if p:
            targets.append(normalize_posix(str(p)))

    if not targets:
        raise ValueError("E_BACKUP_DIR_BUILD_NO_APPID: final_mapping has no paths")

    # 3-4. 统计各 (appid, region) 匹配数
    from collections import Counter

    pair_counts: Counter[tuple[str, str]] = Counter()  # (appid, region)

    games = database.get("game", [])
    # Normalize game paths once
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
        game_entries.append({"appid": appid, "basepath": basepath, "modpath": modpath, "orig": g})

    for target in targets:
        for ge in game_entries:
            if ge["basepath"] and target.startswith(ge["basepath"]):
                pair_counts[(ge["appid"], "common")] += 1
            elif ge["modpath"] and target.startswith(ge["modpath"]):
                pair_counts[(ge["appid"], "workshop")] += 1

    if not pair_counts:
        raise ValueError("E_BACKUP_DIR_BUILD_NO_APPID: no matching game entry")

    # 5. 选最多的 (appid, region)
    (best_appid, best_region), _best_count = pair_counts.most_common(1)[0]

    # Find matching original game entry
    game_entry: dict[str, Any] | None = None
    for ge in game_entries:
        if ge["appid"] == best_appid:
            game_entry = ge["orig"]
            break

    if game_entry is None:
        raise ValueError(f"E_BACKUP_DIR_BUILD_NO_APPID: appid {best_appid} not found")

    # Derive steamapps path and build backup_id + directory path
    if best_region == "common":
        basepath = str(game_entry.get("basepath", ""))
        if not basepath:
            raise ValueError(f"E_BACKUP_DIR_BUILD_NO_APPID: common appid {best_appid} has no basepath")
        basepath_norm = normalize_posix(basepath)
        steamapps = normalize_posix(str(Path(basepath_norm).parent.parent))
        backup_id = get_game_backup_id(steamapps, best_appid)
        backup_dir = f"{basepath_norm}/{bakprefix}{best_appid}_{backup_id}/"
    else:
        modpath = str(game_entry.get("modpath", ""))
        if not modpath:
            raise ValueError(f"E_BACKUP_DIR_BUILD_NO_APPID: workshop appid {best_appid} has no modpath")
        modpath_norm = normalize_posix(modpath)
        steamapps = normalize_posix(str(Path(modpath_norm).parent.parent.parent))
        backup_id = get_workshop_backup_id(steamapps, best_appid)
        backup_dir = f"{modpath_norm}/{bakprefix}{best_appid}_{backup_id}/"

    return normalize_posix(backup_dir)


def load_bakignore_rules(
    user_config: dict[str, Any],
    backup_dir: str,
) -> list[str]:
    """合并 user_config.bakignore 与 .kmmbakignore。

    1. 从 user_config 读 bakignore（list[str]），默认 ["kmmbackup_"]
    2. 检查 backup_dir / ".kmmbakignore" 是否存在
    3. 若存在，逐行读取：跳过空行和 # 开头的行（strip 后），其余加入列表
    4. 合并去重，返回规则列表

    Args:
        user_config: 用户配置字典，可含 "bakignore" 列表
        backup_dir: 备份目录路径

    Returns:
        合并后的规则列表（去重）
    """
    rules: list[str] = []

    # 1. 从 user_config 读取
    config_ignore = user_config.get("bakignore")
    if isinstance(config_ignore, list):
        for item in config_ignore:
            if isinstance(item, str) and item.strip():
                rules.append(item.strip())
    if not rules:
        rules.append("kmmbackup_")

    # 2-3. 从 .kmmbakignore 文件读取
    ignore_file = Path(backup_dir) / ".kmmbakignore"
    if ignore_file.exists():
        try:
            with open(ignore_file, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    rules.append(stripped)
        except OSError:
            pass

    # 4. 合并去重（保持顺序）
    seen: set[str] = set()
    deduped: list[str] = []
    for r in rules:
        if r not in seen:
            seen.add(r)
            deduped.append(r)

    return deduped


__all__ = [
    "get_custom_backup_id",
    "get_workshop_backup_id",
    "build_backup_dir",
    "load_bakignore_rules",
]
