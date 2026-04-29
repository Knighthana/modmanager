"""Comprehensive tests for the rule aggregator (modmanager_cli.rule_aggregator.aggregate)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from modmanager_cli.rule_aggregator import aggregate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_temp_kmm_rule(temp_dir: str, filename: str, content: dict) -> str:
    path = Path(temp_dir) / filename
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _make_temp_user_config(temp_dir: str) -> str:
    path = Path(temp_dir) / "user_config.json"
    path.write_text(json.dumps({"path_alias": []}, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _make_temp_user_config_custom(temp_dir: str, content: dict) -> str:
    path = Path(temp_dir) / "user_config.json"
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return str(path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAggregatorBasic(unittest.TestCase):
    """Basic aggregation tests."""

    def test_single_file_basic(self) -> None:
        """Load a single valid kmm_rule file, verify output structure."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "nickname": "TestMod",
                        "preview": ["prev1.png"],
                        "readme": ["readme.txt"],
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {
                                "from": ["data/file.txt"],
                                "from_type": "file",
                                "into": ["game_data/"],
                                "into_type": "path",
                            }
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            self.assertIn("operation", result)
            self.assertEqual(len(result["operation"]), 1)
            op = result["operation"][0]
            self.assertEqual(op["mixed_id"], "270150:100")
            self.assertEqual(op["nickname"], "TestMod")
            self.assertEqual(len(op["actionlist"]), 1)
            action = op["actionlist"][0]
            self.assertEqual(action["action"], "replace")
            self.assertEqual(action["destin"], "270150:0")
            self.assertIn("provenance_ref", action)
            self.assertTrue(action["provenance_ref"].startswith("/"))
            self.assertIn("action_order", action)
            self.assertIn("sidecar_ref", action)

    def test_multi_file_merge_same_mixed_id(self) -> None:
        """Two kmm_rule files with the same mixed_id — actionlists concatenated."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule1 = _make_temp_kmm_rule(td, "r1.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {
                                "from": ["a.txt"],
                                "from_type": "file",
                                "into": ["dest/"],
                                "into_type": "path",
                            }
                        ],
                    }
                ]
            })
            rule2 = _make_temp_kmm_rule(td, "r2.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {
                                "from": ["b.txt"],
                                "from_type": "file",
                                "into": ["dest/"],
                                "into_type": "path",
                            }
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule1, rule2], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            self.assertEqual(len(result["operation"]), 1)
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 2)
            self.assertEqual(op["actionlist"][0]["from"], ["a.txt"])
            self.assertEqual(op["actionlist"][1]["from"], ["b.txt"])

    def test_multi_file_preview_readme_merge(self) -> None:
        """Two files with overlapping preview/readme lists — extend + dedup."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule1 = _make_temp_kmm_rule(td, "r1.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "preview": ["a.png", "b.png"],
                        "readme": ["r1.md", "common.md"],
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    }
                ]
            })
            rule2 = _make_temp_kmm_rule(td, "r2.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "preview": ["b.png", "c.png"],
                        "readme": ["common.md", "r2.md"],
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule1, rule2], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(op["preview"], ["a.png", "b.png", "c.png"])
            self.assertEqual(op["readme"], ["r1.md", "common.md", "r2.md"])

    def test_nickname_last_wins(self) -> None:
        """Two files with different nicknames — second file's nickname wins."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule1 = _make_temp_kmm_rule(td, "r1.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "nickname": "FirstNick",
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    }
                ]
            })
            rule2 = _make_temp_kmm_rule(td, "r2.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "nickname": "SecondNick",
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule1, rule2], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(op["nickname"], "SecondNick")
            self.assertTrue(any("W_NICKNAME_CONFLICT" in w for w in warnings))


class TestAggregatorFiltering(unittest.TestCase):
    """Filtering tests — hold, destin=none, inheritance."""

    def test_hold_action_filtered(self) -> None:
        """Action with action='hold' should not appear in output."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [
                            {"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                            {"action": "replace", "destin": "270150:0", "from": ["b.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 1)
            self.assertEqual(op["actionlist"][0]["action"], "replace")

    def test_hold_action_from_def_action_filtered(self) -> None:
        """Action inheriting 'hold' from def_action should be filtered."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [
                            # No explicit action — inherits "hold" from def_action
                            {"destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 0)

    def test_destin_none_filtered(self) -> None:
        """Action with destin='none' should be filtered with warning."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "none", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 0)
            self.assertTrue(any("W_DESTIN_NONE_SKIPPED" in w for w in warnings))

    def test_def_action_inheritance(self) -> None:
        """Action without explicit action should inherit from def_action."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "create",
                        "actionlist": [
                            # No explicit action — inherits "create"
                            {"destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 1)
            self.assertEqual(op["actionlist"][0]["action"], "create")

    def test_def_destin_inheritance(self) -> None:
        """Action without explicit destin should inherit from def_destin."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            # No explicit destin — inherits "270150:0"
                            {"action": "replace", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 1)
            self.assertEqual(op["actionlist"][0]["destin"], "270150:0")

    def test_explicit_action_overrides_def(self) -> None:
        """Explicit action overrides def_action even when def_action is 'hold'."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [
                            {"action": "delete", "destin": "270150:0", "into": ["d/a.txt"], "into_type": "file"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 1)
            self.assertEqual(op["actionlist"][0]["action"], "delete")


class TestAggregatorPermission(unittest.TestCase):
    """Permission filtering tests."""

    def test_game_permission_allow(self) -> None:
        """Mod listed in game[].modid with base-target action passes permission check."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            self.assertEqual(len(result["operation"]), 1)
            self.assertEqual(len(result["operation"][0]["actionlist"]), 1)

    def test_game_permission_deny(self) -> None:
        """Mod NOT in game[].modid with base-target action → E_PERMISSION_DENIED_BASE."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["999"]},  # 100 is NOT listed
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            # The operation still exists but the action is removed
            self.assertIsNotNone(result)
            self.assertTrue(any("E_PERMISSION_DENIED_BASE" in e for e in errors))
            self.assertEqual(len(result["operation"][0]["actionlist"]), 0)

    def test_sub_permission_allow(self) -> None:
        """Mod listed in target's sub[] passes sub permission check."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": ["270150:50"],
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                    {
                        "mixed_id": "270150:50",
                        "def_destin": "270150:100",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:100", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    },
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            # Action targeting 270150:100 should be allowed since 270150:50 is in 270150:100's sub[]
            self.assertEqual(len(result["operation"][1]["actionlist"]), 1)

    def test_sub_permission_deny(self) -> None:
        """Mod NOT in target's sub[] → E_PERMISSION_DENIED_SUB."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "sub": ["270150:99"],  # 50 is NOT listed
                        "def_destin": "270150:0",
                        "def_action": "hold",
                        "actionlist": [],
                    },
                    {
                        "mixed_id": "270150:50",
                        "def_destin": "270150:100",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:100", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    },
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertTrue(any("E_PERMISSION_DENIED_SUB" in e for e in errors))
            self.assertEqual(len(result["operation"][1]["actionlist"]), 0)


class TestAggregatorInjection(unittest.TestCase):
    """Injection tests — provenance_ref, action_order, sidecar_ref."""

    def test_provenance_ref_absolute(self) -> None:
        """Verify provenance_ref is an absolute path."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            action = result["operation"][0]["actionlist"][0]
            self.assertTrue(action["provenance_ref"].startswith("/"), f"provenance_ref should be absolute: {action['provenance_ref']}")

    def test_action_order_injection(self) -> None:
        """Provide action_orders mapping, verify correct order value."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            action_orders = {"270150:100": 42}
            result, errors, warnings = aggregate([rule], uc, action_orders=action_orders)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            action = result["operation"][0]["actionlist"][0]
            self.assertEqual(action["action_order"], 42)

    def test_sidecar_ref_injection(self) -> None:
        """Provide sidecar_refs mapping, verify correct injection."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule_path = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            resolved_path = str(Path(rule_path).resolve())
            sidecar_refs = {resolved_path: {"270150:100": {0: "my-sidecar-ref"}}}
            result, errors, warnings = aggregate([rule_path], uc, sidecar_refs=sidecar_refs)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            action = result["operation"][0]["actionlist"][0]
            self.assertEqual(action["sidecar_ref"], "my-sidecar-ref")


class TestAggregatorErrorHandling(unittest.TestCase):
    """Error handling tests."""

    def test_invalid_kmm_rule_not_dict(self) -> None:
        """Load a non-dict kmm_rule file → E_KMM_RULE_INVALID."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", [1, 2, 3])

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNone(result)
            self.assertTrue(any("E_KMM_RULE_INVALID" in e for e in errors))

    def test_invalid_kmm_rule_missing_mod_key(self) -> None:
        """Load a kmm_rule without 'mod' key → E_KMM_RULE_INVALID."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {"not_mod": []})

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNone(result)
            self.assertTrue(any("E_KMM_RULE_INVALID" in e for e in errors))

    def test_invalid_kmm_rule_load_failed(self) -> None:
        """Load a non-existent kmm_rule file → E_KMM_RULE_LOAD_FAILED."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)

            result, errors, warnings = aggregate(["/nonexistent/rule.json"], uc)

            self.assertIsNone(result)
            self.assertTrue(any("E_KMM_RULE_LOAD_FAILED" in e for e in errors))

    def test_missing_user_config(self) -> None:
        """Non-existent user_config path → E_USER_CONFIG_LOAD_FAILED."""
        with tempfile.TemporaryDirectory() as td:
            result, errors, warnings = aggregate([], "/nonexistent/user_config.json")

            self.assertIsNone(result)
            self.assertTrue(any("E_USER_CONFIG_LOAD_FAILED" in e for e in errors))

    def test_output_file_write(self) -> None:
        """Provide output_path, verify file is written with correct content."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "game": [
                    {"appid": "270150", "modid": ["100"]},
                ],
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "replace",
                        "actionlist": [
                            {"action": "replace", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })
            output_path = Path(td) / "output.json"

            result, errors, warnings = aggregate([rule], uc, output_path=str(output_path))

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            self.assertTrue(output_path.exists())
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["operation"][0]["mixed_id"], "270150:100")
            self.assertEqual(written["operation"][0]["actionlist"][0]["action"], "replace")


class TestAggregatorEmptyActions(unittest.TestCase):
    """Edge cases — empty actionlists after filtering."""

    def test_all_actions_filtered_triggers_warning(self) -> None:
        """All actions filtered out → W_EMPTY_ACTIONLIST_AFTER_FILTER."""
        with tempfile.TemporaryDirectory() as td:
            uc = _make_temp_user_config(td)
            rule = _make_temp_kmm_rule(td, "rule.json", {
                "mod": [
                    {
                        "mixed_id": "270150:100",
                        "def_destin": "270150:0",
                        "def_action": "hold",  # all actions would be hold → filtered
                        "actionlist": [
                            {"action": "hold", "destin": "270150:0", "from": ["a.txt"], "from_type": "file", "into": ["d/"], "into_type": "path"},
                        ],
                    }
                ]
            })

            result, errors, warnings = aggregate([rule], uc)

            self.assertIsNotNone(result)
            self.assertEqual(errors, [])
            op = result["operation"][0]
            self.assertEqual(len(op["actionlist"]), 0)
            self.assertTrue(any("W_EMPTY_ACTIONLIST_AFTER_FILTER" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
