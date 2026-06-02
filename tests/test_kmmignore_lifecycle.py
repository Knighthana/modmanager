"""Tests for .kmmignore lifecycle — Planner-managed (裁定 1 + 13).

Verifies:
- T-KI-01~02: orchestrator/__init__.py has no _copy_kmmignore_* definition
- T-KI-03~04: planner_fileops.py has _copy_kmmignore_* functions
- T-KI-05~06: backup_ops/restore_ops don't import .kmmignore-related
- T-KI-13: plan_fileops() output excludes ignored files
- T-KI-14: plan_fileops() output includes ignore_rule_set cache
"""

from __future__ import annotations

import importlib
import inspect
import tempfile
from pathlib import Path

import pytest

from modmgr.orchestrator.planner_fileops import (
    _copy_kmmignore_to_backup,
    _copy_kmmignore_from_backup,
)
from modmgr.orchestrator.entry import Intent, TaskRequest
from modmgr.orchestrator.resolver import CleanContext


# ── T-KI-01 & T-KI-02: orchestrator/__init__.py 不含函数定义 ────────────


class TestOrchestratorNoKmmignoreDefs:
    """T-KI-01 / T-KI-02: orchestrator/__init__.py does NOT define the functions."""

    def _get_orchestrator_source(self) -> str:
        """Return the source text of orchestrator/__init__.py."""
        import modmgr.orchestrator as orch
        return inspect.getsource(orch)

    def test_t_ki_01_no_copy_kmmignore_to_backup_definition(self) -> None:
        """T-KI-01: orchestrator/__init__.py 不含 _copy_kmmignore_to_backup 定义."""
        source = self._get_orchestrator_source()
        assert "def _copy_kmmignore_to_backup" not in source, (
            "orchestrator/__init__.py must not DEFINE _copy_kmmignore_to_backup"
        )

    def test_t_ki_02_no_copy_kmmignore_from_backup_definition(self) -> None:
        """T-KI-02: orchestrator/__init__.py 不含 _copy_kmmignore_from_backup 定义."""
        source = self._get_orchestrator_source()
        assert "def _copy_kmmignore_from_backup" not in source, (
            "orchestrator/__init__.py must not DEFINE _copy_kmmignore_from_backup"
        )


# ── T-KI-03 & T-KI-04: planner_fileops.py 含有函数定义 ──────────────────


class TestPlannerHasKmmignoreDefs:
    """T-KI-03 / T-KI-04: planner_fileops.py defines the functions."""

    def _get_planner_source(self) -> str:
        """Return the source text of planner_fileops.py."""
        import modmgr.orchestrator.planner_fileops as pf
        return inspect.getsource(pf)

    def test_t_ki_03_planner_has_copy_kmmignore_to_backup(self) -> None:
        """T-KI-03: planner_fileops.py 含 _copy_kmmignore_to_backup 函数."""
        source = self._get_planner_source()
        assert "def _copy_kmmignore_to_backup" in source, (
            "planner_fileops.py must DEFINE _copy_kmmignore_to_backup"
        )

    def test_t_ki_04_planner_has_copy_kmmignore_from_backup(self) -> None:
        """T-KI-04: planner_fileops.py 含 _copy_kmmignore_from_backup 函数."""
        source = self._get_planner_source()
        assert "def _copy_kmmignore_from_backup" in source, (
            "planner_fileops.py must DEFINE _copy_kmmignore_from_backup"
        )


# ── T-KI-05 & T-KI-06: backup_ops/restore_ops 不 import .kmmignore ──────


class TestPrimitivesNoKmmignoreImport:
    """T-KI-05 / T-KI-06: primitives don't import .kmmignore-related."""

    def test_t_ki_05_backup_ops_no_kmmignore_import(self) -> None:
        """T-KI-05: backup_ops.py 不 import 任何 .kmmignore 相关."""
        import modmgr.backup_ops as bo
        source = inspect.getsource(bo)
        assert "kmmignore" not in source, (
            "backup_ops.py must not import/reference .kmmignore"
        )

    def test_t_ki_06_restore_ops_no_kmmignore_import(self) -> None:
        """T-KI-06: restore_ops.py 不 import 任何 .kmmignore 相关."""
        import modmgr.restore_ops as ro
        source = inspect.getsource(ro)
        assert "kmmignore" not in source, (
            "restore_ops.py must not import/reference .kmmignore"
        )


# ── Helpers (Steam fixture for plan_fileops) ─────────────────────────

