"""Black-box tests for inherent problem fixes (commit d2ae234).

Validates: on_progress pass-through, orphan removal, dead code deletion,
preflight signature cleanup, package name correctness.

Tests are independent of implementation details — they only verify
public API behavior per ``repo_test/inherent_fixes.md``.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ── helpers ────────────────────────────────────────────────────────────────


def _fake_backup_dir(tmp_path: Path) -> str:
    """Create a minimal backup_dir with valid backupinfo for testing restore."""
    import json
    import time

    bd = tmp_path / "content" / "kmmbackup"
    bd.mkdir(parents=True)
    (bd / "some_file.txt").write_text("hello")
    info = {
        "schema_namespace": "KMM_BackupInfo",
        "tree_created_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "last_modified_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "schema_version": "knighthana@0.1.0",
        "tree": {"children": {}},
    }
    (bd / "backupinfo.json").write_text(json.dumps(info))
    return str(bd) + "/"  # directory path must end with '/' per path convention


# ═══════════════════════════════════════════════════════════════════════════
# 裁定 4 — on_progress 透传
# ═══════════════════════════════════════════════════════════════════════════


class TestOnProgressPassthrough:
    """T-INH-01: on_progress callback is actually invoked by restore_from_backup."""

    def test_restore_receives_on_progress(self, tmp_path: Path):
        from modmgr.backup_ops import restore_from_backup

        backup_dir = _fake_backup_dir(tmp_path)
        cb = MagicMock()
        result = restore_from_backup(backup_dir, on_progress=cb)
        assert result["ok"], f"restore should succeed: {result.get('errors', [])}"
        assert cb.call_count > 0, "on_progress must be called at least once"


# ═══════════════════════════════════════════════════════════════════════════
# 裁定 3 — orphan 链路删除
# ═══════════════════════════════════════════════════════════════════════════


class TestOrphanRemoval:
    """T-INH-04 ~ T-INH-09: orphan symbols and strings are gone."""

    # ── T-INH-04 ────────────────────────────────────────────────────────
    def test_list_orphans_not_importable(self):
        with pytest.raises(ImportError):
            from modmgr.backup_ops import _list_orphans  # noqa: F401

    # ── T-INH-05 ────────────────────────────────────────────────────────
    def test_delete_orphan_files_not_importable(self):
        with pytest.raises(ImportError):
            from modmgr.backup_ops import delete_orphan_files  # noqa: F401

    # ── T-INH-06 ────────────────────────────────────────────────────────
    def test_delete_orphan_files_not_in_all(self):
        import modmgr.backup_ops as bo
        assert "delete_orphan_files" not in bo.__all__

    # ── T-INH-07 ────────────────────────────────────────────────────────
    def test_list_orphans_not_in_all(self):
        import modmgr.backup_ops as bo
        assert "_list_orphans" not in bo.__all__

    # ── T-INH-08 ────────────────────────────────────────────────────────
    def test_restore_result_orphans_is_empty(self, tmp_path: Path):
        from modmgr.backup_ops import restore_from_backup

        backup_dir = _fake_backup_dir(tmp_path)
        result = restore_from_backup(backup_dir, on_progress=lambda *a: None)
        # "orphans" key may be absent or present as empty list (backward compat)
        orphans = result.get("orphans", [])
        assert orphans == [], f"orphans must be empty, got {orphans!r}"

    # ── T-INH-09 ────────────────────────────────────────────────────────
    def test_W_EXTERNAL_FILE_ORPHAN_absent_from_source(self):
        """Verify W_EXTERNAL_FILE_ORPHAN string does not appear in source or docs."""
        roots = [
            Path(__file__).parent.parent / "src",
            Path(__file__).parent.parent / "repo_memo",
            Path(__file__).parent.parent / "frontend",
        ]
        found: list[str] = []
        for root in roots:
            if not root.exists():
                continue
            for f in root.rglob("*"):
                if f.is_file() and f.suffix in (".py", ".md", ".ts", ".tsx", ".json"):
                    try:
                        text = f.read_text()
                        if "W_EXTERNAL_FILE_ORPHAN" in text:
                            found.append(str(f.relative_to(root.parent)))
                    except Exception:
                        pass
        assert not found, f"W_EXTERNAL_FILE_ORPHAN found in: {found}"


# ═══════════════════════════════════════════════════════════════════════════
# 裁定 6 — CODE 清扫
# ═══════════════════════════════════════════════════════════════════════════


class TestCodeCleanup:
    """T-INH-10 ~ T-INH-19: dead code, parameters, and package names."""

    # ── CODE-3: 死代码删除 ─────────────────────────────────────────────
    def test_find_appmanifest_not_in_all(self):
        import modmgr.acf_parser as ap
        assert "find_appmanifest_acf_files" not in ap.__all__

    def test_find_appworkshop_not_in_all(self):
        import modmgr.acf_parser as ap
        assert "find_appworkshop_acf_files" not in ap.__all__

    def test_find_appmanifest_not_importable(self):
        with pytest.raises(ImportError):
            from modmgr.acf_parser import find_appmanifest_acf_files  # noqa: F401

    def test_find_appworkshop_not_importable(self):
        with pytest.raises(ImportError):
            from modmgr.acf_parser import find_appworkshop_acf_files  # noqa: F401

    # ── CODE-5: preflight 参数清理 ─────────────────────────────────────
    def test_apply_preflight_no_context_param(self):
        from modmgr.orchestrator.preflight import run_apply_preflight
        sig = inspect.signature(run_apply_preflight)
        assert "context" not in sig.parameters, "context param must be removed"

    def test_restore_preflight_no_context_param(self):
        from modmgr.orchestrator.preflight import run_restore_preflight
        sig = inspect.signature(run_restore_preflight)
        assert "context" not in sig.parameters, "context param must be removed"

    def test_apply_preflight_runs_without_context(self):
        from modmgr.orchestrator.preflight import run_apply_preflight
        result = run_apply_preflight({})
        assert isinstance(result, dict)
        assert "ok" in result

    def test_restore_preflight_runs_without_context(self):
        from modmgr.orchestrator.preflight import run_restore_preflight
        result = run_restore_preflight({})
        assert isinstance(result, dict)
        assert "ok" in result

    # ── CODE-7: 包名清理 ──────────────────────────────────────────────
    def test_modmgr_import_ok(self):
        import modmgr  # noqa: F401

    def test_modmgr_doc_no_old_name(self):
        import modmgr
        doc = (modmgr.__doc__ or "").lower()
        # "modmanager" should not appear in the package docstring
        # (allowing false-positive "modmanager" in historical context)
        # The actual docstring is just "modmgr package." now
        assert "modmanager package" not in (modmgr.__doc__ or ""), (
            f"Old package name in __doc__: {modmgr.__doc__!r}"
        )

    def test_modmgr_web_doc_cleaned(self):
        import modmgr_web
        doc = (modmgr_web.__doc__ or "").lower()
        assert "modmanager_web" not in doc, (
            f"Old web package name in __doc__: {modmgr_web.__doc__!r}"
        )

    def test_cli_no_delete_orphans_import(self):
        """Verify cli.py no longer imports delete_orphan_files."""
        cli_path = Path(__file__).parent.parent / "src" / "modmgr" / "cli.py"
        content = cli_path.read_text()
        assert "delete_orphan_files" not in content, "delete_orphan_files still in cli.py"
        assert "--delete-orphans" not in content, "--delete-orphans still in cli.py"


# ═══════════════════════════════════════════════════════════════════════════
# 裁定 2 — 文档修正（验证 repo_memo 文档已同步）
# ═══════════════════════════════════════════════════════════════════════════


class TestDocFixes:
    """T-INH-doc: verify repo_memo documents no longer reference old names."""

    def test_bootstrap_md_no_detect_platform_defaults(self):
        content = (Path(__file__).parent.parent / "repo_memo" / "DESIGN_BOOTSTRAP.md").read_text()
        assert "_detect_platform_defaults()" not in content, (
            "DESIGN_BOOTSTRAP.md still references _detect_platform_defaults()"
        )

    def test_userconfig_ops_md_no_detect_platform_defaults(self):
        content = (Path(__file__).parent.parent / "repo_memo" / "DESIGN_USERCONFIG_OPS.md").read_text()
        assert "_detect_platform_defaults()" not in content, (
            "DESIGN_USERCONFIG_OPS.md still references _detect_platform_defaults()"
        )

    def test_restore_ops_md_no_orphan_mention(self):
        content = (Path(__file__).parent.parent / "repo_memo" / "DESIGN_RESTORE_OPS.md").read_text()
        assert "孤儿文件" not in content, (
            "DESIGN_RESTORE_OPS.md still mentions orphan files"
        )
