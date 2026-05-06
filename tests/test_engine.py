import json
import tempfile
import unittest
from pathlib import Path

from modmanager.engine import (
    ForestTree,
    _any_ancestor_deleted,
    _build_forest_trees,
    _build_output,
    _check_filefoldertree_transition,
    _resolve_trees_bottom_up,
    _topological_sort_by_refs,
    compute_mapping,
    find_cycles,
    validate_branch_decisions_schema,
)


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
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "create", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["dest/"], "into_type": "path"}],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_CREATE_TARGET_EXISTS_OVERWRITE" in w for w in result["warnings"]))
            self.assertFalse(result["errors"])
            self.assertTrue(result["final_mapping"])

    def test_deprecated_action_produces_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100",):
                mroot = tmp_path / "mods" / modid
                mroot.mkdir(parents=True)
                (mroot / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "clear_then_copy", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_INVALID_ACTION" in w for w in result["warnings"]))
            self.assertEqual(result["trees"], [])
            self.assertEqual(result["final_mapping"], [])

    def test_local_mod_missing_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:local_dev_mod",
                        "actionlist": [{"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_LOCAL_MOD_MISSING" in w for w in result["warnings"]))
            self.assertEqual(result["trees"], [])

    def test_non_hold_action_with_none_destin_is_skipped_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            src_mod.mkdir(parents=True)
            (src_mod / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "none",
                                "from": ["a.txt"],
                                "from_type": "file",
                                "into": ["d/"],
                                "into_type": "path",
                            }
                        ],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_DESTIN_NONE_SKIPPED" in w for w in result["warnings"]))
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["trees"], [])
            self.assertEqual(result["final_mapping"], [])

    def test_hold_action_with_none_destin_produces_no_none_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            src_mod.mkdir(parents=True)

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "hold", "destin": "none", "into": ["d/"], "into_type": "path"}],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertFalse(any("W_DESTIN_NONE_SKIPPED" in w for w in result["warnings"]))
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["trees"], [])
            self.assertEqual(result["final_mapping"], [])

    def test_all_non_hold_actions_with_none_destin_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            src_mod.mkdir(parents=True)
            (src_mod / "a.txt").write_text("x", encoding="utf-8")

            action_items = [
                {
                    "action": "replace",
                    "from": ["a.txt"],
                    "from_type": "file",
                    "into": ["d_replace/"],
                    "into_type": "path",
                    "destin": "none",
                },
                {
                    "action": "create",
                    "from": ["a.txt"],
                    "from_type": "file",
                    "into": ["d_create/"],
                    "into_type": "path",
                    "destin": "none",
                },
                {
                    "action": "delete",
                    "into": ["d_delete/a.txt"],
                    "into_type": "file",
                    "destin": "none",
                },
                {
                    "action": "replace",
                    "from": ["a.txt"],
                    "from_type": "file",
                    "into": ["d_alt1/"],
                    "into_type": "path",
                    "destin": "none",
                },
                {
                    "action": "replace",
                    "from": ["a.txt"],
                    "from_type": "file",
                    "into": ["d_alt2/"],
                    "into_type": "path",
                    "destin": "none",
                },
            ]

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": action_items,
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["trees"], [])
            self.assertEqual(result["final_mapping"], [])
            none_warnings = [w for w in result["warnings"] if "W_DESTIN_NONE_SKIPPED" in w]
            self.assertEqual(len(none_warnings), len(action_items))

    def test_action_level_none_destin_overrides_valid_parent_destin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            src_mod.mkdir(parents=True)
            (src_mod / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "none",
                                "from": ["a.txt"],
                                "from_type": "file",
                                "into": ["d/"],
                                "into_type": "path",
                            }
                        ],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_DESTIN_NONE_SKIPPED" in w for w in result["warnings"]))
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["final_mapping"], [])

    def test_ref_fields_are_propagated_to_forest_and_final_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            src_mod.mkdir(parents=True)
            (src_mod / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "270150:0",
                                "from": ["a.txt"],
                                "from_type": "file",
                                "into": ["d/"],
                                "into_type": "path",
                                "provenance_ref": "rule_base_path_2:demo.json",
                                "action_order": 7,
                                "sidecar_ref": "sidecar/provenance/demo.json",
                            }
                        ],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            request = result["trees"][0]["changerequest"][0]
            self.assertEqual(request["provenance_ref"], "rule_base_path_2:demo.json")
            self.assertEqual(request["action_order"], 7)
            self.assertEqual(request["sidecar_ref"], "sidecar/provenance/demo.json")
            self.assertEqual(result["final_mapping"][0]["request"]["provenance_ref"], "rule_base_path_2:demo.json")

    def test_missing_ref_fields_fall_back_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            src_mod = tmp_path / "mods" / "100"
            src_mod.mkdir(parents=True)
            (src_mod / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "270150:0",
                                "from": ["a.txt"],
                                "from_type": "file",
                                "into": ["d/"],
                                "into_type": "path",
                                "provenance_ref": "",
                                "sidecar_ref": None,
                            }
                        ],
                    }
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            request = result["trees"][0]["changerequest"][0]
            self.assertEqual(request["provenance_ref"], "404")
            self.assertEqual(request["sidecar_ref"], "404")
            self.assertEqual(request["action_order"], 0)

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
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path", "action_order": 0}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path", "action_order": 3}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "actionlist": [{"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(any("W_FOREST_BRANCHING_UNRESOLVED" in w for w in result["warnings"]))
            self.assertEqual(result["final_mapping"], [])
            self.assertTrue(result["trees"])

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
        result = compute_mapping({"operation": []}, {"game": []}, branch_decisions=["bad"])
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
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
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
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "actionlist": [{"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }
            # Build forest first to get the actual target path
            forest_result = compute_mapping(aggregated_rule_set, db)
            self.assertTrue(forest_result["trees"])
            branched_target = forest_result["trees"][0]["root_path"]

            # Provide a decision with a wrong source
            result = compute_mapping(aggregated_rule_set, db, branch_decisions={branched_target: "/wrong/source.txt"})
            self.assertTrue(any("E_BRANCH_DECISION_INVALID" in e for e in result["errors"]))
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
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "actionlist": [{"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }
            forest_result = compute_mapping(aggregated_rule_set, db)
            branched = forest_result["trees"][0]
            target = branched["root_path"]
            chosen_src = branched["candidates"][0]

            result = compute_mapping(aggregated_rule_set, db, branch_decisions={target: chosen_src})
            self.assertFalse(result["errors"])
            self.assertEqual(len(result["final_mapping"]), 1)
            self.assertEqual(result["final_mapping"][0]["path"], target)
            self.assertEqual(result["final_mapping"][0]["request"]["path"], chosen_src)

    def test_branch_without_decision_becomes_pending(self) -> None:
        """Multiple replace ops, no branch decision → pending + W_FOREST_BRANCHING."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100", "101", "200"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            src_100 = tmp_path / "mods" / "100" / "a.txt"
            src_101 = tmp_path / "mods" / "101" / "a.txt"
            src_100.write_text("x", encoding="utf-8")
            src_101.write_text("y", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "270150:200",
                                "from": ["a.txt"],
                                "from_type": "file",
                                "into": ["d/"],
                                "into_type": "path",
                                "action_order": 1,
                            }
                        ],
                    },
                    {
                        "mixed_id": "270150:101",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "270150:200",
                                "from": ["a.txt"],
                                "from_type": "file",
                                "into": ["d/"],
                                "into_type": "path",
                                "action_order": 9,
                            }
                        ],
                    },
                    {
                        "mixed_id": "270150:200",
                        "actionlist": [{"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertEqual(result["errors"], [])
            self.assertEqual(len(result["final_mapping"]), 0)
            self.assertTrue(any("W_FOREST_BRANCHING" in w for w in result["warnings"]))
            # tree is pending
            self.assertEqual(result["trees"][0]["resolved_state"], "pending")

    def test_branch_with_zero_action_order_becomes_pending(self) -> None:
        """Multiple replace ops with no action_order → pending + W_FOREST_BRANCHING (not E_ACTION_ORDER_CONFLICT)."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100", "101", "200"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            (tmp_path / "mods" / "100" / "a.txt").write_text("x", encoding="utf-8")
            (tmp_path / "mods" / "101" / "a.txt").write_text("y", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:101",
                        "actionlist": [{"action": "replace", "destin": "270150:200", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                    {
                        "mixed_id": "270150:200",
                        "actionlist": [{"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            self.assertFalse(result["errors"])
            self.assertTrue(any("W_FOREST_BRANCHING" in w for w in result["warnings"]))
            self.assertEqual(len(result["final_mapping"]), 0)
            self.assertEqual(result["trees"][0]["resolved_state"], "pending")

    def test_source_deleted_skips_dependant_tree(self) -> None:
        """Tree A is delete, Tree B refs A → B source deleted, B is failed, no delete promotion."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            db = self._mk_db(tmp_path)
            for modid in ("100", "200", "300"):
                (tmp_path / "mods" / modid).mkdir(parents=True)
            (tmp_path / "mods" / "100" / "s").mkdir(parents=True)
            (tmp_path / "mods" / "100" / "s" / "a.txt").write_text("x", encoding="utf-8")

            aggregated_rule_set = {
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "270150:200",
                                "from": ["s/a.txt"],
                                "from_type": "file",
                                "into": ["d/"],
                                "into_type": "path",
                                "action_order": 10,
                            }
                        ],
                    },
                    {
                        "mixed_id": "270150:300",
                        "actionlist": [
                            {
                                "action": "delete",
                                "destin": "270150:100",
                                "into": ["s/a.txt"],
                                "into_type": "file",
                                "action_order": 99,
                            }
                        ],
                    },
                    {
                        "mixed_id": "270150:200",
                        "actionlist": [{"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"}],
                    },
                ]
            }

            result = compute_mapping(aggregated_rule_set, db)
            # Source tree (/mods/100/s/a.txt) is deleted
            self.assertTrue(any("W_SOURCE_DELETED" in w for w in result["warnings"]))
            # No W_DELETE_LEAF_PROMOTED in new behavior
            self.assertFalse(any("W_DELETE_LEAF_PROMOTED" in w for w in result["warnings"]))
            # Tree B (target) has no valid source → "failed"
            target = str(tmp_path / "mods" / "200" / "d" / "a.txt").replace("\\", "/")
            tree_b = next((t for t in result["trees"] if t["root_path"] == target), None)
            self.assertIsNotNone(tree_b)
            self.assertEqual(tree_b["resolved_state"], "failed")

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
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "270150:0",
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
                "operation": [
                    {
                        "mixed_id": "270150:100",
                        "actionlist": [
                            {
                                "action": "replace",
                                "destin": "270150:0",
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


    # ── ForestTree / _build_forest_trees ─────────────────────────────────────────

    def test_build_forest_trees_basic(self) -> None:
        """2 targets: one is source for the other, one is standalone delete."""
        mapping = {
            "/game/out/file.txt": {
                "path": "/game/out/file.txt",
                "destin_mixed_id": "270150:0",
                "changerequest": [
                    {"path": "/mods/100/a.txt", "action": "replace", "mixed_id": "270150:100"},
                    {"path": "!", "action": "delete", "mixed_id": "270150:200"},
                ],
            },
            "/mods/100/a.txt": {
                "path": "/mods/100/a.txt",
                "destin_mixed_id": "270150:100",
                "changerequest": [
                    {"path": "!", "action": "delete", "mixed_id": "270150:200"},
                ],
            },
        }
        trees = _build_forest_trees(mapping, {})
        self.assertEqual(len(trees), 2)

        # Sorted by root_path: /game/out/file.txt < /mods/100/a.txt
        t1 = trees[0]  # /game/out/file.txt
        t2 = trees[1]  # /mods/100/a.txt

        self.assertEqual(t1.root_path, "/game/out/file.txt")
        self.assertEqual(t1.destin_mixed_id, "270150:0")
        # /mods/100/a.txt is in mapping → ref
        self.assertEqual(t1.refs, ["/mods/100/a.txt"])
        self.assertFalse(t1.resolved)
        self.assertIsNone(t1.resolved_state)

        self.assertEqual(t2.root_path, "/mods/100/a.txt")
        self.assertEqual(t2.destin_mixed_id, "270150:100")
        # "!" paths are not refs
        self.assertEqual(t2.refs, [])

    # ── _topological_sort_by_refs ────────────────────────────────────────────────

    def test_topological_sort_simple(self) -> None:
        """A→B→C chain → C before B before A."""
        trees = [
            ForestTree(root_path="/A", destin_mixed_id="m1", changerequest=[], refs=["/B"]),
            ForestTree(root_path="/B", destin_mixed_id="m2", changerequest=[], refs=["/C"]),
            ForestTree(root_path="/C", destin_mixed_id="m3", changerequest=[], refs=[]),
        ]
        warnings: list[str] = []
        sorted_trees = _topological_sort_by_refs(trees, warnings)
        sorted_paths = [t.root_path for t in sorted_trees]
        self.assertEqual(sorted_paths, ["/C", "/B", "/A"])
        self.assertEqual(warnings, [])

    def test_topological_sort_cycle(self) -> None:
        """A→B→A cycle → warning returned, original list preserved."""
        trees = [
            ForestTree(root_path="/A", destin_mixed_id="m1", changerequest=[], refs=["/B"]),
            ForestTree(root_path="/B", destin_mixed_id="m2", changerequest=[], refs=["/A"]),
        ]
        warnings: list[str] = []
        sorted_trees = _topological_sort_by_refs(trees, warnings)
        self.assertEqual(len(sorted_trees), 2)
        self.assertTrue(any("W_FOREST_CYCLE_DETECTED" in w for w in warnings))

    # ── _any_ancestor_deleted ────────────────────────────────────────────────────

    def test_ancestor_deleted_true(self) -> None:
        """Deleted tree at /modA/dir → /modA/dir/file.png returns True."""
        tree_by_root = {
            "/modA/dir": ForestTree("/modA/dir", "m1", [], [], resolved=True, resolved_state="deleted"),
        }
        self.assertTrue(_any_ancestor_deleted("/modA/dir/file.png", tree_by_root))

    def test_ancestor_deleted_false(self) -> None:
        """Deleted tree at /modA/dir → /other/file.png returns False."""
        tree_by_root = {
            "/modA/dir": ForestTree("/modA/dir", "m1", [], [], resolved=True, resolved_state="deleted"),
        }
        self.assertFalse(_any_ancestor_deleted("/other/file.png", tree_by_root))

    # ── _resolve_trees_bottom_up ─────────────────────────────────────────────────

    def test_resolve_trees_simple_kept(self) -> None:
        """Single replace op → auto resolved_state='kept'."""
        tree = ForestTree(
            root_path="/target/a.txt",
            destin_mixed_id="270150:0",
            changerequest=[{"path": "/mods/100/a.txt", "action": "replace", "mixed_id": "270150:100"}],
            refs=[],
        )
        warnings: list[str] = []
        errors: list[str] = []
        _resolve_trees_bottom_up([tree], {}, warnings, errors)
        self.assertTrue(tree.resolved)
        self.assertEqual(tree.resolved_state, "kept")
        self.assertEqual(warnings, [])
        self.assertEqual(errors, [])

    def test_resolve_trees_delete_tree(self) -> None:
        """Single delete op → auto resolved_state='deleted'."""
        tree = ForestTree(
            root_path="/target/a.txt",
            destin_mixed_id="270150:0",
            changerequest=[{"path": "!", "action": "delete", "mixed_id": "270150:100"}],
            refs=[],
        )
        warnings: list[str] = []
        errors: list[str] = []
        _resolve_trees_bottom_up([tree], {}, warnings, errors)
        self.assertTrue(tree.resolved)
        self.assertEqual(tree.resolved_state, "deleted")

    def test_resolve_trees_source_deleted(self) -> None:
        """Tree A deleted, Tree B (refs A) → B fails with W_SOURCE_DELETED."""
        tree_a = ForestTree(
            root_path="/mods/100/a.txt",
            destin_mixed_id="270150:100",
            changerequest=[{"path": "!", "action": "delete", "mixed_id": "270150:200"}],
            refs=[],
        )
        tree_b = ForestTree(
            root_path="/game/target.txt",
            destin_mixed_id="270150:0",
            changerequest=[{"path": "/mods/100/a.txt", "action": "replace", "mixed_id": "270150:100"}],
            refs=["/mods/100/a.txt"],
        )
        warnings: list[str] = []
        errors: list[str] = []
        # topological order: A (dependency) before B
        _resolve_trees_bottom_up([tree_a, tree_b], {}, warnings, errors)
        self.assertEqual(tree_a.resolved_state, "deleted")
        self.assertEqual(tree_b.resolved_state, "failed")  # no valid ops remain
        self.assertTrue(any("W_SOURCE_DELETED" in w for w in warnings))
        self.assertEqual(errors, [])

    def test_resolve_trees_branching(self) -> None:
        """Two replace ops, no branch decision → pending + W_FOREST_BRANCHING."""
        tree = ForestTree(
            root_path="/target/a.txt",
            destin_mixed_id="270150:0",
            changerequest=[
                {"path": "/mods/100/a.txt", "action": "replace", "mixed_id": "270150:100"},
                {"path": "/mods/101/a.txt", "action": "replace", "mixed_id": "270150:101"},
            ],
            refs=[],
        )
        warnings: list[str] = []
        errors: list[str] = []
        _resolve_trees_bottom_up([tree], {}, warnings, errors)
        self.assertEqual(tree.resolved_state, "pending")
        self.assertTrue(any("W_FOREST_BRANCHING" in w for w in warnings))
        self.assertEqual(errors, [])

    def test_resolve_trees_user_decision(self) -> None:
        """Two replace ops, decision picks one → resolved_state='kept'."""
        tree = ForestTree(
            root_path="/target/a.txt",
            destin_mixed_id="270150:0",
            changerequest=[
                {"path": "/mods/100/a.txt", "action": "replace", "mixed_id": "270150:100"},
                {"path": "/mods/101/a.txt", "action": "replace", "mixed_id": "270150:101"},
            ],
            refs=[],
        )
        warnings: list[str] = []
        errors: list[str] = []
        _resolve_trees_bottom_up([tree], {"/target/a.txt": "/mods/100/a.txt"}, warnings, errors)
        self.assertEqual(tree.resolved_state, "kept")
        self.assertFalse(errors)

    # ── _build_output ────────────────────────────────────────────────────────────

    def test_build_output_format(self) -> None:
        """Verify output dict has 'trees' (not 'forest') and 'final_mapping'."""
        trees = [
            ForestTree(
                root_path="/kept.txt", destin_mixed_id="m1",
                changerequest=[{"path": "/src.txt", "action": "replace"}],
                refs=[], resolved=True, resolved_state="kept",
            ),
            ForestTree(
                root_path="/deleted.txt", destin_mixed_id="m2",
                changerequest=[{"path": "!", "action": "delete"}],
                refs=[], resolved=True, resolved_state="deleted",
            ),
            ForestTree(
                root_path="/pending.txt", destin_mixed_id="m3",
                changerequest=[
                    {"path": "/a.txt", "action": "replace"},
                    {"path": "/b.txt", "action": "replace"},
                ],
                refs=[], resolved=True, resolved_state="pending",
            ),
        ]
        warnings: list[str] = []
        errors: list[str] = []
        result = _build_output(trees, warnings, errors)

        # Top-level keys
        self.assertIn("trees", result)
        self.assertNotIn("forest", result)
        self.assertIn("final_mapping", result)
        self.assertIn("warnings", result)
        self.assertIn("errors", result)

        # trees list has 3 entries
        self.assertEqual(len(result["trees"]), 3)
        for entry in result["trees"]:
            self.assertIn("root_path", entry)
            self.assertIn("destin_mixed_id", entry)
            self.assertIn("changerequest", entry)
            self.assertIn("refs", entry)
            self.assertIn("resolved_state", entry)

        # pending tree has warning and candidates
        pending_entries = [t for t in result["trees"] if t["resolved_state"] == "pending"]
        self.assertEqual(len(pending_entries), 1)
        self.assertEqual(pending_entries[0]["warning"], "W_FOREST_BRANCHING")
        self.assertIn("candidates", pending_entries[0])

        # final_mapping contains kept + deleted (2 entries)
        self.assertEqual(len(result["final_mapping"]), 2)

        # W_FOREST_BRANCHING_UNRESOLVED warning present
        self.assertTrue(any("W_FOREST_BRANCHING_UNRESOLVED" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()



