"""Wave-2 tests — 2026-09-08 adjudications:

- A3: restore consumes caller-provided backup_dirs (no database/ACF
  derivation); CLI restore works; derivation remains the fallback.
- A4: prep is per-dir — existing complete trees are never rebuilt
  (DESIGN_BACKUP_OPS §7.2 不重建树), including multi-dir plans.
- B1: restore hash computation tolerates I/O errors (per-entry
  failure instead of a full crash).
- D6: RUN intent also gets per-dir prep.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from modmgr.orchestrator.entry import Intent, TaskRequest
from modmgr.orchestrator.fileops import execute as fileops_execute

APPID = "270150"
MOD_A = "2606099273"
MOD_B = "1111111111"


def _build_fixture(root: Path, mods: list[str]) -> None:
    steamapps = root / "steamapps"
    for cid in mods:
        mod = steamapps / "workshop" / "content" / APPID / cid
        mod.mkdir(parents=True, exist_ok=True)
        (mod / "file.txt").write_text(f"content-{cid}")
    ws = steamapps / "workshop"
    ws.mkdir(exist_ok=True)
    installed = "\n".join(
        f'\t\t"{cid}"\n\t\t{{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}}'
        for cid in mods
    )
    details = "\n".join(
        f'\t\t"{cid}"\n\t\t{{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}}'
        for cid in mods
    )
    (ws / f"appworkshop_{APPID}.acf").write_text(
        '"AppWorkshop"\n{\n\t"WorkshopItemsInstalled"\n\t{\n'
        + installed
        + '\n\t}\n\t"WorkshopItemDetails"\n\t{\n'
        + details
        + "\n\t}\n}"
    )


def _database(root: Path, mods: list[str]) -> dict:
    return {
        "game": [{
            "appid": APPID,
            "basepath": str(root / "steamapps" / "common" / "RWR") + "/",
            "modpath": str(root / "steamapps" / "workshop" / "content" / APPID) + "/",
            "mods_found": mods,
        }],
        "mod": [
            {"mixed_id": f"{APPID}:{cid}",
             "path": str(root / "steamapps" / "workshop" / "content" / APPID / cid) + "/"}
            for cid in mods
        ],
    }


def _delete_mapping(root: Path, mods: list[str]) -> list[dict]:
    return [
        {"path": str(root / "steamapps" / "workshop" / "content" / APPID / cid / "file.txt"),
         "request": {"path": "!", "action": "delete", "mixed_id": f"{APPID}:{cid}"}}
        for cid in mods
    ]


def _user_config() -> dict:
    return {"baksuffix": "kmmbackup"}  # no bakignore key


def _backup_request() -> TaskRequest:
    return TaskRequest(identity="cli", intent=Intent.BACKUP,
                       resolver_type="raw_dict", resolver_args={})


def _restore_request(flags: dict | None = None) -> TaskRequest:
    return TaskRequest(identity="cli", intent=Intent.RESTORE,
                       resolver_type="raw_dict", resolver_args={},
                       flags=flags or {})


class TestRestoreExplicitBackupDirs:
    """A3: restore consumes caller-provided backup_dirs; derivation is fallback."""

    def test_restore_with_explicit_backup_dirs_needs_no_database(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_fixture(root, [MOD_A])
            data_backup = {
                "final_mapping": _delete_mapping(root, [MOD_A]),
                "database": _database(root, [MOD_A]),
                "user_config": _user_config(),
            }
            r1 = fileops_execute(_backup_request(), data_backup, Intent.BACKUP, {})
            assert r1.ok, r1.errors
            backup_dir = next(root.rglob(f"{MOD_A}.*.kmmbackup"))

            # Apply a deletion so restore has something to bring back
            data_apply = dict(data_backup)
            data_apply["final_mapping"] = [{
                "path": str(root / "steamapps" / "workshop" / "content" / APPID / MOD_A / "file.txt"),
                "request": {"path": "!", "action": "delete"},
            }]
            r2 = fileops_execute(_restore_request(), dict(data_apply), Intent.APPLY, {})
            assert r2.ok, r2.errors
            assert not (root / "steamapps" / "workshop" / "content" / APPID / MOD_A / "file.txt").exists()

            # Restore with EXPLICIT backup_dirs and an EMPTY database —
            # the CLI restore contract.  Must not crash (A3).
            explicit = {str(backup_dir): []}
            data_restore = {
                "final_mapping": [{
                    "path": str(root / "steamapps" / "workshop" / "content" / APPID / MOD_A / "file.txt"),
                    "request": {"path": str(backup_dir / "file.txt"), "action": "replace",
                                "mixed_id": "0:0"},
                }],
                "database": {"game": [], "mod": [], "steamlib": []},
                "user_config": _user_config(),
                "backup_dirs": explicit,
            }
            r3 = fileops_execute(
                _restore_request({"force": True}), data_restore, Intent.RESTORE, {}
            )
            assert r3.ok, r3.errors
            assert (root / "steamapps" / "workshop" / "content" / APPID / MOD_A / "file.txt").exists()

    def test_restore_fallback_derivation_still_works(self) -> None:
        """Without explicit backup_dirs, derivation (current-version query)
        remains the fallback."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_fixture(root, [MOD_A])
            data_backup = {
                "final_mapping": _delete_mapping(root, [MOD_A]),
                "database": _database(root, [MOD_A]),
                "user_config": _user_config(),
            }
            r1 = fileops_execute(_backup_request(), data_backup, Intent.BACKUP, {})
            assert r1.ok, r1.errors

            # Same data again for restore — derivation finds the same dir
            r2 = fileops_execute(
                _restore_request({"force": True}), data_backup, Intent.RESTORE, {}
            )
            assert r2.ok, r2.errors

    def test_cross_version_restore_is_rejected(self) -> None:
        """Negative test (version binding): after the game/workshop ACF
        advances, derivation points at a NEW container name — the old
        backup becomes unreachable and restore fails cleanly with
        E_BACKUP_DIR_MISSING instead of touching the wrong files."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_fixture(root, [MOD_A])
            data_backup = {
                "final_mapping": _delete_mapping(root, [MOD_A]),
                "database": _database(root, [MOD_A]),
                "user_config": _user_config(),
            }
            r1 = fileops_execute(_backup_request(), data_backup, Intent.BACKUP, {})
            assert r1.ok

            # Simulate a workshop update: timeupdated advances
            acf = root / "steamapps" / "workshop" / f"appworkshop_{APPID}.acf"
            text = acf.read_text().replace("1716297600", "1816297600")
            acf.write_text(text)

            r2 = fileops_execute(
                _restore_request({"force": True}), data_backup, Intent.RESTORE, {}
            )
            assert not r2.ok
            assert any("E_BACKUP_DIR_MISSING" in e for e in r2.errors), r2.errors


class TestPerDirPrep:
    """A4: prep only runs for dirs lacking a complete tree."""

    def test_existing_tree_is_not_rebuilt_in_multi_dir_backup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_fixture(root, [MOD_A, MOD_B])
            data = {
                "final_mapping": _delete_mapping(root, [MOD_A]),
                "database": _database(root, [MOD_A, MOD_B]),
                "user_config": _user_config(),
            }
            r1 = fileops_execute(_backup_request(), data, Intent.BACKUP, {})
            assert r1.ok, r1.errors
            mod_a_file = (
                root / "steamapps" / "workshop" / "content" / APPID / MOD_A / "file.txt"
            )
            backup_file = next(
                p for p in root.rglob("file.txt") if ".kmmbackup" in str(p) and MOD_A in str(p)
            )
            mtime_1 = backup_file.stat().st_mtime_ns

            # Second round: add MOD_B.  MOD_A's tree exists — its file must
            # be skipped (already backed up), not re-copied.
            import time as _t
            _t.sleep(0.01)
            data2 = {
                "final_mapping": _delete_mapping(root, [MOD_A, MOD_B]),
                "database": _database(root, [MOD_A, MOD_B]),
                "user_config": _user_config(),
            }
            r2 = fileops_execute(_backup_request(), data2, Intent.BACKUP, {})
            assert r2.ok, r2.errors

            skipped_paths = [s["path"] for s in r2.backup_result["skipped"]]
            assert any(str(mod_a_file) == p for p in skipped_paths), (
                f"MOD_A file should be skipped (tree intact), got skipped={skipped_paths}"
            )
            assert backup_file.stat().st_mtime_ns == mtime_1, (
                "MOD_A backup copy must not be rewritten (§7.2 不重建树)"
            )
            # MOD_B got backed up for the first time
            assert any(MOD_B in b["path"] for b in r2.backup_result["backed_up"])

    def test_run_intent_also_preps_missing_tree(self) -> None:
        """D6: RUN = backup + apply; its backup phase must also prep."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_fixture(root, [MOD_A])
            data = {
                "final_mapping": _delete_mapping(root, [MOD_A]),
                "database": _database(root, [MOD_A]),
                "user_config": _user_config(),
            }
            request = TaskRequest(identity="cli", intent=Intent.RUN,
                                  resolver_type="raw_dict", resolver_args={})
            result = fileops_execute(request, data, Intent.RUN, {})
            assert result.ok, result.errors
            backup_dir = next(root.rglob(f"{MOD_A}.*.kmmbackup"))
            info = json.loads((backup_dir / "backupinfo.json").read_text())
            assert info.get("tree", {}).get("children"), (
                "RUN's backup phase must create backupinfo with a tree"
            )


