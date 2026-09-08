"""Wave-3 tests — W_PATH_CASE_MISMATCH report-only warning.

Per the 2026-09-08 adjudication: when a kmmrule's from/into spelling
differs from the actual filesystem only in letter case, the engine must
REPORT it (so the author fixes the rule file) — never rewrite, never
auto-normalize user-authored paths.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from modmgr.engine import compute_mapping


class CaseMismatchWarningTests(unittest.TestCase):
    def _mk_db(self, tmp_path: Path) -> dict:
        game_root = tmp_path / "game"
        mod_root = tmp_path / "mods"
        game_root.mkdir(parents=True, exist_ok=True)
        mod_root.mkdir(parents=True, exist_ok=True)
        return {
            "game": [
                {
                    "appid": "270150",
                    "basepath": str(game_root) + "/",
                    "modpath": str(mod_root) + "/",
                }
            ]
        }

    def test_from_case_mismatch_reported_not_rewritten(self) -> None:
        """from 'media/...' while FS has 'Media/...' → warning naming the
        actual spelling; no mapping entry is produced for it."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            media = src_mod / "Media" / "packages"
            media.mkdir(parents=True)
            (media / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{
                            "action": "replace", "destin": "270150:0",
                            "from": ["media/packages/"], "from_type": "dir",
                            "into": ["dest/"], "into_type": "dir",
                        }],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertFalse(result["errors"])
            mismatch = [w for w in result["warnings"] if "W_PATH_CASE_MISMATCH" in w]
            self.assertTrue(mismatch, result["warnings"])
            self.assertTrue(any("Media/packages" in w for w in mismatch), mismatch)
            # report-only: the wrong-case spelling stays visible for the author
            self.assertTrue(any("media/packages" in w for w in mismatch), mismatch)
            self.assertTrue(any("W_NO_SOURCE_MATCH" in w for w in result["warnings"]))

    def test_exact_case_no_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            media = src_mod / "Media" / "packages"
            media.mkdir(parents=True)
            (media / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{
                            "action": "replace", "destin": "270150:0",
                            "from": ["Media/packages/"], "from_type": "dir",
                            "into": ["dest/"], "into_type": "dir",
                        }],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertFalse([w for w in result["warnings"] if "W_PATH_CASE_MISMATCH" in w])
            self.assertFalse(result["errors"])
            self.assertTrue(result["final_mapping"])

    def test_delete_case_mismatch_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            target_dir = tmp_path / "game" / "Media"
            target_dir.mkdir(parents=True)
            (target_dir / "old.bin").write_text("old", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{
                            "action": "delete", "destin": "270150:0",
                            "into": ["media/"], "into_type": "dir",
                        }],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            mismatch = [w for w in result["warnings"] if "W_PATH_CASE_MISMATCH" in w]
            self.assertTrue(mismatch, result["warnings"])
            self.assertTrue(any("Media" in w for w in mismatch))


if __name__ == "__main__":
    unittest.main()
