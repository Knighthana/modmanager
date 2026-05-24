"""Comprehensive tests for the rule validator (modmgr.rule_validator.validate_kmm_rule_files).

Covers test scenarios S1–S20 from ``repo_test/rule_validation.md``.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from modmgr.rule_validator import validate_kmm_rule_files


# ===================================================================
# Helper
# ===================================================================


def _make_rule(temp_dir: str, filename: str, content: dict) -> str:
    """Write *content* as JSON to *temp_dir*/*filename* and return the path."""
    path = Path(temp_dir) / filename
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _make_text_file(temp_dir: str, filename: str, text: str) -> str:
    """Write raw *text* to *temp_dir*/*filename*."""
    path = Path(temp_dir) / filename
    path.write_text(text, encoding="utf-8")
    return str(path)


def _valid_rule_content() -> dict[str, Any]:
    """Return a minimal valid kmm_rule dict that passes Stage 1 + Stage 2."""
    return {
        "schema_namespace": "test",
        "schema_version": "1.0",
        "rule_meta_tag": {
            "rulenamespace": "test",
            "rulename": "test_mod",
        },
        "game": [{"appid": "270150", "modid": ["100"]}],
        "mod": [
            {
                "mixed_id": "270150:100",
                "nickname": "TestMod",
                "def_destin": "270150:0",
                "def_action": "replace",
                "actionlist": [
                    {
                        "action": "replace",
                        "from": ["data/file.txt"],
                        "from_type": "file",
                        "into": ["game_data/"],
                        "into_type": "dir",
                    }
                ],
            }
        ],
    }


# ===================================================================
# Tests
# ===================================================================


class TestValidateKmmRuleFiles(unittest.TestCase):
    """Test suite covering S1–S20 from repo_test/rule_validation.md."""

    # -- S1: valid file passes -----------------------------------------------

    def test_valid_file_passes(self) -> None:
        """S1: A valid kmm_rule file passes both stages."""
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "valid.json", _valid_rule_content())
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [path])
            self.assertEqual(rejected, [])
            self.assertEqual(warnings, [])

    # -- S2 / S3: from_type / into_type = "path" rejected via schema ----------

    def test_path_type_rejected_via_schema(self) -> None:
        """S2 / S3: from_type='path' is rejected by schema enum."""
        content = _valid_rule_content()
        content["mod"][0]["actionlist"][0]["from_type"] = "path"
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "bad_from_type.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertGreater(len(rejected[0]["errors"]), 0)
            self.assertEqual(warnings, [])

    # -- S4: missing mixed_id rejected ---------------------------------------

    def test_missing_mixed_id_rejected(self) -> None:
        """S4: Mod entry without ``mixed_id`` is rejected (schema required)."""
        content = _valid_rule_content()
        del content["mod"][0]["mixed_id"]
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "no_mixed_id.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertEqual(warnings, [])

    # -- S5: non-JSON file rejected ------------------------------------------

    def test_non_json_file_rejected(self) -> None:
        """S5: A plain-text file is rejected (JSON decode error)."""
        with tempfile.TemporaryDirectory() as td:
            path = _make_text_file(td, "not_json.txt", "this is not json")
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertIn("JSON decode", rejected[0]["errors"][0])
            self.assertEqual(warnings, [])

    # -- S6: empty file rejected ---------------------------------------------

    def test_empty_file_rejected(self) -> None:
        """S6: A 0-byte file is rejected (JSON decode error)."""
        with tempfile.TemporaryDirectory() as td:
            path = _make_text_file(td, "empty.json", "")
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertIn("JSON decode", rejected[0]["errors"][0])
            self.assertEqual(warnings, [])

    # -- S7: path traversal in from ------------------------------------------

    def test_path_traversal_in_from_rejected(self) -> None:
        """S7: ``from`` containing ``../`` is rejected with E_PATH_TRAVERSAL."""
        content = _valid_rule_content()
        content["mod"][0]["actionlist"][0]["from"] = ["../escape.txt"]
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "traversal_from.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertTrue(
                any("E_PATH_TRAVERSAL" in e for e in rejected[0]["errors"])
            )
            self.assertEqual(warnings, [])

    # -- S8: path traversal in into ------------------------------------------

    def test_path_traversal_in_into_rejected(self) -> None:
        """S8: ``into`` containing ``../`` is rejected with E_PATH_TRAVERSAL."""
        content = _valid_rule_content()
        content["mod"][0]["actionlist"][0]["into"] = ["../escape/"]
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "traversal_into.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertTrue(
                any("E_PATH_TRAVERSAL" in e for e in rejected[0]["errors"])
            )
            self.assertEqual(warnings, [])

    # -- S11: invalid action rejected ----------------------------------------

    def test_invalid_action_rejected(self) -> None:
        """S11: ``action: "unknown_action"`` is rejected."""
        content = _valid_rule_content()
        content["mod"][0]["actionlist"][0]["action"] = "unknown_action"
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "bad_action.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertEqual(warnings, [])

    # -- S12: replace missing from rejected ----------------------------------

    def test_replace_missing_from_rejected(self) -> None:
        """S12: ``action: 'replace'`` without ``from`` is rejected."""
        content = _valid_rule_content()
        del content["mod"][0]["actionlist"][0]["from"]
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "no_from.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertEqual(warnings, [])

    # -- S15: replace empty from rejected (C6) -------------------------------

    def test_replace_empty_from_rejected(self) -> None:
        """S15: ``action: 'replace'`` with empty ``from`` list — C6 rejects."""
        content = _valid_rule_content()
        content["mod"][0]["actionlist"][0]["from"] = []
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "empty_from.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertTrue(
                any("E_MISSING_FROM" in e for e in rejected[0]["errors"])
            )
            self.assertEqual(warnings, [])

    # -- S16: replace empty into rejected (C7) -------------------------------

    def test_replace_empty_into_rejected(self) -> None:
        """S16: ``action: 'replace'`` with empty ``into`` list — C7 rejects."""
        content = _valid_rule_content()
        content["mod"][0]["actionlist"][0]["into"] = []
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "empty_into.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], path)
            self.assertTrue(
                any("E_MISSING_INTO" in e for e in rejected[0]["errors"])
            )
            self.assertEqual(warnings, [])

    # -- S17/S18: mixed_id format warning (C8) --------------------------------

    def test_mixed_id_format_warning(self) -> None:
        """S17/S18: ``mixed_id`` without leading digits triggers C8 warning."""
        content = _valid_rule_content()
        # Passes schema (has colon) but fails C8 (no leading digits)
        content["mod"][0]["mixed_id"] = "abc:def"
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "bad_mixed_id.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [path])
            self.assertEqual(rejected, [])
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]["path"], path)
            self.assertTrue(
                any("W_MIXED_ID_FORMAT" in w for w in warnings[0]["warnings"])
            )

    # -- S19: def_destin format warning (C9) ----------------------------------

    def test_def_destin_format_warning(self) -> None:
        """S19: ``def_destin`` with non-standard format triggers C9 warning."""
        content = _valid_rule_content()
        # Passes schema (string) but fails C9 (no leading digits)
        content["mod"][0]["def_destin"] = "bad_format:value"
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "bad_destin.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [path])
            self.assertEqual(rejected, [])
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]["path"], path)
            self.assertTrue(
                any("W_DESTIN_FORMAT" in w for w in warnings[0]["warnings"])
            )

    # -- S20: sub[] format warning (C10) --------------------------------------

    def test_sub_format_warning(self) -> None:
        """S20: ``sub[]`` entry without leading digits triggers C10 warning."""
        content = _valid_rule_content()
        content["mod"][0]["sub"] = ["bad:format", "270150:200"]
        with tempfile.TemporaryDirectory() as td:
            path = _make_rule(td, "bad_sub.json", content)
            passed, rejected, warnings = validate_kmm_rule_files([path])

            self.assertEqual(passed, [path])
            self.assertEqual(rejected, [])
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0]["path"], path)
            self.assertTrue(
                any("W_SUB_FORMAT" in w for w in warnings[0]["warnings"])
            )

    # -- I2: mixed input (2 valid + 1 invalid) -------------------------------

    def test_mixed_input(self) -> None:
        """I2: 2 valid + 1 invalid file → passed=2, rejected=1."""
        with tempfile.TemporaryDirectory() as td:
            v1 = _make_rule(td, "valid1.json", _valid_rule_content())
            v2 = _make_rule(td, "valid2.json", _valid_rule_content())

            bad = _valid_rule_content()
            bad["mod"][0]["actionlist"][0]["from"] = ["../../evil.txt"]
            inv = _make_rule(td, "invalid.json", bad)

            passed, rejected, warnings = validate_kmm_rule_files([v1, v2, inv])

            self.assertEqual(len(passed), 2)
            self.assertIn(v1, passed)
            self.assertIn(v2, passed)
            self.assertEqual(len(rejected), 1)
            self.assertEqual(rejected[0]["path"], inv)
            self.assertTrue(
                any("E_PATH_TRAVERSAL" in e for e in rejected[0]["errors"])
            )

    # -- I3: all invalid, no crash -------------------------------------------

    def test_all_invalid(self) -> None:
        """I3: all rejected, aggregator sees no crash."""
        with tempfile.TemporaryDirectory() as td:
            p1 = _make_text_file(td, "not_json.txt", "garbage")
            p2 = _make_text_file(td, "empty.json", "")
            bad_content = _valid_rule_content()
            bad_content["mod"][0]["actionlist"][0]["action"] = "bogus"
            p3 = _make_rule(td, "bad_action.json", bad_content)

            passed, rejected, warnings = validate_kmm_rule_files([p1, p2, p3])

            self.assertEqual(passed, [])
            self.assertEqual(len(rejected), 3)
            self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
