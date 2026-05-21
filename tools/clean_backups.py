#!/usr/bin/env python3
"""清理 steamapps 下所有 mod 目录中的 kmmbackup 目录。

用法:
    python tools/clean_backups.py /path/to/steamapps [--dry-run]

在 steamapps/workshop/content/{appid}/{contentid}/ 下递归查找
所有以 .kmmbackup 结尾的目录并删除。
"""

import argparse
import os
import shutil
import sys
from pathlib import Path


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
    parser.add_argument("steamapps", help="steamapps 目录路径")
    parser.add_argument("--dry-run", "-n", action="store_true", help="只列出，不删除")
    args = parser.parse_args()

    root = Path(args.steamapps)
    if not root.is_dir():
        print(f"错误: 目录不存在 — {root}", file=sys.stderr)
        sys.exit(1)

    backups = find_backup_dirs(root)
    if not backups:
        print("未找到任何 .kmmbackup 目录")
        return

    for d in backups:
        if args.dry_run:
            print(f"[dry-run] 将删除: {d}")
        else:
            try:
                shutil.rmtree(str(d))
                print(f"已删除: {d}")
            except OSError as exc:
                print(f"删除失败: {d} — {exc}", file=sys.stderr)

    print(f"\n{'[dry-run] ' if args.dry_run else ''}共 {len(backups)} 个目录")


if __name__ == "__main__":
    main()
