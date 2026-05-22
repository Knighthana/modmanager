"""Tests for the modmanager_web module entrypoint."""

from __future__ import annotations

import builtins
import unittest
from unittest.mock import patch

from hana_modmgr_web.__main__ import main


class WebEntrypointTests(unittest.TestCase):
    def test_main_exits_cleanly_when_uvicorn_is_missing(self) -> None:
        original_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "uvicorn":
                raise ImportError("No module named uvicorn")
            return original_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(SystemExit) as ctx:
                main()

        self.assertEqual(ctx.exception.code, 2)
