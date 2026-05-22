"""Tests for backup_dir_builder module."""

from __future__ import annotations

import time
from pathlib import Path
from unittest import TestCase

from modmgr.backup_dir_builder import (
    build_backup_dir,
    build_backup_dirs,
    get_custom_backup_id,
    load_dir_suffixes,
)
from modmgr.backup_ops import get_game_backup_id, get_workshop_timestamphex


# ── P1-02: get_workshop_timestamphex ─────────────────────────────────────────

class TestGetWorkshopTimestamphex(TestCase):
    def test_get_workshop_timestamphex_success(self):
        """Format A: WorkshopItemsInstalled -> appid -> timeupdated, with AppWorkshop wrapper."""
        with tempfile() as tmp:
            ws = Path(tmp) / "workshop"
            ws.mkdir()
            acf = ws / "appworkshop_270150.acf"
            acf.write_text(
                '"AppWorkshop"\n'
                '{\n'
                '    "WorkshopItemsInstalled"\n'
                '    {\n'
                '        "2606099273"\n'
                '        {\n'
                '            "timeupdated" "1700000000"\n'
                '        }\n'
                '    }\n'
                '    "WorkshopItemDetails"\n'
                '    {\n'
                '        "2606099273"\n'
                '        {\n'
                '            "latest_timeupdated" "1700000000"\n'
                '        }\n'
                '    }\n'
                '}\n'
            )
            ok, hex_id, warning = get_workshop_timestamphex(tmp, "270150", "2606099273")
            self.assertTrue(ok)
            self.assertEqual(hex_id, format(1700000000, "x"))
            self.assertEqual(warning, "")

    def test_get_workshop_timestamphex_missing(self):
        """ACF file does not exist → returns failure."""
        with tempfile() as tmp:
            ok, hex_id, warning = get_workshop_timestamphex(tmp, "999999", "12345")
            self.assertFalse(ok)
            self.assertIsNone(hex_id)
            self.assertIn("SKIPPED", warning)

    def test_get_workshop_timestamphex_version_lagged(self):
        """T_local < T_remote → unstable, skip."""
        with tempfile() as tmp:
            ws = Path(tmp) / "workshop"
            ws.mkdir()
            acf = ws / "appworkshop_270150.acf"
            acf.write_text(
                '"AppWorkshop"\n'
                '{\n'
                '    "WorkshopItemsInstalled"\n'
                '    {\n'
                '        "2606099273"\n'
                '        {\n'
                '            "timeupdated" "1000000"\n'
                '        }\n'
                '    }\n'
                '    "WorkshopItemDetails"\n'
                '    {\n'
                '        "2606099273"\n'
                '        {\n'
                '            "latest_timeupdated" "2000000"\n'
                '        }\n'
                '    }\n'
                '}\n'
            )
            ok, hex_id, warning = get_workshop_timestamphex(tmp, "270150", "2606099273")
            self.assertFalse(ok)
            self.assertIsNone(hex_id)
            self.assertIn("VERSION_LAGGED", warning)


# ── P1-04: get_custom_backup_id ─────────────────────────────────────────────

class TestGetCustomBackupId(TestCase):
    def test_get_custom_backup_id_from_mtime(self):
        """Multiple source files → return hex of latest mtime."""
        with tempfile() as tmp:
            f1 = Path(tmp) / "a.txt"
            f1.write_bytes(b"old")
            time.sleep(0.05)
            f2 = Path(tmp) / "b.txt"
            f2.write_bytes(b"new")
            max_mtime = int(f2.stat().st_mtime)

            result = get_custom_backup_id([str(f1), str(f2)])
            self.assertEqual(result, format(max_mtime, "x"))

    def test_get_custom_backup_id_only_first_exists(self):
        """Only first path exists, second is missing."""
        with tempfile() as tmp:
            f1 = Path(tmp) / "a.txt"
            f1.write_bytes(b"data")
            mtime = int(f1.stat().st_mtime)
            result = get_custom_backup_id([str(f1), "/nonexistent/path"])
            self.assertEqual(result, format(mtime, "x"))

    def test_get_custom_backup_id_all_missing(self):
        """All paths missing → return hex of current time."""
        result = get_custom_backup_id(["/nonexistent/path1", "/nonexistent/path2"])
        # Can't predict exact time, but should be hex of a recent timestamp
        self.assertTrue(result.isalnum())
        self.assertGreater(len(result), 0)

    def test_get_custom_backup_id_empty_list(self):
        """Empty list → return hex of current time."""
        result = get_custom_backup_id([])
        self.assertTrue(result.isalnum())
        self.assertGreater(len(result), 0)


