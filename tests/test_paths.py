import unittest

from modmgr.paths import (
    build_game_index,
    is_numeric_modid,
    mod_root_from_mixed_id,
    normalize_posix,
    path_for_mixed_id,
    split_mixed_id,
)


class PathsModuleTests(unittest.TestCase):
    def _db(self):
        return {
            "game": [
                {
                    "appid": "270150",
                    "basepath": r"C:\\Games\\MyGame",
                    "modpath": r"D:\\Workshop\\mods",
                }
            ]
        }

    def test_split_mixed_id(self):
        self.assertEqual(split_mixed_id("270150:100"), ("270150", "100"))
        self.assertIsNone(split_mixed_id("270150"))
        self.assertIsNone(split_mixed_id(":100"))

    def test_is_numeric_modid(self):
        self.assertTrue(is_numeric_modid("270150:100"))
        self.assertFalse(is_numeric_modid("270150:local_dev"))

    def test_normalize_posix(self):
        self.assertEqual(normalize_posix(r"D:\\Workshop\\mods\\100\\"), "/mnt/d/Workshop/mods/100")

    def test_mod_root_from_mixed_id_gamebase(self):
        idx = build_game_index(self._db())
        self.assertEqual(mod_root_from_mixed_id("270150:0", idx), "/mnt/c/Games/MyGame")

    def test_mod_root_from_mixed_id_workshop(self):
        idx = build_game_index(self._db())
        self.assertEqual(mod_root_from_mixed_id("270150:100", idx), "/mnt/d/Workshop/mods/100")

    def test_path_for_mixed_id_with_relative(self):
        idx = build_game_index(self._db())
        p = path_for_mixed_id("270150:100", idx, r"Data\\a.txt")
        self.assertEqual(p, "/mnt/d/Workshop/mods/100/Data/a.txt")

    def test_path_for_mixed_id_invalid(self):
        idx = build_game_index(self._db())
        self.assertIsNone(path_for_mixed_id("bad", idx))


if __name__ == "__main__":
    unittest.main()
