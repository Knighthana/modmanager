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
# _any_path_component_ends_with
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skip(reason="_any_path_component_ends_with removed in orchestrator refactor")
def test_any_path_component_ends_with_match():
    pass


@pytest.mark.skip(reason="_any_path_component_ends_with removed in orchestrator refactor")
def test_any_path_component_ends_with_no_match():
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# _should_ignore
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skip(reason="_should_ignore removed in orchestrator refactor")
def test_should_ignore_dir_suffix(fixture_dir):
    """目录级：路径组件以禁止后缀结尾 → 忽略。"""
    pass


@pytest.mark.skip(reason="_should_ignore removed in orchestrator refactor")
def test_should_ignore_normal_file(fixture_dir):
    """正常文件不被忽略。"""
    pass


@pytest.mark.skip(reason="_should_ignore removed in orchestrator refactor")
def test_should_ignore_kmmbakignore_cascade(fixture_dir):
    """gitignore 级联：.kmmbakignore 规则生效。"""
    pass


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
# backup() dry_run
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skip(reason="backup() removed in orchestrator refactor")
def test_backup_dry_run(fixture_dir, sample_database, sample_user_config, sample_mapping_with_content):
    """backup dry_run 返回结构化文件列表。"""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# apply() dry_run
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.skip(reason="apply() removed in orchestrator refactor")
def test_apply_dry_run_without_backup(fixture_dir, sample_database, sample_user_config, sample_mapping_with_content):
    """apply dry_run 但无备份目录 → gate 失败，记录警告。"""
    pass
