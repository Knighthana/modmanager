"""Tests for input validation module."""

import unittest

from modmgr.validation import validate_aggregated_rule_set, validate_database


class ValidateAggregatedRuleSetTests(unittest.TestCase):
    def test_valid_minimal_aggregated_rule_set(self):
        aggregated_rule_set = {"operation": []}
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertEqual(errs, [])

    def test_valid_single_operation(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": [],
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertEqual(errs, [])

    def test_aggregated_rule_set_not_dict(self):
        errs = validate_aggregated_rule_set([])
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e for e in errs))

    def test_aggregated_rule_set_missing_operation_key(self):
        errs = validate_aggregated_rule_set({"other": []})
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "operation" in e for e in errs))

    def test_operation_not_list(self):
        errs = validate_aggregated_rule_set({"operation": "not_a_list"})
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "list" in e for e in errs))

    def test_operation_entry_not_dict(self):
        errs = validate_aggregated_rule_set({"operation": ["string_entry"]})
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e for e in errs))

    def test_mixed_id_missing(self):
        errs = validate_aggregated_rule_set({"operation": [{"other_field": "value"}]})
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "mixed_id" in e for e in errs))

    def test_mixed_id_not_string(self):
        errs = validate_aggregated_rule_set({"operation": [{"mixed_id": 123}]})
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "mixed_id" in e for e in errs))

    def test_mixed_id_empty(self):
        errs = validate_aggregated_rule_set({"operation": [{"mixed_id": ""}]})
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "empty" in e for e in errs))

    def test_mixed_id_invalid_format(self):
        errs = validate_aggregated_rule_set({"operation": [{"mixed_id": "270150"}]})  # missing modid part
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "appid:modid" in e for e in errs))

    def test_mixed_id_not_unique(self):
        aggregated_rule_set = {
            "operation": [
                {"mixed_id": "270150:100", "actionlist": []},
                {"mixed_id": "270150:100", "actionlist": []},
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "not unique" in e for e in errs))

    def test_actionlist_not_list(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": "not_a_list",
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "actionlist" in e for e in errs))

    def test_actionlist_item_not_dict(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": ["not_a_dict"],
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e for e in errs))

    def test_actionlist_missing_from_for_replace(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": [{"action": "replace", "destin": "270150:0", "into": ["data/"], "into_type": "dir"}],  # missing 'from'
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "from" in e for e in errs))

    def test_actionlist_missing_into_for_replace(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": [{"action": "replace", "destin": "270150:0", "from": ["file.txt"], "from_type": "file"}],  # missing 'into'
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "into" in e for e in errs))

    def test_actionlist_destin_invalid_format(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": [
                        {
                            "action": "replace",
                            "destin": "bad_format",
                            "from": ["file.txt"],
                            "from_type": "file",
                            "into": ["data/"],
                            "into_type": "dir",
                        }
                    ],
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertTrue(any("E_AGGREGATED_RULE_SET_INVALID" in e and "destin" in e for e in errs))

    def test_actionlist_destin_none_allowed(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": [
                        {
                            "action": "replace",
                            "destin": "none",
                            "from": ["file.txt"],
                            "from_type": "file",
                            "into": ["data/"],
                            "into_type": "dir",
                        }
                    ],
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertEqual(errs, [])

    def test_actionlist_rejects_file_and_path_type(self):
        aggregated_rule_set = {
            "operation": [
                {
                    "mixed_id": "270150:100",
                    "actionlist": [
                        {
                            "action": "replace",
                            "destin": "270150:0",
                            "from": ["src/*"],
                            "from_type": "file_and_path",
                            "into": ["dest/"],
                            "into_type": "dir",
                        }
                    ],
                }
            ]
        }
        errs = validate_aggregated_rule_set(aggregated_rule_set)
        self.assertTrue(any("from_type" in e and "file, dir" in e for e in errs))


class ValidateDatabaseTests(unittest.TestCase):
    def test_valid_minimal_database(self):
        database = {"game": []}
        errs = validate_database(database)
        self.assertEqual(errs, [])

    def test_valid_single_game(self):
        database = {
            "game": [
                {
                    "appid": "270150",
                    "basepath": "/mnt/c/Games/MyGame",
                    "modpath": "/mnt/d/Workshop/mods",
                }
            ]
        }
        errs = validate_database(database)
        self.assertEqual(errs, [])

    def test_database_not_dict(self):
        errs = validate_database([])
        self.assertTrue(any("E_DATABASE_INVALID" in e for e in errs))

    def test_database_missing_game_key(self):
        errs = validate_database({"other": []})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "game" in e for e in errs))

    def test_game_not_list(self):
        errs = validate_database({"game": "not_a_list"})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "list" in e for e in errs))

    def test_game_entry_not_dict(self):
        errs = validate_database({"game": ["string_entry"]})
        self.assertTrue(any("E_DATABASE_INVALID" in e for e in errs))

    def test_appid_missing(self):
        errs = validate_database({"game": [{"basepath": "/path", "modpath": "/path"}]})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "appid" in e for e in errs))

    def test_appid_not_string(self):
        errs = validate_database({"game": [{"appid": 123, "basepath": "/path", "modpath": "/path"}]})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "appid" in e for e in errs))

    def test_appid_empty(self):
        errs = validate_database({"game": [{"appid": "", "basepath": "/path", "modpath": "/path"}]})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "empty" in e for e in errs))

    def test_appid_not_unique_allowed(self):
        """Duplicate appids are allowed — resolved by managed_entries or branch_decisions."""
        database = {
            "game": [
                {"appid": "270150", "basepath": "/path1", "modpath": "/path1"},
                {"appid": "270150", "basepath": "/path2", "modpath": "/path2"},
            ]
        }
        errs = validate_database(database)
        # No uniqueness error — duplicates are valid
        self.assertFalse(any("not unique" in e for e in errs))

    def test_basepath_missing(self):
        errs = validate_database({"game": [{"appid": "270150", "modpath": "/path"}]})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "basepath" in e for e in errs))

    def test_basepath_not_string(self):
        errs = validate_database({"game": [{"appid": "270150", "basepath": 123, "modpath": "/path"}]})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "basepath" in e for e in errs))

    def test_modpath_missing(self):
        errs = validate_database({"game": [{"appid": "270150", "basepath": "/path"}]})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "modpath" in e for e in errs))

    def test_modpath_not_string(self):
        errs = validate_database({"game": [{"appid": "270150", "basepath": "/path", "modpath": 123}]})
        self.assertTrue(any("E_DATABASE_INVALID" in e and "modpath" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
