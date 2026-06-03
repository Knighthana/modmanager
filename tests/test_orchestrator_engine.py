# test_orchestrator_engine.py — 引擎函数测试

"""测试 orchestrator 引擎函数（不依赖工作区上下文）。

直接构造 final_mapping / database / user_config 调用引擎函数，
验证 dry_run 输出格式、gate check、ignore 过滤、restore HASH 比对。
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

import pytest

from modmgr.backup_dir_builder import build_backup_dirs, load_dir_suffixes
from modmgr.backup_ops import get_game_backup_id, get_workshop_timestamphex


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def fixture_dir():
    """临时目录模拟 Steam 库结构。"""
    d = tempfile.mkdtemp(prefix="test_engine_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_database(fixture_dir):
    """构造 database + mock ACF 文件（含 appmanifest 和 appworkshop）。"""
    common = Path(fixture_dir) / "steamapps" / "common" / "RunningWithRifles"
    workshop = Path(fixture_dir) / "steamapps" / "workshop" / "content" / "270150"
    steamapps = Path(fixture_dir) / "steamapps"
    common.mkdir(parents=True)
    workshop.mkdir(parents=True)

    # Mock appmanifest_270150.acf（StateFlags=4, buildid=22924257）
    (steamapps / "appmanifest_270150.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"270150"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"22924257"\n}\n'
    )

    # Mock workshop/appworkshop_270150.acf
    ws_acf_dir = steamapps / "workshop"
    ws_acf_dir.mkdir(exist_ok=True)
    (ws_acf_dir / "appworkshop_270150.acf").write_text(
        '"AppWorkshop"\n{\n'
        '\t"WorkshopItemsInstalled"\n\t{\n'
        '\t\t"2606099273"\n\t\t{\n\t\t\t"timeupdated"\t\t"1776317725"\n\t\t}\n'
        '\t}\n'
        '\t"WorkshopItemDetails"\n\t{\n'
        '\t\t"2606099273"\n\t\t{\n\t\t\t"latest_timeupdated"\t\t"1776317725"\n\t\t}\n'
        '\t}\n'
        '}\n'
    )

    return {
        "game": [{
            "appid": "270150",
            "basepath": str(common) + "/",
            "modpath": str(workshop) + "/",
        }]
    }


@pytest.fixture
def sample_user_config():
    return {"baksuffix": "kmmbackup"}


@pytest.fixture
def sample_final_mapping(fixture_dir):
    """构造一个简单的 final_mapping。"""
    base = Path(fixture_dir)
    (base / "steamapps" / "common" / "RunningWithRifles" / "media").mkdir(parents=True)
    return [
        {
            "path": str(base / "steamapps/common/RunningWithRifles/media/file_a.mod"),
            "request": {"action": "create", "path": "/tmp/src/file_a.mod"},
        },
    ]


@pytest.fixture
def sample_mapping_with_content(fixture_dir):
    """构造含 workshop contentid 的 mapping。"""
    base = Path(fixture_dir)
    d = base / "steamapps/workshop/content/270150/2606099273/some"
    d.mkdir(parents=True)
    (d / "file.mod").write_text("test content")
    return [
        {
            "path": str(d / "file.mod"),
            "request": {"action": "create", "path": "/tmp/src/file.mod"},
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# load_dir_suffixes
# ═══════════════════════════════════════════════════════════════════════════════

def test_load_dir_suffixes_default():
    """默认返回 ['.kmmbackup']。"""
    assert load_dir_suffixes() == [".kmmbackup"]


# ═══════════════════════════════════════════════════════════════════════════════
# Ignore rules — replacement for removed _should_ignore / _any_path_component
# Tests now use the public IgnoreRuleSet / should_ignore API
# ═══════════════════════════════════════════════════════════════════════════════

from modmgr.orchestrator.fileops.planner.ignore_rules import (
    IgnoreRuleSet,
    collect_rules,
    should_ignore,
)


def test_should_ignore_hardcoded_suffix():
    """Hardcoded .kmmbackup suffix is ignored."""
    rules = IgnoreRuleSet()
    assert should_ignore("/some/path.kmmbackup/file.txt", rules)
    assert should_ignore("dir.kmmbackup/game.bin", rules)
    assert not should_ignore("normal/path/file.txt", rules)


def test_should_ignore_normal_file_not_ignored():
    """正常文件不被硬编码规则忽略。"""
    rules = IgnoreRuleSet()
    assert not should_ignore("game.bin", rules)
    assert not should_ignore("data.txt", rules)
    assert not should_ignore("subdir/readme.md", rules)


def test_should_ignore_empty_rules():
    """空规则集 (no hardcoded) 不忽略任何文件。"""
    rules = IgnoreRuleSet(hardcoded_suffixes=[])
    assert not should_ignore("debug.log", rules)
    assert not should_ignore("any/file.txt", rules)


def test_should_ignore_custom_suffix():
    """自定义硬编码后缀。"""
    rules = IgnoreRuleSet(hardcoded_suffixes=[".bak"])
    assert should_ignore("test.bak/file.txt", rules)
    assert not should_ignore("normal.txt", rules)


def test_should_ignore_via_kmmignore_file():
    """通过临时 .kmmignore 文件测试 collect_rules + should_ignore。"""
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        game_root = root / "game"
        game_root.mkdir()
        (game_root / ".kmmignore").write_text("*.log\n")

        rules = collect_rules([str(game_root)])

        # 被 gitignore 规则忽略
        assert should_ignore(str(game_root / "debug.log"), rules)
        # 不被忽略
        assert not should_ignore(str(game_root / "game.bin"), rules)
        assert not should_ignore(str(game_root / "data.txt"), rules)


# ═══════════════════════════════════════════════════════════════════════════════
# build_backup_dirs
# ═══════════════════════════════════════════════════════════════════════════════

def test_build_backup_dirs_app(fixture_dir, sample_database, sample_user_config, sample_final_mapping):
    """app 本体（basepath 匹配）生成正确的 backup_dir。"""
    dirs, warnings = build_backup_dirs(sample_final_mapping, sample_database, sample_user_config)
    assert len(dirs) == 1
    key = list(dirs.keys())[0]
    assert "/common/RunningWithRifles/" in key
    assert key.endswith(".kmmbackup/")


def test_build_backup_dirs_content(fixture_dir, sample_database, sample_user_config, sample_mapping_with_content):
    """workshop contentid（modpath 匹配）生成正确的 backup_dir。"""
    dirs, warnings = build_backup_dirs(sample_mapping_with_content, sample_database, sample_user_config)
    assert len(dirs) == 1
    key = list(dirs.keys())[0]
    assert "/2606099273/" in key
    assert key.endswith(".kmmbackup/")


# ═══════════════════════════════════════════════════════════════════════════════
# plan_fileops dry_run — replacement for removed backup/apply dry_run
# Tests now use the public plan_fileops API
# ═══════════════════════════════════════════════════════════════════════════════

from modmgr.orchestrator.entry import Intent, TaskRequest
from modmgr.orchestrator.fileops.planner.planner import plan_fileops


def test_plan_fileops_backup_dry_run(fixture_dir, sample_database, sample_user_config, sample_mapping_with_content):
    """plan_fileops(BACKUP, dry_run=True) 返回 plan 且 dry_run=True。"""
    request = TaskRequest(
        identity="cli",
        intent=Intent.BACKUP,
        resolver_type="file_paths",
        resolver_args={},
        flags={"dry_run": True},
    )
    data = {
        "final_mapping": sample_mapping_with_content,
        "database": sample_database,
        "user_config": sample_user_config,
    }
    plan = plan_fileops(request, data)
    assert plan is not None
    assert plan.dry_run is True
    assert plan.intent == Intent.BACKUP


def test_plan_fileops_apply_dry_run(fixture_dir, sample_database, sample_user_config, sample_final_mapping):
    """plan_fileops(APPLY, dry_run=True) 返回 plan 且 preflight 检查执行。"""
    request = TaskRequest(
        identity="cli",
        intent=Intent.APPLY,
        resolver_type="file_paths",
        resolver_args={},
        flags={"dry_run": True, "force": True},
    )
    data = {
        "final_mapping": sample_final_mapping,
        "database": sample_database,
        "user_config": sample_user_config,
    }
    plan = plan_fileops(request, data)
    assert plan is not None
    assert plan.dry_run is True
    # APPLY should run preflight
    assert plan.preflight_manifest is not None or plan.preflight_ok is not None
