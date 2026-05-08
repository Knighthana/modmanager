#!/usr/bin/env python3
"""
modmanager_cli 测试 Fixture 生成器
从用户真实的 Windows Steam 游戏目录镜像生成 mock 测试环境。

两种模式:
  full  - 完整镜像目录结构，为每个文件生成轻量 mock
  hot   - 仅创建被 kmm_rule 实际引用的路径和文件，用于快速迭代

用法:
  python tools/generate_fixture.py full  -o OUTPUT_DIR [--clean]
  python tools/generate_fixture.py hot   -o OUTPUT_DIR [--clean]
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────────────────
SOURCE_ROOT = Path("/mnt/d/Games/steamapps/")
MANIFEST_PATH = Path(__file__).resolve().parent / "fixture_manifest.json"

# 子 mod ID 列表（hot 模式需要完整镜像全部文件）
HOT_SUBMOD_IDS = [
    "3425312546",
    "3426079135",
    "3427135267",
    "3428584891",
    "3430161019",
    "3430976333",
    "3435124100",
    "3437114999",
    "3442063538",
    "3442533598",
    "3445750210",
    "3470055515",
    "一点不战术地图v1.9 TEMP",
]

# 主 mod ID（hot 模式只建目录骨架 + 少量 mock）
MAIN_MOD_ID = "2606099273"

# 主 mod 中被 kmm_rule 的 "into" 引用的目标路径（相对于 mod 根）
# 这些目录下需要至少存在文件才能让替换操作成功
INTO_TARGET_DIRS = [
    "media/packages/GFL_Castling/",
    "media/packages/GFL_Castling/maps/",
    "media/packages/GFL_Castling/maps/1使用方法和图例/",
    "media/packages/GFL_Castling/maps/map105_3/",
    "media/packages/GFL_Castling/textures/",
    "media/packages/GFL_Castling/materials/",
    "media/packages/GFL_Castling/particles/",
    "media/packages/GFL_Castling/vehicles/",
    "media/packages/GFL_Castling/weapons/",
    "media/packages/GFL_Castling/sounds/",
    "media/packages/GFL_Castling/calls/",
]

# 在 into 目标目录中额外创建的 mock 文件
EXTRA_MOCK_FILES = [
    "media/packages/GFL_Castling/maps/map.png",
    "media/packages/GFL_Castling/maps/splash.png",
    "media/packages/GFL_Castling/textures/placeholder.png",
]

# 被 kmm_rule delete action 明确引用的文件（需存在，否则删除会失败）
DELETE_TARGET_FILES = [
    "media/packages/GFL_Castling/maps/map105_3/asphalt.png",
    "media/packages/GFL_Castling/maps/map105_3/dirt.png",
    "media/packages/GFL_Castling/maps/map105_3/road.png",
    "media/packages/GFL_Castling/maps/map105_3/sand.png",
]

# 被 kmm_rule into 引用的 lobby 路径
LOBBY_SOURCE = SOURCE_ROOT / "common/RunningWithRifles/media/packages/vanilla/maps/lobby"
LOBBY_DEST_REL = "steamapps/common/RunningWithRifles/media/packages/vanilla/maps/lobby"

# ACF 文件（复制原始内容）
ACF_FILES = [
    ("appmanifest_270150.acf", "steamapps/appmanifest_270150.acf"),
    ("workshop/appworkshop_270150.acf", "steamapps/workshop/appworkshop_270150.acf"),
]

# hot 模式额外包含的顶层文件（kmm_rule JSON 在 workshop content 根目录）
HOT_EXTRA_FILES_SRC = [
    "workshop/content/270150/kmm_rule_RWR-khn_CT-castears-z2414_Replace.json",
]

# 故意不创建的目录（测试缺失行为）
EXCLUDED_DIRS = {"warn_vehicles", "knighthana_custom_rules"}

# 媒体文件扩展名 — 这些生成 mock 文本即可
# 所有非 .acf / 非 kmm_rule*.json 的文件都生成文本 mock
COPY_ORIGINAL_EXTENSIONS = {".acf"}


# ── 工具函数 ──────────────────────────────────────────────────────────────

def is_kmm_rule_json(path: Path) -> bool:
    """判断是否为 kmm_rule JSON 文件（需要复制原始内容）。"""
    name = path.name
    return name.startswith("kmm_rule") and name.endswith(".json")


def should_copy_original(path: Path) -> bool:
    """判断文件是否需要复制原始内容（ACF / kmm_rule JSON）。"""
    return path.suffix.lower() in COPY_ORIGINAL_EXTENSIONS or is_kmm_rule_json(path)


def mock_content(rel_path: str) -> str:
    """生成 mock 文本内容。"""
    return f"[PRE-REPLACE] {rel_path}\n"


def ensure_dir(directory: Path) -> None:
    """确保目录存在。"""
    directory.mkdir(parents=True, exist_ok=True)


def clean_output(output_dir: Path) -> None:
    """清空输出目录。"""
    if output_dir.exists():
        print(f"  清理现有输出目录: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def copy_file_with_original_content(src: Path, dst: Path) -> None:
    """复制文件原始内容。"""
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def write_mock_file(dst: Path, rel_path: str) -> None:
    """写入 mock 文本文件。"""
    ensure_dir(dst.parent)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(mock_content(rel_path))


def collect_all_subdirs(root: Path) -> set:
    """收集 root 下所有子目录的相对路径集合。"""
    dirs = set()
    for dirpath, dirnames, _ in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if rel != Path("."):
            dirs.add(str(rel))
        for d in dirnames:
            full_d = Path(dirpath) / d
            rel_d = full_d.relative_to(root)
            dirs.add(str(rel_d))
    return dirs


def collect_all_files(root: Path) -> list:
    """收集 root 下所有文件的相对路径列表。"""
    files = []
    for dirpath, _, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root)
        for fn in filenames:
            rel_file = rel_dir / fn
            files.append(str(rel_file))
    return files


def print_stats(output_dir: Path, elapsed: float) -> None:
    """打印生成统计信息。"""
    file_count = 0
    dir_count = 0
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(output_dir):
        dir_count += 1
        for fn in filenames:
            file_count += 1
            fp = Path(dirpath) / fn
            try:
                total_size += fp.stat().st_size
            except OSError:
                pass

    print()
    print(f"  ✅ 生成完成!")
    print(f"  📂 输出目录: {output_dir}")
    print(f"  📄 文件数:   {file_count}")
    print(f"  📁 目录数:   {dir_count}")
    print(f"  💾 总大小:   {total_size / 1024:.1f} KB")
    print(f"  ⏱  耗时:    {elapsed:.2f} 秒")


# ── 核心生成逻辑 ──────────────────────────────────────────────────────────

def validate_source() -> None:
    """验证源路径是否可访问。"""
    if not SOURCE_ROOT.exists():
        print(f"❌ 错误: 源路径不可访问: {SOURCE_ROOT}")
        print("   请确保已在 WSL 中挂载 /mnt/d/")
        sys.exit(1)
    if not (SOURCE_ROOT / "workshop/content/270150").exists():
        print(f"❌ 错误: 找不到 workshop/content/270150 目录")
        sys.exit(1)


def mode_full(output_dir: Path, clean: bool) -> None:
    """
    full 模式：完整镜像 workshop/content/270150/ 下所有文件。
    - .acf / kmm_rule*.json → 复制原始内容
    - 其他所有文件 → 生成 mock 文本
    - 顶层 ACF 文件 → 复制原始内容
    - lobby 文件 → 复制原始内容（供 bluearchive_titlescreen 规则使用）
    """
    print("=" * 60)
    print("  🏗️  full 模式：完整镜像目录结构")
    print("=" * 60)

    if clean:
        clean_output(output_dir)
    else:
        ensure_dir(output_dir)

    workshop_root = SOURCE_ROOT / "workshop/content/270150"
    total_files = 0

    # ── 1. 复制顶层 ACF 文件 ──
    print("\n  📋 复制 ACF 文件...")
    for src_rel, dst_rel in ACF_FILES:
        src = SOURCE_ROOT / src_rel
        dst = output_dir / dst_rel
        if src.exists():
            copy_file_with_original_content(src, dst)
            total_files += 1
            print(f"    ✅ {src_rel}")

    # ── 2. 遍历 workshop/content/270150/ ──
    print(f"\n  📂 遍历 {workshop_root} ...")
    processed = 0
    for dirpath, dirnames, filenames in os.walk(workshop_root):
        rel_dir = Path(dirpath).relative_to(workshop_root)

        # 跳过被排除的目录
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

        for fn in filenames:
            src_file = Path(dirpath) / fn
            rel_file = rel_dir / fn
            dst_file = output_dir / "steamapps/workshop/content/270150" / rel_file

            if should_copy_original(src_file):
                copy_file_with_original_content(src_file, dst_file)
            else:
                mock_rel = f"steamapps/workshop/content/270150/{rel_file}"
                write_mock_file(dst_file, mock_rel)

            processed += 1
            if processed % 2000 == 0:
                print(f"    ... 已处理 {processed} 个文件")

    total_files += processed

    # ── 3. 复制 lobby 原始文件 ──
    if LOBBY_SOURCE.exists():
        print(f"\n  📂 复制 lobby 文件 (原始内容) ...")
        lobby_count = 0
        for dirpath, dirnames, filenames in os.walk(LOBBY_SOURCE):
            rel_dir = Path(dirpath).relative_to(LOBBY_SOURCE)
            for fn in filenames:
                src_file = Path(dirpath) / fn
                dst_file = output_dir / LOBBY_DEST_REL / rel_dir / fn
                copy_file_with_original_content(src_file, dst_file)
                lobby_count += 1
        total_files += lobby_count
        print(f"    ✅ 已复制 {lobby_count} 个 lobby 文件")
    else:
        print(f"    ⚠️  lobby 目录不存在，跳过: {LOBBY_SOURCE}")


def mode_hot(output_dir: Path, clean: bool) -> None:
    """
    hot 模式：仅创建被 kmm_rule 实际引用的路径和文件。
    - 全部子 mod → 完整 mock 镜像
    - 主 mod (2606099273) → 目录骨架 + into 目标下的 mock
    - ACF → 复制原始内容
    - lobby → 复制原始内容
    - 故意不创建: warn_vehicles, knighthana_custom_rules
    """
    print("=" * 60)
    print("  🔥 hot 模式：仅创建 kmm_rule 引用的路径")
    print("=" * 60)

    if clean:
        clean_output(output_dir)
    else:
        ensure_dir(output_dir)

    workshop_root = SOURCE_ROOT / "workshop/content/270150"
    total_files = 0

    # ── 1. 复制 ACF 文件 ──
    print("\n  📋 复制 ACF 文件...")
    for src_rel, dst_rel in ACF_FILES:
        src = SOURCE_ROOT / src_rel
        dst = output_dir / dst_rel
        if src.exists():
            copy_file_with_original_content(src, dst)
            total_files += 1
            print(f"    ✅ {src_rel}")
        else:
            print(f"    ⚠️  ACF 不存在，跳过: {src_rel}")

    # ── 2. 全部子 mod → 完整 mock 镜像 ──
    print(f"\n  📦 镜像子 mod 文件 ({len(HOT_SUBMOD_IDS)} 个 mod)...")
    submod_files = 0
    for mod_id in HOT_SUBMOD_IDS:
        mod_src = workshop_root / mod_id
        if not mod_src.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(mod_src):
            rel_dir = Path(dirpath).relative_to(mod_src)
            for fn in filenames:
                src_file = Path(dirpath) / fn
                rel_file = rel_dir / fn
                dst_file = output_dir / "steamapps/workshop/content/270150" / mod_id / rel_file

                if should_copy_original(src_file):
                    copy_file_with_original_content(src_file, dst_file)
                else:
                    mock_rel = f"steamapps/workshop/content/270150/{mod_id}/{rel_file}"
                    write_mock_file(dst_file, mock_rel)

                submod_files += 1
        print(f"    ✅ {mod_id}")

    total_files += submod_files
    print(f"    ✅ 子 mod 共 {submod_files} 个文件")

    # ── 2b. 额外顶层文件（如 kmm_rule JSON） ──
    extra_files_copied = 0
    for extra_rel in HOT_EXTRA_FILES_SRC:
        extra_src = SOURCE_ROOT / extra_rel
        if extra_src.exists():
            dst_file = output_dir / "steamapps" / extra_rel
            copy_file_with_original_content(extra_src, dst_file)
            extra_files_copied += 1
            print(f"    ✅ 额外文件: {extra_rel}")
    total_files += extra_files_copied

    # ── 3. 主 mod → 目录骨架 + into 目标 mock ──
    print(f"\n  🏗️  构建主 mod ({MAIN_MOD_ID}) 目录骨架...")
    main_src = workshop_root / MAIN_MOD_ID
    main_dst_base = output_dir / "steamapps/workshop/content/270150" / MAIN_MOD_ID

    if not main_src.exists():
        print(f"    ⚠️  主 mod 目录不存在，跳过: {MAIN_MOD_ID}")
    else:
        # 3a. 收集所有子目录并创建
        print(f"    扫描目录结构...")
        all_dirs = collect_all_subdirs(main_src)
        for d in sorted(all_dirs):
            ensure_dir(main_dst_base / d)
        print(f"    ✅ 创建了 {len(all_dirs)} 个目录")

        # 3b. 在 into 目标目录中创建 placeholder mock 文件
        #     确保替换操作有目标文件可覆盖
        mainmod_files = 0
        for target_dir in INTO_TARGET_DIRS:
            # 在目标目录中创建一个 placeholder
            placeholder_rel = f"{target_dir}.fixture_placeholder"
            dst_file = main_dst_base / placeholder_rel
            mock_rel = f"steamapps/workshop/content/270150/{MAIN_MOD_ID}/{placeholder_rel}"
            write_mock_file(dst_file, mock_rel)
            mainmod_files += 1

        # 3c. 创建被 delete action 引用的具体文件
        for file_rel in DELETE_TARGET_FILES:
            dst_file = main_dst_base / file_rel
            mock_rel = f"steamapps/workshop/content/270150/{MAIN_MOD_ID}/{file_rel}"
            write_mock_file(dst_file, mock_rel)
            mainmod_files += 1

        # 3d. 创建额外代表文件
        for file_rel in EXTRA_MOCK_FILES:
            dst_file = main_dst_base / file_rel
            mock_rel = f"steamapps/workshop/content/270150/{MAIN_MOD_ID}/{file_rel}"
            write_mock_file(dst_file, mock_rel)
            mainmod_files += 1

        total_files += mainmod_files
        print(f"    ✅ 主 mod mock 文件: {mainmod_files} 个")

    # ── 4. 复制 lobby 原始文件 ──
    if LOBBY_SOURCE.exists():
        print(f"\n  📂 复制 lobby 文件 (原始内容) ...")
        lobby_count = 0
        for dirpath, dirnames, filenames in os.walk(LOBBY_SOURCE):
            rel_dir = Path(dirpath).relative_to(LOBBY_SOURCE)
            for fn in filenames:
                src_file = Path(dirpath) / fn
                dst_file = output_dir / LOBBY_DEST_REL / rel_dir / fn
                copy_file_with_original_content(src_file, dst_file)
                lobby_count += 1
        total_files += lobby_count
        print(f"    ✅ 已复制 {lobby_count} 个 lobby 文件")
    else:
        print(f"    ⚠️  lobby 目录不存在，跳过: {LOBBY_SOURCE}")


# ── CLI 入口 ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="modmanager_cli 测试 Fixture 生成器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
 模式说明:
   full  完整镜像目录结构，为每个文件生成轻量 mock（文本内容）
   hot   仅创建被 kmm_rule 实际引用的路径和文件，用于快速迭代

 用法示例:
   python tools/generate_fixture.py full  -o /tmp/kmm_fixture --clean
   python tools/generate_fixture.py hot   -o /tmp/kmm_fixture --clean
   python tools/generate_fixture.py hot   -o /tmp/kmm_fixture --with-db
        """,
    )
    parser.add_argument(
        "mode",
        choices=["full", "hot"],
        help="生成模式",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="输出目录路径",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="生成前清空输出目录",
    )
    parser.add_argument(
        "--with-db",
        action="store_true",
        help="生成后自动调用 generate_database 并写入 database.json",
    )

    args = parser.parse_args()

    # 验证源路径
    validate_source()

    # 加载 manifest 信息（用于校验）
    if MANIFEST_PATH.exists():
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            print(f"📋 配置文件: {MANIFEST_PATH}")
            print(f"   版本: {manifest.get('schema_version', 'N/A')}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  配置文件读取失败: {e}")
    else:
        print(f"⚠️  找不到配置文件: {MANIFEST_PATH}")

    output_dir = args.output.resolve()
    print(f"🎯 输出目录: {output_dir}")

    start = time.time()

    if args.mode == "full":
        mode_full(output_dir, args.clean)
    else:
        mode_hot(output_dir, args.clean)

    elapsed = time.time() - start
    print_stats(output_dir, elapsed)

    # ── --with-db: 生成 database.json ──────────────────────────────────────
    if args.with_db:
        print("\n" + "=" * 60)
        print("  📊 生成数据库 (--with-db)")
        print("=" * 60)

        output_steamapps_dir = str(output_dir / "steamapps")
        from modmanager.bootstrap import generate_database
        from modmanager.iojson import write_json_file

        db = generate_database(
            "manual",
            paths=[output_steamapps_dir],
            greedy_parsing=True,
        )
        db_path = output_dir / "database.json"
        write_json_file(db_path, db)
        print(f'  📊 数据库已生成: {db_path}')
        print(f'     Games: {len(db.get("game", []))} | Mods: {len(db.get("mod", []))}')


if __name__ == "__main__":
    main()