APPID = "270150"
CONTENTID = "2606099273"


def _build_steam_fixture(root: Path) -> None:
    """Create a minimal Steam workshop fixture with ACF files on disk."""
    steamapps = root / "steamapps"
    common = steamapps / "common" / "RunningWithRifles"
    mod = steamapps / "workshop" / "content" / APPID / CONTENTID
    common.mkdir(parents=True)
    mod.mkdir(parents=True)

    # Create a mod file
    (mod / "test_mod_file.txt").write_text("content")
    (mod / "data.bin").write_text("binary")

    # Create appmanifest ACF (needed for app backup stability check)
    (steamapps / f"appmanifest_{APPID}.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"' + APPID + '"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"22924257"\n}\n'
    )

    # Create appworkshop ACF (needed for content backup hex_id)
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


# ── T-KI-13: plan_fileops() 输出不含被 ignore 的文件 ────────────────────


class TestPlanFiltering:
    """T-KI-13: plan_fileops() entries_by_backup_dir 不含被 ignore 的文件."""

    def test_t_ki_13_plan_excludes_ignored_files(self) -> None:
        """T-KI-13: plan_fileops() 返回的 entries_by_backup_dir 不含被 ignore 的文件."""
        from modmgr.orchestrator.planner_fileops import plan_fileops

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            # Place .kmmignore at game basepath so it's within collection scope
            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            (game_root / ".kmmignore").write_text("*.log\nbuild/\n")
            # Create files matching ignore patterns under basepath
            (game_root / "debug.log").write_text("logs")
            (game_root / "build").mkdir()
            (game_root / "build" / "output.o").write_text("obj")

            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "data.bin"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "debug.log"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "build" / "output.o"), "game_name": "RunningWithRifles"},
            ]

            context = CleanContext(
                final_mapping=final_mapping,
                database=_make_database(root),
                user_config={"baksuffix": "kmmbackup"},
            )
            request = TaskRequest(
                identity="cli",
                intent=Intent.BACKUP,
                resolver_type="raw_dict",
                resolver_args={},
                flags={"dry_run": True},
            )

            plan = plan_fileops(request, context)

            # Collect all paths in entries_by_backup_dir
            all_paths = set()
            for entries in plan.entries_by_backup_dir.values():
                for entry in entries:
                    all_paths.add(entry.get("path", ""))

            # game.bin and data.bin should be present
            assert any("game.bin" in p for p in all_paths), (
                "game.bin should NOT be filtered"
            )
            assert any("data.bin" in p for p in all_paths), (
                "data.bin should NOT be filtered"
            )
            # debug.log should NOT be present (filtered by *.log)
            assert not any("debug.log" in p for p in all_paths), (
                "debug.log should be filtered by *.log rule"
            )
            # build/output.o should NOT be present (filtered by build/)
            assert not any("output.o" in p for p in all_paths), (
                "output.o should be filtered by build/ rule"
            )


# ── T-KI-14: plan_fileops() 输出含 ignore_rule_set 缓存 ────────────────


class TestIgnoreRuleSetCache:
    """T-KI-14: plan_fileops() 输出中的 ignore_rule_set 缓存可供原语直接消费."""

    def test_t_ki_14_plan_contains_ignore_rule_set(self) -> None:
        """T-KI-14: FileOpsPlan.ignore_rules is populated."""
        from modmgr.orchestrator.planner_fileops import plan_fileops
        from modmgr.orchestrator.ignore_rules import IgnoreRuleSet

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            # Place .kmmignore at game basepath (within collection scope)
            game_root = root / "steamapps" / "common" / "RunningWithRifles"
            (game_root / ".kmmignore").write_text("*.txt\n")

            final_mapping = [
                {"path": str(game_root / "game.bin"), "game_name": "RunningWithRifles"},
                {"path": str(game_root / "data.bin"), "game_name": "RunningWithRifles"},
            ]

            context = CleanContext(
                final_mapping=final_mapping,
                database=_make_database(root),
                user_config={"baksuffix": "kmmbackup"},
            )
            request = TaskRequest(
                identity="cli",
                intent=Intent.BACKUP,
                resolver_type="raw_dict",
                resolver_args={},
                flags={"dry_run": True},
            )

            plan = plan_fileops(request, context)

            # ignore_rules should be populated (not default empty)
            assert isinstance(plan.ignore_rules, IgnoreRuleSet)
            # The rule set should contain the *.txt rule from .kmmignore
            assert len(plan.ignore_rules.gitignore_rules) > 0