# ── P1-05: build_backup_dir ─────────────────────────────────────────────────

def _make_game(appid: str, basepath: str, modpath: str) -> dict:
    return {
        "appid": appid,
        "installdir": f"Game{appid}",
        "basepath": basepath,
        "modpath": modpath,
    }


class TestBuildBackupDir(TestCase):
    def test_build_backup_dir_common(self):
        """final_mapping targets under basepath → common backup dir."""
        with tempfile() as tmp:
            steamapps = Path(tmp) / "steamapps"
            common = steamapps / "common" / "Game270150"
            common.mkdir(parents=True)
            target_file = common / "data" / "file.txt"
            target_file.parent.mkdir()
            target_file.write_bytes(b"test")

            # Create appmanifest for backup_id
            (steamapps / "appmanifest_270150.acf").write_text(
                '"AppState"\n{\n"appid" "270150"\n"StateFlags" "4"\n"buildid" "22924257"\n}\n'
            )

            database = {
                "game": [_make_game("270150", str(common), str(steamapps / "workshop" / "content" / "270150"))]
            }
            final_mapping = [{"path": str(target_file), "request": {"action": "replace"}}]
            user_config = {}

            result = build_backup_dir(final_mapping, database, user_config)
            expected = f"{common}/270150.{format(22924257, 'x')}.kmmbackup/"
            self.assertEqual(result, expected)

    def test_build_backup_dir_workshop(self):
        """final_mapping targets under modpath → workshop backup dir."""
        with tempfile() as tmp:
            steamapps = Path(tmp) / "steamapps"
            modpath = steamapps / "workshop" / "content" / "270150"
            modpath.mkdir(parents=True)
            target_file = modpath / "12345" / "file.txt"
            target_file.parent.mkdir()
            target_file.write_bytes(b"test")

            common = steamapps / "common" / "Game270150"
            common.mkdir(parents=True)

            # Create appworkshop for backup_id
            (steamapps / "workshop").mkdir(exist_ok=True)
            (steamapps / "workshop" / "appworkshop_270150.acf").write_text(
                '"AppWorkshop"\n'
                '{\n'
                '    "WorkshopItemsInstalled"\n'
                '    {\n'
                '        "12345"\n'
                '        {\n'
                '            "timeupdated" "1800000000"\n'
                '        }\n'
                '    }\n'
                '    "WorkshopItemDetails"\n'
                '    {\n'
                '        "12345"\n'
                '        {\n'
                '            "latest_timeupdated" "1800000000"\n'
                '        }\n'
                '    }\n'
                '}\n'
            )

            database = {
                "game": [_make_game("270150", str(common), str(modpath))]
            }
            final_mapping = [{"path": str(target_file), "request": {"action": "replace"}}]
            user_config = {}

            result = build_backup_dir(final_mapping, database, user_config)
            expected = f"{modpath}/12345/12345.{format(1800000000, 'x')}.kmmbackup/"
            self.assertEqual(result, expected)

    def test_build_backup_dir_no_appid(self):
        """final_mapping paths cannot match any game → ValueError."""
        with tempfile() as tmp:
            database = {
                "game": [_make_game("270150", "/some/basepath", "/some/modpath")]
            }
            final_mapping = [{"path": "/unrelated/path/file.txt", "request": {"action": "replace"}}]
            user_config = {}

            with self.assertRaises(ValueError) as ctx:
                build_backup_dir(final_mapping, database, user_config)
            self.assertIn("E_BACKUP_DIR_BUILD_NO_APPID", str(ctx.exception))

    def test_build_backup_dir_empty_mapping(self):
        """Empty final_mapping → ValueError."""
        database = {"game": [_make_game("270150", "/base", "/mod")]}
        with self.assertRaises(ValueError) as ctx:
            build_backup_dir([], database, {})
        self.assertIn("E_BACKUP_DIR_BUILD_NO_APPID", str(ctx.exception))

    def test_build_backup_dir_custom_baksuffix(self):
        """user_config provides custom baksuffix."""
        with tempfile() as tmp:
            steamapps = Path(tmp) / "steamapps"
            common = steamapps / "common" / "Game270150"
            common.mkdir(parents=True)
            target_file = common / "data.txt"
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_bytes(b"x")

            (steamapps / "appmanifest_270150.acf").write_text(
                '"AppState"\n{\n"appid" "270150"\n"StateFlags" "4"\n"buildid" "22924257"\n}\n'
            )

            database = {
                "game": [_make_game("270150", str(common), str(steamapps / "workshop" / "content" / "270150"))]
            }
            final_mapping = [{"path": str(target_file)}]
            user_config = {"baksuffix": "mybackup"}

            result = build_backup_dir(final_mapping, database, user_config)
            expected = f"{common}/270150.{format(22924257, 'x')}.mybackup/"
            self.assertEqual(result, expected)

    def test_build_backup_dir_mixed_targets(self):
        """Targets span multiple appids → pick most frequent."""
        with tempfile() as tmp:
            steamapps = Path(tmp) / "steamapps"
            common1 = steamapps / "common" / "Game270150"
            common1.mkdir(parents=True)
            common2 = steamapps / "common" / "Game892970"
            common2.mkdir(parents=True)

            # 2 targets for appid 270150, 1 for 892970
            targets_270150 = [
                common1 / "f1.txt",
                common1 / "sub" / "f2.txt",
            ]
            targets_892970 = [common2 / "f3.txt"]
            for t in targets_270150:
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_bytes(b"x")
            for t in targets_892970:
                t.parent.mkdir(parents=True, exist_ok=True)
                t.write_bytes(b"x")

            (steamapps / "appmanifest_270150.acf").write_text(
                '"AppState"\n{\n"appid" "270150"\n"StateFlags" "4"\n"buildid" "22924257"\n}\n'
            )
            (steamapps / "appmanifest_892970.acf").write_text(
                '"AppState"\n{\n"appid" "892970"\n"StateFlags" "4"\n"buildid" "19233942"\n}\n'
            )

            database = {
                "game": [
                    _make_game("270150", str(common1), str(steamapps / "workshop" / "content" / "270150")),
                    _make_game("892970", str(common2), str(steamapps / "workshop" / "content" / "892970")),
                ]
            }
            final_mapping = [{"path": str(t)} for t in targets_270150 + targets_892970]
            user_config = {}

            result = build_backup_dir(final_mapping, database, user_config)
            # Should pick 270150 (2 matches vs 1)
            expected = f"{common1}/270150.{format(22924257, 'x')}.kmmbackup/"
            self.assertEqual(result, expected)


# ── P1-06: load_dir_suffixes ────────────────────────────────────────────────

class TestLoadDirSuffixes(TestCase):
    def test_load_dir_suffixes_default(self):
        result = load_dir_suffixes({})
        self.assertEqual(result, [".kmmbackup"])

    def test_load_dir_suffixes_with_custom(self):
        user_config = {"ignore": ["test", ".other", "test"]}
        result = load_dir_suffixes(user_config)
        self.assertIn(".kmmbackup", result)
        self.assertIn(".test", result)
        self.assertIn(".other", result)
        self.assertEqual(len(result), 3)  # dedup

    def test_load_dir_suffixes_auto_dot(self):
        user_config = {"ignore": ["nodot"]}
        result = load_dir_suffixes(user_config)
        self.assertIn(".nodot", result)


# ── P1-09: loop protection in backup_dir_builder (indirect) ──────────────────

def tempfile():
    """Helper: return context-managed temporary directory as string path."""
    import tempfile as _tf
    from contextlib import contextmanager

    @contextmanager
    def _tmpdir():
        d = _tf.mkdtemp()
        try:
            yield d
        finally:
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    return _tmpdir()
