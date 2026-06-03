"""Tests for .kmmignore lifecycle — 原地规则（in-place），不搬动。

黑箱测试 — 通过公开 API 验证行为，不检查源码实现。

SPEC: repo_test/kmmignore_lifecycle.md
Decision: 2026-06-03 — .kmmignore 始终原地生效，不随 backup/restore 移动。

验证:
- T-KI-07: plan_fileops() 从源目录读取 .kmmignore（过滤生效）
- T-KI-08/09: plan_fileops() 排除被 ignore 的文件 + 产出 ignore_rule_set 缓存
- T-KI-10: 源目录无 .kmmignore → 不报错
- T-KI-11: backup 后 backup_dir 不含 .kmmignore
- T-KI-12: restore 后源目录 .kmmignore 不变
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from modmgr.orchestrator.entry import Intent, TaskRequest
from modmgr.orchestrator.fileops.planner.planner import plan_fileops
from modmgr.orchestrator.fileops.planner.ignore_rules import IgnoreRuleSet

# ── Fixture constants ──────────────────────────────────────────────────

APPID = "270150"
CONTENTID = "2606099273"


def _build_steam_fixture(root: Path) -> None:
    """Create a minimal Steam workshop fixture with ACF files on disk."""
    steamapps = root / "steamapps"
    common = steamapps / "common" / "RunningWithRifles"
    mod = steamapps / "workshop" / "content" / APPID / CONTENTID
    common.mkdir(parents=True)
    mod.mkdir(parents=True)

    (mod / "test_mod_file.txt").write_text("content")
    (mod / "data.bin").write_text("binary")

    (steamapps / f"appmanifest_{APPID}.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"' + APPID + '"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"22924257"\n}\n'
    )

    ws_dir = steamapps / "workshop"
    ws_dir.mkdir(exist_ok=True)
    (ws_dir / f"appworkshop_{APPID}.acf").write_text(
        '"AppWorkshop"\n{\n\t"WorkshopItemsInstalled"\n\t{\n'
        '\t\t"' + CONTENTID + '"\n\t\t{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t}\n\t"WorkshopItemDetails"\n\t{\n'
        '\t\t"' + CONTENTID + '"\n\t\t{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t}\n}'
    )


def _make_database(root: Path) -> dict:
    return {
        "schema_namespace": "KMM_Database",
        "schema_version": "knighthana@0.1.0",
        "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
        "steamlib": [{"path": str(root) + "/", "contains_libraryfolders_vdf": False}],
        "game": [{
            "appid": APPID,
            "name": "RunningWithRifles",
            "basepath": str(root / "steamapps" / "common" / "RunningWithRifles") + "/",
            "modpath": str(root / "steamapps" / "workshop" / "content" / APPID) + "/",
            "mods_found": [CONTENTID],
        }],
        "mod": [
            {
                "mixed_id": f"{APPID}:{CONTENTID}",
                "path": str(root / "steamapps" / "workshop" / "content" / APPID / CONTENTID) + "/",
            },
        ],
        "history": [],
    }


def _make_context(root: Path, final_mapping: list[dict]) -> dict:
    """Construct a data dict for plan_fileops()."""
    return {
        "final_mapping": final_mapping,
        "database": _make_database(root),
        "user_config": {"baksuffix": "kmmbackup"},
    }


def _make_request(intent: Intent = Intent.BACKUP) -> TaskRequest:
    return TaskRequest(
        identity="cli",
        intent=intent,
        resolver_type="raw_dict",
        resolver_args={},
        flags={"dry_run": True},
    )


def _all_paths(plan) -> set[str]:
    """Extract all paths from a FileOpsPlan's entries_by_backup_dir."""
    paths = set()
    for entries in plan.entries_by_backup_dir.values():
        for entry in entries:
            paths.add(entry.get("path", ""))
    return paths


# ═══════════════════════════════════════════════════════════════════════
# T-KI-07: plan_fileops() 从源目录读取 .kmmignore（过滤生效）
# ═══════════════════════════════════════════════════════════════════════

class TestKmmignoreInPlaceFiltering:
    """T-KI-07 / T-KI-08: kmmignore 从源目录原地读取并过滤，被忽略的文件不出现在 plan 中。"""

    def test_ignored_files_excluded_from_plan(self) -> None:
        """被 .kmmignore 忽略的文件不出现在 entries_by_backup_dir 中。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            (game_root / ".kmmignore").write_text("*.log\nbuild/\n")
            (game_root / "debug.log").write_text("logs")
            (game_root / "build").mkdir()
            (game_root / "build" / "output.o").write_text("obj")

            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "data.bin"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "debug.log"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "build" / "output.o"), "game_name": "RunningWithRifles"},
            ]

            context = _make_context(root, final_mapping)
            request = _make_request(Intent.BACKUP)
            plan = plan_fileops(request, context)
            paths = _all_paths(plan)

            assert any("game.bin" in p for p in paths), "game.bin 不应被过滤"
            assert any("data.bin" in p for p in paths), "data.bin 不应被过滤"
            assert not any("debug.log" in p for p in paths), "debug.log 应被 *.log 过滤"
            assert not any("output.o" in p for p in paths), "output.o 应被 build/ 过滤"

    def test_no_kmmignore_no_error(self) -> None:
        """源目录无 .kmmignore → 不报错，过滤结果为空。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "data.bin"), "game_name": "RunningWithRifles"},
            ]

            context = _make_context(root, final_mapping)
            request = _make_request(Intent.BACKUP)
            plan = plan_fileops(request, context)
            paths = _all_paths(plan)

            assert any("game.bin" in p for p in paths)
            assert any("data.bin" in p for p in paths)


