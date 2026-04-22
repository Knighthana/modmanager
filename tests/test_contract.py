"""Contract tests: every code path of compute_mapping must produce output
that conforms to output_schema.json.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from modmanager_cli.engine import compute_mapping
from modmanager_cli.schema import get_output_schema, validate_output, validate_output_collect


# ── helpers ───────────────────────────────────────────────────────────────────

def _mk_db(tmp_path: Path) -> dict[str, Any]:
    game_root = tmp_path / "game"
    mod_root = tmp_path / "mods"
    game_root.mkdir(parents=True, exist_ok=True)
    mod_root.mkdir(parents=True, exist_ok=True)
    return {
        "game": [
            {
                "appid": "1",
                "basepath": str(game_root),
                "modpath": str(mod_root),
            }
        ]
    }


def _assert_valid(tc: unittest.TestCase, result: Any) -> None:
    errs = validate_output_collect(result)
    tc.assertEqual(errs, [], msg="Schema violations:\n" + "\n".join(errs))


# ── schema self-test ──────────────────────────────────────────────────────────

class SchemaLoadTests(unittest.TestCase):
    def test_schema_loads_without_error(self) -> None:
        schema = get_output_schema()
        self.assertIn("properties", schema)
        self.assertEqual(schema["title"], "ComputeMappingOutput")

    def test_schema_has_required_top_level_keys(self) -> None:
        schema = get_output_schema()
        required = set(schema["required"])
        self.assertSetEqual(required, {"warnings", "errors", "forest", "final_mapping"})

    def test_schema_change_request_enum_matches_engine(self) -> None:
        from modmanager_cli.engine import VALID_ACTIONS
        schema = get_output_schema()
        schema_enum = set(schema["definitions"]["ChangeRequest"]["properties"]["action"]["enum"])
        self.assertSetEqual(schema_enum, VALID_ACTIONS)

    def test_validate_output_rejects_missing_keys(self) -> None:
        errs = validate_output_collect({"warnings": [], "errors": []})
        self.assertTrue(any("forest" in e or "final_mapping" in e for e in errs))

    def test_validate_output_rejects_wrong_type_for_warnings(self) -> None:
        errs = validate_output_collect(
            {"warnings": "not-a-list", "errors": [], "forest": [], "final_mapping": []}
        )
        self.assertTrue(errs)

    def test_validate_output_rejects_extra_top_level_key(self) -> None:
        errs = validate_output_collect(
            {"warnings": [], "errors": [], "forest": [], "final_mapping": [], "extra": 1}
        )
        self.assertTrue(errs)

    def test_validate_output_accepts_minimal_valid_structure(self) -> None:
        errs = validate_output_collect(
            {"warnings": [], "errors": [], "forest": [], "final_mapping": []}
        )
        self.assertEqual(errs, [])

    def test_validate_output_accepts_change_request_ref_fields(self) -> None:
        errs = validate_output_collect(
            {
                "warnings": [],
                "errors": [],
                "forest": [
                    {
                        "path": "/dst/a.txt",
                        "changerequest": [
                            {
                                "path": "/src/a.txt",
                                "action": "replace",
                                "action_order": 0,
                                "provenance_ref": "404",
                                "sidecar_ref": "404",
                                "mixed_id": "1:10",
                                "hashtype": "sha256",
                                "hashvalue": "",
                            }
                        ],
                    }
                ],
                "final_mapping": [],
            }
        )
        self.assertEqual(errs, [])


# ── contract tests against actual compute_mapping output ─────────────────────

class ContractTests(unittest.TestCase):
    """Every output path of compute_mapping must satisfy the schema."""

    # ── empty aggregated rule set ─────────────────────────────────────────────

    def test_empty_aggregated_rule_set_conforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = _mk_db(tmp_path)
            result = compute_mapping({"mod": []}, db)
            _assert_valid(self, result)
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["forest"], [])
            self.assertEqual(result["final_mapping"], [])

    # ── normal single-node forest ─────────────────────────────────────────────

    def test_single_rule_no_branch_conforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = _mk_db(tmp_path)
            src = tmp_path / "mods" / "10"
            src.mkdir(parents=True)
            (src / "a.txt").write_text("x", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "1:10",
                        "sub": [],
                        "def_destin": "1:0",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["dest/"], "into_type": "path"}],
                    }
                ]
            }
            result = compute_mapping(aggregated_rule_set, db)
            _assert_valid(self, result)
            self.assertEqual(result["errors"], [])
            self.assertEqual(len(result["forest"]), 1)
            self.assertEqual(len(result["final_mapping"]), 1)
            # forest node structure
            node = result["forest"][0]
            self.assertIn("path", node)
            self.assertIn("changerequest", node)
            self.assertIsInstance(node["changerequest"], list)

    # ── create-overwrites-existing path ──────────────────────────────────────

    def test_create_existing_conforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = _mk_db(tmp_path)
            src = tmp_path / "mods" / "10"
            src.mkdir(parents=True)
            (src / "a.txt").write_text("x", encoding="utf-8")
            target_dir = tmp_path / "game" / "dest"
            target_dir.mkdir(parents=True)
            (target_dir / "a.txt").write_text("old", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "1:10",
                        "sub": [],
                        "def_destin": "1:0",
                        "def_action": "create",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["dest/"], "into_type": "path"}],
                    }
                ]
            }
            result = compute_mapping(aggregated_rule_set, db)
            _assert_valid(self, result)

    # ── schema-error path (invalid branch_decisions type) ────────────────────

    def test_schema_error_path_conforms(self) -> None:
        result = compute_mapping({"mod": []}, {}, branch_decisions=["bad"]) # type: ignore[arg-type]
        _assert_valid(self, result)
        self.assertTrue(result["errors"])
        self.assertEqual(result["final_mapping"], [])

    # ── clear_then_copy conflict (E_ error) ───────────────────────────────────

    def test_conflict_error_path_conforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = _mk_db(tmp_path)
            for modid in ("10", "11"):
                mroot = tmp_path / "mods" / modid
                mroot.mkdir(parents=True)
                (mroot / "a.txt").write_text("x", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "1:10",
                        "sub": [],
                        "def_destin": "1:0",
                        "def_action": "replace",
                        "actionlist": [{"action": "clear_then_copy", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "1:11",
                        "sub": [],
                        "def_destin": "1:0",
                        "def_action": "replace",
                        "actionlist": [{"action": "clear_then_copy", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }
            result = compute_mapping(aggregated_rule_set, db)
            _assert_valid(self, result)
            self.assertTrue(any(e.startswith("E_CLEAR_THEN_COPY_CONFLICT") for e in result["errors"]))
            self.assertEqual(result["final_mapping"], [])

    # ── unresolved branch path ────────────────────────────────────────────────

    def test_unresolved_branch_conforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = _mk_db(tmp_path)
            for modid in ("10", "11", "20"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            (tmp_path / "mods" / "10" / "a.txt").write_text("x", encoding="utf-8")
            (tmp_path / "mods" / "11" / "a.txt").write_text("y", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "1:10",
                        "sub": [],
                        "def_destin": "1:20",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "1:11",
                        "sub": [],
                        "def_destin": "1:20",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "1:20",
                        "sub": ["1:10", "1:11"],
                        "def_destin": "1:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                ]
            }
            result = compute_mapping(aggregated_rule_set, db)
            _assert_valid(self, result)
            # branched node must carry 'warning' and 'candidates'
            branched = [n for n in result["forest"] if n.get("warning") == "W_FOREST_BRANCHING"]
            self.assertTrue(branched)
            for node in branched:
                self.assertIn("candidates", node)
                self.assertIsInstance(node["candidates"], list)

    # ── resolved branch path ──────────────────────────────────────────────────

    def test_resolved_branch_conforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = _mk_db(tmp_path)
            for modid in ("10", "11", "20"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            (tmp_path / "mods" / "10" / "a.txt").write_text("x", encoding="utf-8")
            (tmp_path / "mods" / "11" / "a.txt").write_text("y", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "1:10",
                        "sub": [],
                        "def_destin": "1:20",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "1:11",
                        "sub": [],
                        "def_destin": "1:20",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "1:20",
                        "sub": ["1:10", "1:11"],
                        "def_destin": "1:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                ]
            }
            forest_result = compute_mapping(aggregated_rule_set, db)
            branched = forest_result["forest"][0]
            decisions = {branched["path"]: branched["candidates"][0]}
            result = compute_mapping(aggregated_rule_set, db, branch_decisions=decisions)
            _assert_valid(self, result)
            self.assertFalse(result["errors"])
            self.assertEqual(len(result["final_mapping"]), 1)
            fm = result["final_mapping"][0]
            self.assertIn("path", fm)
            self.assertIn("request", fm)

    # ── invalid branch source → error path ───────────────────────────────────

    def test_invalid_branch_source_error_conforms(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = _mk_db(tmp_path)
            for modid in ("10", "11", "20"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            (tmp_path / "mods" / "10" / "a.txt").write_text("x", encoding="utf-8")
            (tmp_path / "mods" / "11" / "a.txt").write_text("y", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "1:10",
                        "sub": [],
                        "def_destin": "1:20",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "1:11",
                        "sub": [],
                        "def_destin": "1:20",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "1:20",
                        "sub": ["1:10", "1:11"],
                        "def_destin": "1:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                ]
            }
            forest_result = compute_mapping(aggregated_rule_set, db)
            target = forest_result["forest"][0]["path"]
            result = compute_mapping(aggregated_rule_set, db, branch_decisions={target: "/no/such/file.txt"})
            _assert_valid(self, result)
            self.assertTrue(any("E_BRANCH_DECISION_INVALID_SOURCE" in e for e in result["errors"]))


if __name__ == "__main__":
    unittest.main()
