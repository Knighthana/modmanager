#!/usr/bin/env python3
"""清理 steamapps 下所有 mod 目录中的 kmmbackup 目录。

用法:
    python tools/clean_backups.py [--config tools/clean_backups.example.json] [--dry-run]

如果提供了 --config，从 JSON 文件中读取 steamapps 路径列表。
否则需要直接在命令行指定 steamapps 路径。
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def load_targets(config_path: str | None) -> list[str]:
    """从配置文件或命令行读取目标路径列表。

    配置文件格式 (JSON):
        {"steamapps_paths": ["/path/to/steamapps1", "/path/to/steamapps2"]}
    """
    if config_path is None:
        return []

    with open(config_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("steamapps_paths", [])


def find_backup_dirs(root: Path) -> list[Path]:
    """在 workshop/content 下递归查找所有 *.kmmbackup 目录。"""
    workshop = root / "workshop" / "content"
    if not workshop.is_dir():
        print(f"未找到 workshop/content 目录: {workshop}")
        return []

    results: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(str(workshop)):
        for d in dirnames:
            if d.endswith(".kmmbackup"):
                results.append(Path(dirpath) / d)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 steamapps 下所有 kmmbackup 目录")
    parser.add_argument("steamapps", nargs="?", help="steamapps 目录路径")
    parser.add_argument("--config", help="JSON 配置文件 (含 steamapps_paths 列表)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="只列出，不删除")
    args = parser.parse_args()

    targets = load_targets(args.config)
    if args.steamapps:
        targets.append(args.steamapps)

    if not targets:
        print("错误: 请指定 steamapps 路径或提供 --config", file=sys.stderr)
        sys.exit(1)

    total = 0
    for target in targets:
        root = Path(target)
        if not root.is_dir():
            print(f"错误: 目录不存在 — {root}", file=sys.stderr)
            continue

        backups = find_backup_dirs(root)
        if not backups:
            print(f"({root}) 未找到任何 .kmmbackup 目录")
            continue

        for d in backups:
            if args.dry_run:
                print(f"[dry-run] 将删除: {d}")
            else:
                try:
                    shutil.rmtree(str(d))
                    print(f"已删除: {d}")
                except OSError as exc:
                    print(f"删除失败: {d} — {exc}", file=sys.stderr)

        total += len(backups)

    print(f"\n{'[dry-run] ' if args.dry_run else ''}共 {total} 个目录")


if __name__ == "__main__":
    main()