# ═══════════════════════════════════════════════════════════════════════
# T-KI-09: plan_fileops() 输出含 ignore_rule_set 缓存
# ═══════════════════════════════════════════════════════════════════════

class TestIgnoreRuleSetCache:
    """T-KI-09: plan_fileops() 的 ignore_rule_set 可供原语消费。"""

    def test_plan_contains_ignore_rule_set(self) -> None:
        """有 .kmmignore 时 ignore_rules 缓存非空。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            (game_root / ".kmmignore").write_text("*.txt\n")

            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
            ]

            context = _make_context(root, final_mapping)
            request = _make_request(Intent.BACKUP)
            plan = plan_fileops(request, context)

            assert isinstance(plan.ignore_rules, IgnoreRuleSet)
            assert len(plan.ignore_rules.gitignore_rules) > 0, (
                "有 .kmmignore 时 ignore_rule_set 应为非空"
            )

    def test_empty_ignore_set_when_no_kmmignore(self) -> None:
        """无 .kmmignore 时 ignore_rules 为空缓存。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
            ]

            context = _make_context(root, final_mapping)
            request = _make_request(Intent.BACKUP)
            plan = plan_fileops(request, context)

            assert isinstance(plan.ignore_rules, IgnoreRuleSet)
            assert len(plan.ignore_rules.gitignore_rules) == 0, (
                "无 .kmmignore 时 ignore_rule_set 应为空"
            )


# ═══════════════════════════════════════════════════════════════════════
# T-KI-11: backup 操作不搬动 .kmmignore → backup_dir 不含该文件
# ═══════════════════════════════════════════════════════════════════════

class TestKmmignoreNotCopiedToBackup:
    """T-KI-11: backup 后 backup_dir 不含 .kmmignore 文件。

    黑箱验证：通过公众 API plan_fileops() 检查组装的 backup 条目中
    不含 .kmmignore。实际文件操作由原语完成，此测试验证 Planner 不会
    把 .kmmignore 加入备份清单。
    """

    def test_backup_plan_excludes_kmmignore_files(self) -> None:
        """plan_fileops 的 entries_by_backup_dir 不含 .kmmignore 条目。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            (game_root / ".kmmignore").write_text("*.log\n")

            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
            ]

            context = _make_context(root, final_mapping)
            request = _make_request(Intent.BACKUP)
            plan = plan_fileops(request, context)
            paths = _all_paths(plan)

            # .kmmignore 本身不应出现在备份条目中
            kmmignore_in_plan = any(".kmmignore" in p for p in paths)
            assert not kmmignore_in_plan, (
                ".kmmignore 不应出现在备份 plan 的条目列表中（原地规则）"
            )


# ═══════════════════════════════════════════════════════════════════════
# T-KI-12: restore 操作不恢复 .kmmignore → 源目录文件不变
# ═══════════════════════════════════════════════════════════════════════

class TestKmmignoreNotRestored:
    """T-KI-12: restore 后源目录 .kmmignore 不被覆盖/还原。

    黑箱验证：通过 plan_fileops(restore) 检查组装的 restore 条目中
    是否包含 .kmmignore。若不含，原语不会操作该文件。
    """

    def test_restore_plan_excludes_kmmignore_files(self) -> None:
        """restore plan 不含从 backup_dir 还原 .kmmignore 的条目。"""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            (game_root / ".kmmignore").write_text("*.log\n")

            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
            ]

            context = _make_context(root, final_mapping)
            request = _make_request(Intent.RESTORE)
            plan = plan_fileops(request, context)
            paths = _all_paths(plan)

            kmmignore_in_plan = any(".kmmignore" in p for p in paths)
            assert not kmmignore_in_plan, (
                "restore plan 不应包含 .kmmignore 条目（原地规则）"
            )


# ═══════════════════════════════════════════════════════════════════════
# T-KI-05/06 等价验证：原语对 .kmmignore 无感知
# ═══════════════════════════════════════════════════════════════════════

class TestPrimitivesKmmignoreUnaware:
    """原语不感知 .kmmignore — 行为等价于不 import 该文件。

    黑箱验证：原语（backup_ops, restore_ops）的公开接口不应包含
    任何 .kmmignore 相关参数或行为。调用它们的正常路径不依赖
    .kmmignore 文件的存在与否。
    """

    def test_backup_ops_no_kmmignore_in_all(self) -> None:
        """backup_ops.__all__ 不含 .kmmignore 相关符号。"""
        import modmgr.backup_ops as bo
        all_exports = getattr(bo, "__all__", [])
        kmmignore_exports = [s for s in all_exports if "kmmignore" in s.lower()]
        assert not kmmignore_exports, (
            f"backup_ops.__all__ 不应导出 kmmignore 相关符号: {kmmignore_exports}"
        )

    def test_restore_ops_no_kmmignore_in_all(self) -> None:
        """restore_ops.__all__ 不含 .kmmignore 相关符号。"""
        import modmgr.restore_ops as ro
        all_exports = getattr(ro, "__all__", [])
        kmmignore_exports = [s for s in all_exports if "kmmignore" in s.lower()]
        assert not kmmignore_exports, (
            f"restore_ops.__all__ 不应导出 kmmignore 相关符号: {kmmignore_exports}"
        )
