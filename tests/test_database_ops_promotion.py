"""Tests for database_ops promotion (裁定 7): generate_database migration.

SPEC: repo_test/database_ops_promotion.md
Tests: T-DB-01 through T-DB-10
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import modmgr.bootstrap as bootstrap_module
import modmgr.database_ops as database_ops_module


class TestBootstrapBoundary(TestCase):
    """T-DB-01 ~ T-DB-03: bootstrap no longer exports generate_database."""

    def test_t_db_01_import_bootstrap_generate_database_raises(self) -> None:
        """T-DB-01: from modmgr.bootstrap import generate_database → ImportError."""
        with self.assertRaises(ImportError):
            # noinspection PyUnresolvedReferences
            from modmgr.bootstrap import generate_database  # type: ignore[unused-import]

    def test_t_db_02_bootstrap_all_excludes_generate_database(self) -> None:
        """T-DB-02: bootstrap.__all__ does not contain 'generate_database'."""
        self.assertNotIn("generate_database", bootstrap_module.__all__)

    def test_t_db_03_discover_user_config_still_works(self) -> None:
        """T-DB-03: bootstrap.discover_user_config() still callable."""
        with tempfile.TemporaryDirectory() as td:
            config_index = str(Path(td) / "user_config.json")
            config, returned_index = bootstrap_module.discover_user_config(
                config_index=config_index
            )
            self.assertIn("databases", config)
            self.assertEqual(returned_index, config_index)


class TestDatabaseOpsNewFunction(TestCase):
    """T-DB-04 ~ T-DB-08: database_ops.generate_database exists and works."""

    def test_t_db_04_import_database_ops_generate_database_succeeds(self) -> None:
        """T-DB-04: from modmgr.database_ops import generate_database → success."""
        from modmgr.database_ops import generate_database  # noqa

    def test_t_db_05_database_ops_all_contains_generate_database(self) -> None:
        """T-DB-05: database_ops.__all__ contains 'generate_database'."""
        self.assertIn("generate_database", database_ops_module.__all__)

    def test_t_db_06_generate_database_returns_dict_with_four_keys(self) -> None:
        """T-DB-06: generate_database() returns dict with OS/steamlib/game/mod."""
        from modmgr.database_ops import generate_database

        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            config_index = str(Path(td) / "user_config.json")
            config = {
                "schema_namespace": "KMM_UserConfig",
                "schema_version": "knighthana@0.1.0",
                "baksuffix": "kmmbackup",
                "bakignore": [],
                "rule_sources": [],
                "path_alias": [],
                "workspace_dir": "/tmp/ws",
                "databases": {"default": {"path": db_path}},
            }
            Path(config_index).parent.mkdir(parents=True, exist_ok=True)
            Path(config_index).write_text(json.dumps(config), encoding="utf-8")

            # Patch discover_with_fallback to return a known structure
            fake_db = {
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [],
                "game": [],
                "mod": [],
            }
            with patch.object(
                database_ops_module, "discover_with_fallback", return_value=fake_db
            ):
                result = generate_database(
                    "auto",
                    config_index=config_index,
                    working_pathstyle="linux",
                )

        self.assertIsInstance(result, dict)
        self.assertIn("OS", result)
        self.assertIn("steamlib", result)
        self.assertIn("game", result)
        self.assertIn("mod", result)

    def test_t_db_07_generate_database_writes_to_specified_location(self) -> None:
        """T-DB-07: generate_database() writes to user_config.databases[name].path."""
        from modmgr.database_ops import generate_database

        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            config_index = str(Path(td) / "user_config.json")
            config = {
                "schema_namespace": "KMM_UserConfig",
                "schema_version": "knighthana@0.1.0",
                "baksuffix": "kmmbackup",
                "bakignore": [],
                "rule_sources": [],
                "path_alias": [],
                "workspace_dir": "/tmp/ws",
                "databases": {"default": {"path": db_path}},
            }
            Path(config_index).parent.mkdir(parents=True, exist_ok=True)
            Path(config_index).write_text(json.dumps(config), encoding="utf-8")

            fake_db = {
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [],
                "game": [],
                "mod": [],
            }
            with patch.object(
                database_ops_module, "discover_with_fallback", return_value=fake_db
            ):
                result = generate_database(
                    "auto",
                    config_index=config_index,
                    working_pathstyle="linux",
                )

            # Verify file was written
            self.assertTrue(Path(db_path).exists())
            loaded = json.loads(Path(db_path).read_text(encoding="utf-8"))
            self.assertIn("steamlib", loaded)

    def test_t_db_08_generate_database_supports_on_progress_callback(self) -> None:
        """T-DB-08: generate_database() supports on_progress callback."""
        from modmgr.database_ops import generate_database

        progress_calls: list[tuple] = []

        def progress_callback(step: str, finished: int, total: int, message: str = "") -> None:
            progress_calls.append((step, finished, total, message))

        with tempfile.TemporaryDirectory() as td:
            db_path = str(Path(td) / "db.json")
            config_index = str(Path(td) / "user_config.json")
            config = {
                "schema_namespace": "KMM_UserConfig",
                "schema_version": "knighthana@0.1.0",
                "baksuffix": "kmmbackup",
                "bakignore": [],
                "rule_sources": [],
                "path_alias": [],
                "workspace_dir": "/tmp/ws",
                "databases": {"default": {"path": db_path}},
            }
            Path(config_index).parent.mkdir(parents=True, exist_ok=True)
            Path(config_index).write_text(json.dumps(config), encoding="utf-8")

            fake_db = {
                "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
                "steamlib": [],
                "game": [],
                "mod": [],
            }
            with patch.object(
                database_ops_module, "discover_with_fallback", return_value=fake_db
            ):
                generate_database(
                    "auto",
                    config_index=config_index,
                    working_pathstyle="linux",
                    on_progress=progress_callback,
                )

        # on_progress should have been called at least once
        self.assertGreater(len(progress_calls), 0)


class TestWebRouteAdaptation(TestCase):
    """T-DB-09 ~ T-DB-10: Web route call chain."""

    def test_t_db_09_web_route_does_not_use_bootstrap_generate_database(self) -> None:
        """T-DB-09: POST /api/database/generate doesn't go through bootstrap."""
        # Check the database route module does not import from bootstrap.generate_database
        import modmgr_web.routes.database as db_route

        # The module should not have bootstrap's generate_database as its source
        import modmgr.bootstrap
        self.assertFalse(
            hasattr(modmgr.bootstrap, "generate_database"),
            "bootstrap.generate_database should not exist",
        )

    def test_t_db_10_web_route_uses_database_ops_generate_database(self) -> None:
        """T-DB-10: POST /api/database/generate uses database_ops.generate_database."""
        import modmgr_web.routes.database as db_route
        import modmgr.database_ops

        # The module should reference database_ops.generate_database
        self.assertIs(
            db_route.generate_database,
            modmgr.database_ops.generate_database,
        )


class TestDocumentationConsistency(TestCase):
    """T-DB-11/12: Design docs reflect generate_database migration."""

    REPO_MEMO_DIR = Path(__file__).resolve().parent.parent / "repo_memo"

    def test_t_db_11_bootstrap_doc_no_generate_database(self) -> None:
        """T-DB-11: DESIGN_BOOTSTRAP.md does NOT mention generate_database."""
        path = self.REPO_MEMO_DIR / "DESIGN_BOOTSTRAP.md"
        content = path.read_text(encoding="utf-8")
        self.assertNotIn(
            "generate_database",
            content,
            "DESIGN_BOOTSTRAP.md should not mention generate_database",
        )

    def test_t_db_12_database_ops_doc_mentions_generate_database(self) -> None:
        """T-DB-12: DESIGN_DATABASE_OPS.md mentions generate_database as public API."""
        path = self.REPO_MEMO_DIR / "DESIGN_DATABASE_OPS.md"
        content = path.read_text(encoding="utf-8")
        self.assertIn(
            "generate_database",
            content,
            "DESIGN_DATABASE_OPS.md should mention generate_database as public API",
        )