class TestDryRunFidelity:
    """B4: dry run mirrors the real-run decision chain."""

    def test_backup_dry_run_respects_tree_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_fixture(root, [MOD_A])
            data = {
                "final_mapping": _delete_mapping(root, [MOD_A]),
                "database": _database(root, [MOD_A]),
                "user_config": _user_config(),
            }
            # Real backup first: file becomes isbackuped=true
            r1 = fileops_execute(_backup_request(), data, Intent.BACKUP, {})
            assert r1.ok

            # Dry run must NOT report the file as "would backup" again
            dry_request = TaskRequest(identity="cli", intent=Intent.BACKUP,
                                      resolver_type="raw_dict", resolver_args={},
                                      flags={"dry_run": True})
            r2 = fileops_execute(dry_request, data, Intent.BACKUP, {"dry_run": True})
            br = r2.backup_result or {}
            assert br.get("dry_run") is True
            would = [b["path"] for b in br.get("backed_up", [])]
            assert not any("file.txt" in p for p in would), (
                f"dry run must skip already-backed-up files, got {would}"
            )
            assert any("already backed up" in s.get("reason", "") for s in br.get("skipped", []))



    """B1: hash computation failures degrade to per-entry errors."""

class TestRestoreHashIoTolerance:
    """B1: hash computation failures degrade to per-entry errors."""

    def test_sha256_hex_returns_empty_on_io_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from modmgr import restore_ops

        target = tmp_path / "f.bin"
        target.write_text("x")

        def _boom(*a, **k):
            raise OSError("disk error")

        # Simulate an I/O failure inside the read loop
        monkeypatch.setattr(restore_ops.os, "path", restore_ops.os.path)
        real_isfile = restore_ops.os.path.isfile

        def fake_open(*a, **k):
            raise OSError("disk error")

        monkeypatch.setattr("builtins.open", fake_open)
        try:
            # isfile uses stat, unaffected by builtins.open patch
            assert real_isfile(target)
            value = restore_ops._sha256_hex(str(target))
        finally:
            monkeypatch.undo()
        assert value == ""

    def test_restore_survives_unreadable_target(self, tmp_path: Path) -> None:
        """An unreadable (dir-in-place) target yields a per-entry error;
        other entries still restore."""
        from modmgr.restore_ops import restore_entries

        backup_dir = tmp_path / "src" / "bd"
        backup_dir.mkdir(parents=True)
        (backup_dir / "good.txt").write_text("good")
        (backup_dir / "bad.txt").write_text("bad")

        content_root = backup_dir.parent
        good_target = content_root / "good.txt"
        good_target.write_text("changed")
        # 'bad' target is a directory — hash step is skipped (isfile False),
        # the copy step fails with OSError → per-entry error, no crash.
        bad_target = content_root / "bad.txt"
        bad_target.mkdir()

        tree = {
            "name": "bd", "type": "dir",
            "children": [
                {"name": "good.txt", "type": "file", "isbackuped": True,
                 "hashtype": "sha256", "hashvalue": "deadbeef"},
                {"name": "bad.txt", "type": "file", "isbackuped": True,
                 "hashtype": "sha256", "hashvalue": "deadbeef"},
            ],
        }
        entries = {str(backup_dir) + "/": [
            {"path": str(good_target), "request": {"action": "replace"}},
            {"path": str(bad_target), "request": {"action": "replace"}},
        ]}
        result = restore_entries(
            entries, {str(backup_dir) + "/": {"tree": tree}}, force=True
        )
        # good.txt restored, bad.txt errored per-entry, no exception raised
        assert any("good.txt" in str(r.get("path", "")) for r in result["restored"])
        assert any("bad.txt" in e for e in result["errors"])
