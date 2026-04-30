#!/usr/bin/env python3
"""交互式森林可视化脚本 - 简单易用的人类交互界面"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_core_modules():
    """加载核心模块，支持本地 src 目录回退"""
    try:
        from modmanager.iojson import load_json_file
        from modmanager.forest_visual import visualize_payload, VisualizationError
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[1]
        src_dir = repo_root / "src"
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
        from modmanager.iojson import load_json_file
        from modmanager.forest_visual import visualize_payload, VisualizationError

    return load_json_file, visualize_payload, VisualizationError


def _list_available_forests() -> list[Path]:
    """列出当前目录下可用的 forest 文件"""
    examples_dir = Path(__file__).parent / "examples"
    
    # 如果 examples 目录不存在，返回空列表
    if not examples_dir.exists():
        return []
    
    # 查找所有 .json 文件
    json_files = sorted(examples_dir.glob("*.json"))
    return json_files


def _select_forest_file() -> Path | None:
    """交互式选择 forest 文件"""
    print("\n" + "=" * 60)
    print("🌲 森林可视化工具")
    print("=" * 60)
    
    available_forests = _list_available_forests()
    
    if not available_forests:
        print("\n❌ 未找到示例文件。请在 examples/ 目录中放置 .json 文件")
        return None
    
    print("\n📁 可用的森林文件：\n")
    for idx, forest_path in enumerate(available_forests, 1):
        print(f"  {idx}. {forest_path.name}")
    
    while True:
        try:
            choice = input(f"\n请选择文件编号 (1-{len(available_forests)})，或输入文件路径: ").strip()
            
            if not choice:
                print("❌ 输入不能为空")
                continue
            
            # 尝试作为数字索引
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(available_forests):
                    return available_forests[idx]
                else:
                    print(f"❌ 请输入 1 到 {len(available_forests)} 之间的数字")
                    continue
            except ValueError:
                # 作为文件路径处理
                path = Path(choice)
                if path.exists() and path.is_file():
                    return path
                else:
                    print(f"❌ 文件不存在: {choice}")
                    continue
        except KeyboardInterrupt:
            print("\n\n已取消")
            return None


def _select_format() -> str | None:
    """交互式选择输出格式"""
    formats = {
        "1": "ascii",
        "2": "dot",
        "3": "svg",
    }
    
    print("\n📊 选择输出格式：\n")
    print("  1. ASCII (纯文本树形结构)")
    print("  2. DOT (Graphviz 源代码)")
    print("  3. SVG (矢量图，需要 graphviz)")
    
    while True:
        choice = input(f"\n请选择格式 (1-3): ").strip()
        
        if choice in formats:
            return formats[choice]
        else:
            print("❌ 请输入 1、2 或 3")


def _select_output() -> Path | None:
    """交互式选择输出位置"""
    print("\n💾 输出选项：\n")
    print("  1. 显示在屏幕上")
    print("  2. 保存到文件")

    while True:
        choice = input(f"\n请选择 (1-2): ").strip()

        if choice == "1":
            return None  # None 表示输出到屏幕
        elif choice == "2":
            filename = input("输入输出文件名 (相对于当前目录): ").strip()
            if filename:
                return Path(filename)
            else:
                print("❌ 文件名不能为空")
                continue
        else:
            print("❌ 请输入 1 或 2")


def _select_detail_mode(default_on: bool = True) -> bool:
    """交互式选择是否展示 M1 详细字段。"""
    default_text = "y" if default_on else "n"
    raw = input(f"\n显示 M1 详细字段(action_order/provenance_ref/sidecar_ref)? [y/n, 默认 {default_text}]: ").strip().lower()
    if not raw:
        return default_on
    return raw in {"y", "yes", "1", "true"}


def main():
    """主交互循环"""
    load_json_file, visualize_payload, VisualizationError = _load_core_modules()
    
    while True:
        try:
            # 选择 forest 文件
            forest_path = _select_forest_file()
            if forest_path is None:
                break
            
            # 加载 forest 数据
            print(f"\n⏳ 加载 {forest_path.name}...")
            try:
                payload = load_json_file(str(forest_path))
            except Exception as exc:
                print(f"❌ 加载失败: {exc}")
                continue
            
            # 选择输出格式
            output_format = _select_format()
            if output_format is None:
                continue
            
            # 选择输出位置与展示模式
            output_path = _select_output()
            show_m1_details = _select_detail_mode(default_on=True)

            # 生成可视化
            print(f"\n⏳ 生成 {output_format.upper()} 可视化...")
            try:
                rendered = visualize_payload(payload, output_format, show_m1_details=show_m1_details)
            except VisualizationError as exc:
                print(f"❌ 可视化失败 (错误代码 {exc.code}): {exc}")
                continue
            except Exception as exc:
                print(f"❌ 可视化失败: {exc}")
                continue
            
            # 输出结果
            if output_path:
                try:
                    output_path.write_text(rendered, encoding="utf-8")
                    print(f"\n✅ 成功保存到: {output_path.absolute()}")
                except Exception as exc:
                    print(f"❌ 保存失败: {exc}")
                    continue
            else:
                print("\n" + "=" * 60)
                print(rendered)
                print("=" * 60)
            
            # 询问是否继续
            again = input("\n是否继续? (y/n, 默认 n): ").strip().lower()
            if again != "y":
                print("\n👋 再见！")
                break
            
        except KeyboardInterrupt:
            print("\n\n👋 再见！")
            break
        except Exception as exc:
            print(f"\n❌ 出错: {exc}")
            continue


if __name__ == "__main__":
    main()
