import json
import tempfile
import unittest
from pathlib import Path

from modmanager.iojson import dumps_pretty, load_json_file, write_json_file


class IoJsonTests(unittest.TestCase):
    def test_dumps_pretty(self):
        payload = dumps_pretty({"a": 1}, ensure_ascii=False, indent=2)
        self.assertIn('"a": 1', payload)

    def test_load_and_write_json_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.json"
            data = {"k": [1, 2, 3], "name": "测试"}
            write_json_file(p, data, ensure_ascii=False, indent=2)
            loaded = load_json_file(p)
            self.assertEqual(loaded, data)

    def test_load_json_file_parses_valid_json(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "raw.json"
            p.write_text(json.dumps({"x": True}), encoding="utf-8")
            self.assertEqual(load_json_file(p), {"x": True})


if __name__ == "__main__":
    unittest.main()
