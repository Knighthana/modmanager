"""Tests for backup_ops module (Phase 7-12 implementation)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest import TestCase

from modmgr.backup_ops import (
    get_game_backup_id,
    restore_from_backup,
    run_differential_backup,
)


# ── Phase 7: get_game_backup_id ───────────────────────────────────────────────

class TestGetGameBackupId(TestCase):
    def test_returns_hex_for_valid_acf(self):
        """ACF with StateFlags=4 and valid buildid → returns (True, hex, "")."""
        with tempfile.TemporaryDirectory() as tmp:
            acf = Path(tmp) / "appmanifest_270150.acf"
            acf.write_text('"AppState"\n{\n"appid" "270150"\n"StateFlags" "4"\n"buildid" "22924257"\n}\n')
            ok, hex_id, warn = get_game_backup_id(tmp, "270150")
            self.assertTrue(ok)
            self.assertEqual(hex_id, format(22924257, "x"))
            self.assertEqual(warn, "")

    def test_returns_failure_for_missing_acf(self):
        """Missing ACF → returns (False, None, error)."""
        with tempfile.TemporaryDirectory() as tmp:
            ok, hex_id, warn = get_game_backup_id(tmp, "270150")
            self.assertFalse(ok)
            self.assertIsNone(hex_id)
            self.assertIn("E_BACKUP_STATE_UNSTABLE", warn)

    def test_returns_failure_for_missing_stateflags(self):
        """ACF without StateFlags → returns (False, None, error)."""
        with tempfile.TemporaryDirectory() as tmp:
            acf = Path(tmp) / "appmanifest_270150.acf"
            acf.write_text('"AppState"\n{\n"appid" "270150"\n"buildid" "22924257"\n}\n')
            ok, hex_id, warn = get_game_backup_id(tmp, "270150")
            self.assertFalse(ok)
            self.assertIsNone(hex_id)
            self.assertIn("StateFlags", warn)

    def test_returns_failure_for_missing_buildid(self):
        """ACF without buildid → returns (False, None, error)."""
        with tempfile.TemporaryDirectory() as tmp:
            acf = Path(tmp) / "appmanifest_270150.acf"
            acf.write_text('"AppState"\n{\n"appid" "270150"\n"StateFlags" "4"\n}\n')
            ok, hex_id, warn = get_game_backup_id(tmp, "270150")
            self.assertFalse(ok)
            self.assertIsNone(hex_id)
            self.assertIn("buildid", warn)




# ── Phase 10: run_differential_backup ────────────────────────────────────────

class TestRunDifferentialBackup(TestCase):
    def test_skips_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup") + "/"
            result = run_differential_backup(bdir, ["/nonexistent/path/file.txt"])

            self.assertTrue(result["ok"])
            self.assertEqual(result["backed_up"], [])
            self.assertEqual(len(result["skipped"]), 1)

    def test_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src"
            src_dir.mkdir()
            files = [src_dir / f"f{i}.txt" for i in range(3)]
            for f in files:
                f.write_bytes(b"data")

            bdir = str(Path(tmp) / "backup") + "/"
            result = run_differential_backup(bdir, [str(f) for f in files])

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["backed_up"]), 3)


# ── Phase 12: restore_from_backup ─────────────────────────────────────────────

class TestRestoreFromBackup(TestCase):
    def test_gate_fails_without_backup_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = restore_from_backup(str(Path(tmp) / "nonexistent") + "/")
            self.assertFalse(result["ok"])
            self.assertTrue(any("E_BACKUP_DIR_MISSING" in e for e in result["errors"]))

