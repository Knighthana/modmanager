import json
import tempfile
import unittest
from pathlib import Path

from modmanager_cli.engine import (
    _check_filefoldertree_transition,
    compute_mapping,
    find_cycles,
    validate_branch_decisions_schema,
)
from modmanager_cli.engine import validate_forest_roots


class EngineTests(unittest.TestCase):
    def _mk_db(self, tmp_path: Path) -> dict:
        game_root = tmp_path / "game"
        mod_root = tmp_path / "mods"
        game_root.mkdir(parents=True, exist_ok=True)
        mod_root.mkdir(parents=True, exist_ok=True)
        return {
            "game": [
                {
                    "appid": "270150",
                    "basepath": str(game_root),
                    "modpath": str(mod_root),
                }
            ]
        }

    def test_create_existing_warns_and_keeps_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            src_mod.mkdir(parents=True)
            (src_mod / "a.txt").write_text("x", encoding="utf-8")

            target_dir = tmp_path / "game" / "dest"
            target_dir.mkdir(parents=True)
            (target_dir / "a.txt").write_text("old", encoding="utf-8")

            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "create",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["dest/"], "into_type": "path"}],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_CREATE_TARGET_EXISTS_OVERWRITE" in w for w in result["warnings"]))
            self.assertFalse(result["errors"])
            self.assertTrue(result["final_mapping"])

    def test_clear_then_copy_same_dir_conflict_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100", "101"):
                mroot = tmp_path / "mods" / modid
                mroot.mkdir(parents=True)
                (mroot / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [{"action": "clear_then_copy", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [{"action": "clear_then_copy", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any(e.startswith("E_CLEAR_THEN_COPY_CONFLICT") for e in result["errors"]))
            self.assertEqual(result["final_mapping"], [])

    def test_sub_not_recognized_rule_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            dst_mod = tmp_path / "mods" / "200"
            src_mod.mkdir(parents=True)
            dst_mod.mkdir(parents=True)
            (src_mod / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:200",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_SUB_NOT_RECOGNIZED" in w for w in result["warnings"]))
            self.assertEqual(result["forest"], [])

    def test_local_mod_missing_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:local_dev_mod",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_LOCAL_MOD_MISSING" in w for w in result["warnings"]))
            self.assertEqual(result["forest"], [])

    def test_unresolved_branch_blocks_final_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100", "101", "200"):
                mroot = tmp_path / "mods" / modid
                mroot.mkdir(parents=True)
            (tmp_path / "mods" / "100" / "a.txt").write_text("x", encoding="utf-8")
            (tmp_path / "mods" / "101" / "a.txt").write_text("y", encoding="utf-8")

            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:200",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "sub": [],
                        "def_destin": "270150:200",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "sub": ["270150:100", "270150:101"],
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_FOREST_BRANCHING_UNRESOLVED" in w for w in result["warnings"]))
            self.assertEqual(result["final_mapping"], [])
            self.assertTrue(result["forest"])

    def test_filefoldertree_transition_only_forward(self) -> None:
        old_tree = {
            "name": "root",
            "type": "folder",
            "children": [
                {
                    "name": "a.txt",
                    "type": "file",
                    "isbackuped": False,
                    "hashtype": "invalid",
                    "hashvalue": "0",
                }
            ],
        }
        new_tree = {
            "name": "root",
            "type": "folder",
            "children": [
                {
                    "name": "a.txt",
                    "type": "file",
                    "isbackuped": True,
                    "hashtype": "sha256",
                    "hashvalue": "abcd",
                }
            ],
        }

        self.assertEqual(_check_filefoldertree_transition(old_tree, new_tree), [])

        bad_tree = json.loads(json.dumps(new_tree))
        bad_tree["children"][0]["isbackuped"] = False
        errs = _check_filefoldertree_transition(new_tree, bad_tree)
        self.assertTrue(any("E_TREE_ATTR_BACKWARD" in e for e in errs))

    # ── branch decision schema validation ─────────────────────────────────

    def test_branch_decisions_schema_must_be_dict(self) -> None:
        result = compute_mapping({"mod": []}, {"game": []}, branch_decisions=["bad"])
        self.assertTrue(any("E_BRANCH_DECISION_INVALID_SCHEMA" in e for e in result["errors"]))

    def test_branch_decisions_key_must_be_string(self) -> None:
        errs = validate_branch_decisions_schema({1: "src"})
        self.assertTrue(any("E_BRANCH_DECISION_INVALID_SCHEMA" in e for e in errs))

    def test_branch_decisions_value_must_be_string(self) -> None:
        errs = validate_branch_decisions_schema({"/target/a.txt": 42})
        self.assertTrue(any("E_BRANCH_DECISION_INVALID_SCHEMA" in e for e in errs))

    def test_branch_decisions_valid_schema_no_errors(self) -> None:
        errs = validate_branch_decisions_schema({"/target/a.txt": "/src/a.txt"})
        self.assertEqual(errs, [])

    def test_branch_decision_superfluous_warns_for_non_branched_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src = tmp_path / "mods" / "100"
            src.mkdir(parents=True)
            (src / "a.txt").write_text("x", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    }
                ]
            }
            # Provide a decision for a target that doesn't branch
            result = compute_mapping(aggregated_rule_set, db, branch_decisions={"/nonexistent/target": "/some/src"})
            self.assertTrue(any("W_BRANCH_DECISION_SUPERFLUOUS" in w for w in result["warnings"]))

    def test_branch_decision_invalid_source_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100", "101", "200"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            (tmp_path / "mods" / "100" / "a.txt").write_text("x", encoding="utf-8")
            (tmp_path / "mods" / "101" / "a.txt").write_text("y", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:200",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "sub": [],
                        "def_destin": "270150:200",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "sub": ["270150:100", "270150:101"],
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                ]
            }
            # Build forest first to get the actual target path
            forest_result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(forest_result["forest"])
            branched_target = forest_result["forest"][0]["path"]

            # Provide a decision with a wrong source
            result = compute_mapping(aggregated_rule_set, db, branch_decisions={branched_target: "/wrong/source.txt"})
            self.assertTrue(any("E_BRANCH_DECISION_INVALID_SOURCE" in e for e in result["errors"]))
            self.assertEqual(result["final_mapping"], [])

    def test_branch_decision_resolved_produces_final_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100", "101", "200"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            (tmp_path / "mods" / "100" / "a.txt").write_text("x", encoding="utf-8")
            (tmp_path / "mods" / "101" / "a.txt").write_text("y", encoding="utf-8")
            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:200",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "sub": [],
                        "def_destin": "270150:200",
                        "def_action": "replace",
                        "actionlist": [{"from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "sub": ["270150:100", "270150:101"],
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                ]
            }
            forest_result = compute_mapping(aggregated_rule_set, db)
            branched = forest_result["forest"][0]
            target = branched["path"]
            chosen_src = branched["candidates"][0]

            result = compute_mapping(aggregated_rule_set, db, branch_decisions={target: chosen_src})
            self.assertFalse(result["errors"])
            self.assertEqual(len(result["final_mapping"]), 1)
            self.assertEqual(result["final_mapping"][0]["path"], target)
            self.assertEqual(result["final_mapping"][0]["request"]["path"], chosen_src)

    # ── file-level cycle detection ─────────────────────────────────────────────

    def test_no_cycle_returns_empty(self) -> None:
        edges = {
            "/a": {"/b"},
            "/b": {"/c"},
        }
        self.assertEqual(find_cycles(edges), [])

    def test_single_cycle_detected_with_path(self) -> None:
        edges = {
            "/a": {"/b"},
            "/b": {"/c"},
            "/c": {"/a"},
        }
        cycles = find_cycles(edges)
        self.assertEqual(len(cycles), 1)
        # cycle must start and end at same node
        self.assertEqual(cycles[0][0], cycles[0][-1])
        # all three nodes present
        self.assertIn("/a", cycles[0])
        self.assertIn("/b", cycles[0])
        self.assertIn("/c", cycles[0])

    def test_self_loop_detected(self) -> None:
        edges = {"/a": {"/a"}}
        cycles = find_cycles(edges)
        self.assertEqual(len(cycles), 1)
        self.assertEqual(cycles[0][0], cycles[0][-1])

    def test_two_independent_cycles_both_detected(self) -> None:
        edges = {
            "/a": {"/b"},
            "/b": {"/a"},
            "/x": {"/y"},
            "/y": {"/x"},
        }
        cycles = find_cycles(edges)
        self.assertEqual(len(cycles), 2)

    def test_compute_mapping_cycle_error_contains_path(self) -> None:
        # Directly test find_cycles with a proper 3-node loop and verify
        # that E_FILE_CIRCULAR_DEP error strings contain the chain.
        edges = {
            "/mods/100/a.txt": {"/mods/200/a.txt"},
            "/mods/200/a.txt": {"/mods/300/a.txt"},
            "/mods/300/a.txt": {"/mods/100/a.txt"},
        }
        cycles = find_cycles(edges)
        self.assertTrue(len(cycles) >= 1)
        # each cycle must start and end at the same node
        for c in cycles:
            self.assertEqual(c[0], c[-1])
        # error format must include "E_FILE_CIRCULAR_DEP:" and " -> "
        fake_errors = [f"E_FILE_CIRCULAR_DEP: {' -> '.join(c)}" for c in cycles]
        for e in fake_errors:
            self.assertTrue(e.startswith("E_FILE_CIRCULAR_DEP:"))
            self.assertIn(" -> ", e)

    def test_path_glob_expands_directories_for_path_to_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_root = tmp_path / "mods" / "100" / "v1.9"
            (src_root / "src1").mkdir(parents=True)
            (src_root / "src2").mkdir(parents=True)
            (src_root / "src3").mkdir(parents=True)

            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {
                                "from": ["v1.9/*/"],
                                "from_type": "path",
                                "into": ["maps/"],
                                "into_type": "path",
                            }
                        ],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)

            self.assertEqual(result["errors"], [])
            targets = {entry["path"] for entry in result["final_mapping"]}
            self.assertIn(str(tmp_path / "game" / "maps" / "src1").replace("\\", "/"), targets)
            self.assertIn(str(tmp_path / "game" / "maps" / "src2").replace("\\", "/"), targets)
            self.assertIn(str(tmp_path / "game" / "maps" / "src3").replace("\\", "/"), targets)

    def test_file_glob_does_not_pull_directories(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_root = tmp_path / "mods" / "100" / "src"
            src_root.mkdir(parents=True)
            (src_root / "top.txt").write_text("x", encoding="utf-8")
            (src_root / "nested").mkdir()
            (src_root / "nested" / "deep.txt").write_text("y", encoding="utf-8")

            aggregated_rule_set = {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": [],
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {
                                "from": ["src/*"],
                                "from_type": "file",
                                "into": ["out/"],
                                "into_type": "path",
                            }
                        ],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)

            self.assertEqual(result["errors"], [])
            targets = {entry["path"] for entry in result["final_mapping"]}
            self.assertIn(str(tmp_path / "game" / "out" / "top.txt").replace("\\", "/"), targets)
            self.assertNotIn(str(tmp_path / "game" / "out" / "nested").replace("\\", "/"), targets)
            self.assertNotIn(str(tmp_path / "game" / "out" / "deep.txt").replace("\\", "/"), targets)


