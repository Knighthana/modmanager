from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def _load_rule_aggregator_module():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "cli-hmi" / "rule_aggregator.py"
    spec = importlib.util.spec_from_file_location("rule_aggregator", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("failed to load rule_aggregator module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RuleAggregatorTests(unittest.TestCase):
    def test_single_rule_aggregation_success(self) -> None:
        module = _load_rule_aggregator_module()
        payload = {
            "mod": [
                {
                    "mixed_id": "270150:100",
                    "sub": [],
                    "def_destin": "270150:0",
                    "def_action": "replace",
                    "actionlist": [
                        {
                            "from": ["a\\\\b\\\\c.txt"],
                            "from_type": "file",
                            "into": ["x\\\\y/"],
                            "into_type": "path",
                        }
                    ],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rule.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            aggregated, errors, warnings = module.aggregate_single_kmm_rule_file(str(path))

        self.assertEqual(errors, [])
        self.assertIsNotNone(aggregated)
        action = aggregated["mod"][0]["actionlist"][0]
        # provenance_ref defaults to the absolute path of the rule file
        self.assertTrue(action["provenance_ref"].endswith("rule.json"))
        # sidecar_ref defaults to "undesignated" when not supplied
        self.assertEqual(action["sidecar_ref"], "undesignated")
        self.assertEqual(action["action_order"], 0)
        self.assertEqual(action["from"], ["a/b/c.txt"])
        self.assertEqual(action["into"], ["x/y/"])
        self.assertTrue(any(w.startswith("W_PROVENANCE_REF_DEFAULTED") for w in warnings))

    def test_invalid_rule_returns_errors(self) -> None:
        module = _load_rule_aggregator_module()
        payload = {
            "mod": [
                {
                    "mixed_id": "bad-id",
                    "actionlist": [],
                }
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rule.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            aggregated, errors, _warnings = module.aggregate_single_kmm_rule_file(str(path))

        self.assertIsNone(aggregated)
        self.assertTrue(errors)
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