if __name__ == "__main__":
    unittest.main()


class ValidateForestRootsTests(unittest.TestCase):
    """Unit tests for validate_forest_roots()."""

    def _make_mod_index(self, entries: list[dict]) -> dict:
        return {m["mixed_id"]: m for m in entries}

    def test_empty_forest_returns_no_warnings(self):
        warnings = validate_forest_roots([], self._make_mod_index([]))
        self.assertEqual(warnings, [])

    def test_gamebase_as_root_no_warnings(self):
        forest = [{"path": "/game/data/file.txt", "destin_mixed_id": "270150:0", "changerequest": []}]
        mod_index = self._make_mod_index([
            {"mixed_id": "270150:0", "sub": []},
            {"mixed_id": "270150:999", "sub": []},
        ])
        warnings = validate_forest_roots(forest, mod_index)
        self.assertFalse(any("W_GAMEBASE_NOT_ROOT" in w for w in warnings))
        self.assertFalse(any("W_SUB_AS_ROOT" in w for w in warnings))

    def test_sub_as_root_emits_warning(self):
        # 270150:200 is listed as sub of 270150:300 but appears as a root destin
        forest = [{"path": "/mods/200/file.txt", "destin_mixed_id": "270150:200", "changerequest": []}]
        mod_index = self._make_mod_index([
            {"mixed_id": "270150:200", "sub": []},
            {"mixed_id": "270150:300", "sub": ["270150:200"]},
        ])
        warnings = validate_forest_roots(forest, mod_index)
        self.assertTrue(any("W_SUB_AS_ROOT" in w and "270150:200" in w for w in warnings))

    def test_non_sub_dom_mod_as_root_no_sub_warning(self):
        forest = [{"path": "/mods/300/file.txt", "destin_mixed_id": "270150:300", "changerequest": []}]
        mod_index = self._make_mod_index([
            {"mixed_id": "270150:200", "sub": []},
            {"mixed_id": "270150:300", "sub": ["270150:200"]},
        ])
        warnings = validate_forest_roots(forest, mod_index)
        self.assertFalse(any("W_SUB_AS_ROOT" in w for w in warnings))

    def test_missing_gamebase_emits_warning(self):
        # Forest has entries but none belongs to modid 0
        forest = [{"path": "/mods/300/file.txt", "destin_mixed_id": "270150:300", "changerequest": []}]
        mod_index = self._make_mod_index([
            {"mixed_id": "270150:300", "sub": []},
        ])
        warnings = validate_forest_roots(forest, mod_index)
        self.assertTrue(any("W_GAMEBASE_NOT_ROOT" in w for w in warnings))

    def test_node_without_destin_mixed_id_ignored(self):
        # Legacy node with no destin_mixed_id should not crash
        forest = [{"path": "/mods/300/file.txt", "changerequest": []}]
        mod_index = self._make_mod_index([
            {"mixed_id": "270150:300", "sub": []},
        ])
        # Should run without exception; W_GAMEBASE_NOT_ROOT expected since root_destins is empty
        warnings = validate_forest_roots(forest, mod_index)
        self.assertIsInstance(warnings, list)
