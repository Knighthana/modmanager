"""Tests for backup_ops module (Phase 7-12 implementation)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest import TestCase

from modmanager.backup_ops import (
    apply_final_mapping,
    build_filefoldertree_with_hashes,
    check_backup_gate,
    delete_orphan_files,
    detect_dirty_state,
    finalize_backup_dir,
    get_game_backup_id,
    init_backup_dir,
    inspect_conflict,
    load_backup_info,
    restore_from_backup,
    run_differential_backup,
)


# ── Phase 7: get_game_backup_id ───────────────────────────────────────────────

class TestGetGameBackupId(TestCase):
    def test_returns_hex_for_valid_acf(self):
        with tempfile.TemporaryDirectory() as tmp:
            acf = Path(tmp) / "appmanifest_270150.acf"
            acf.write_text('"AppState"\n{\n"appid" "270150"\n"LastUpdated" "1700000000"\n}\n')
            result = get_game_backup_id(tmp, "270150")
            self.assertEqual(result, format(1700000000, "x"))

    def test_returns_zero_for_missing_acf(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(get_game_backup_id(tmp, "270150"), "0")

    def test_returns_zero_for_missing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            acf = Path(tmp) / "appmanifest_270150.acf"
            acf.write_text('"AppState"\n{\n"appid" "270150"\n}\n')
            self.assertEqual(get_game_backup_id(tmp, "270150"), "0")

    def test_returns_zero_for_non_numeric_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            acf = Path(tmp) / "appmanifest_270150.acf"
            acf.write_text('"AppState"\n{\n"LastUpdated" "not_a_number"\n}\n')
            self.assertEqual(get_game_backup_id(tmp, "270150"), "0")


# ── Phase 8: build_filefoldertree_with_hashes ─────────────────────────────────

class TestBuildFilefoldertree(TestCase):
    def test_single_file_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "hello.txt"
            f.write_bytes(b"hello")
            tree = build_filefoldertree_with_hashes(tmp)
            self.assertEqual(tree["type"], "folder")
            self.assertEqual(len(tree["children"]), 1)
            child = tree["children"][0]
            self.assertEqual(child["name"], "hello.txt")
            self.assertEqual(child["type"], "file")
            self.assertTrue(child["isbackuped"])
            self.assertEqual(child["hashtype"], "sha256")
            self.assertEqual(len(child["hashvalue"]), 64)

    def test_nested_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = Path(tmp) / "sub"
            sub.mkdir()
            (sub / "file.txt").write_bytes(b"data")
            tree = build_filefoldertree_with_hashes(tmp)
            self.assertEqual(tree["children"][0]["name"], "sub")
            self.assertEqual(tree["children"][0]["children"][0]["name"], "file.txt")

    def test_skips_backupinfo_json_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "backupinfo.json").write_bytes(b"{}")
            (Path(tmp) / "real.txt").write_bytes(b"x")
            tree = build_filefoldertree_with_hashes(tmp)
            names = [c["name"] for c in tree["children"]]
            self.assertNotIn("backupinfo.json", names)
            self.assertIn("real.txt", names)

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tree = build_filefoldertree_with_hashes(tmp)
            self.assertEqual(tree["type"], "folder")
            self.assertEqual(tree["children"], [])

    def test_hash_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "f.bin"
            f.write_bytes(b"\x00" * 1024)
            t1 = build_filefoldertree_with_hashes(tmp)
            t2 = build_filefoldertree_with_hashes(tmp)
            self.assertEqual(
                t1["children"][0]["hashvalue"],
                t2["children"][0]["hashvalue"],
            )


# ── Phase 8: backup dir lifecycle ─────────────────────────────────────────────

class TestBackupDirLifecycle(TestCase):
    def test_init_creates_error_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            init_backup_dir(bdir)
            info = load_backup_info(bdir)
            self.assertEqual(info["filefoldertree_status"], "error")

    def test_finalize_creates_ready_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            init_backup_dir(bdir)
            (Path(bdir) / "data.txt").write_bytes(b"test")
            info = finalize_backup_dir(bdir)
            self.assertEqual(info["filefoldertree_status"], "ready")
            self.assertIn("filefoldertree", info)

    def test_finalize_tree_contains_backed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            init_backup_dir(bdir)
            (Path(bdir) / "file.txt").write_bytes(b"content")
            info = finalize_backup_dir(bdir)
            names = [c["name"] for c in info["filefoldertree"]["children"]]
            self.assertIn("file.txt", names)

    def test_load_returns_empty_for_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_backup_info(str(Path(tmp) / "nonexistent")), {})

    def test_load_returns_empty_for_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "backupinfo.json").write_bytes(b"not json")
            self.assertEqual(load_backup_info(tmp), {})


# ── Phase 9: check_backup_gate ────────────────────────────────────────────────

class TestCheckBackupGate(TestCase):
    def _ready_backup(self, tmp: str) -> str:
        bdir = str(Path(tmp) / "backup")
        init_backup_dir(bdir)
        finalize_backup_dir(bdir)
        return bdir

    def test_passes_for_ready_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = self._ready_backup(tmp)
            self.assertEqual(check_backup_gate(bdir), [])

    def test_fails_for_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors = check_backup_gate(str(Path(tmp) / "nonexistent"))
            self.assertTrue(any("E_BACKUP_DIR_MISSING" in e for e in errors))

    def test_fails_for_error_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            init_backup_dir(bdir)  # status=error
            errors = check_backup_gate(bdir)
            self.assertTrue(any("E_BACKUP_TREE_INCOMPLETE" in e for e in errors))

    def test_fails_for_missing_backupinfo(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            Path(bdir).mkdir()
            errors = check_backup_gate(bdir)
            self.assertTrue(any("E_BACKUP_INFO_MISSING" in e for e in errors))

    def test_fails_for_ready_status_but_missing_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            # Write info with ready status but no filefoldertree
            Path(bdir).mkdir()
            (Path(bdir) / "backupinfo.json").write_text(
                json.dumps({"filefoldertree_status": "ready"})
            )
            errors = check_backup_gate(bdir)
            self.assertTrue(any("E_BACKUP_TREE_MISSING" in e for e in errors))


# ── Phase 10: run_differential_backup ────────────────────────────────────────

class TestRunDifferentialBackup(TestCase):
    def test_backs_up_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src" / "a.txt"
            src.parent.mkdir()
            src.write_bytes(b"content_a")

            bdir = str(Path(tmp) / "backup")
            result = run_differential_backup(bdir, [str(src)])

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["backed_up"]), 1)
            self.assertEqual(result["errors"], [])
            self.assertEqual(load_backup_info(bdir)["filefoldertree_status"], "ready")

    def test_skips_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            result = run_differential_backup(bdir, ["/nonexistent/path/file.txt"])

            self.assertTrue(result["ok"])
            self.assertEqual(result["backed_up"], [])
            self.assertEqual(len(result["skipped"]), 1)

    def test_empty_file_list_finalizes_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            result = run_differential_backup(bdir, [])

            self.assertTrue(result["ok"])
            self.assertEqual(load_backup_info(bdir)["filefoldertree_status"], "ready")

    def test_backed_up_file_is_in_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "orig" / "important.dat"
            src.parent.mkdir()
            src.write_bytes(b"\xde\xad\xbe\xef")

            bdir = str(Path(tmp) / "backup")
            run_differential_backup(bdir, [str(src)])
            info = load_backup_info(bdir)

            # Check that the tree has some file nodes (backup content)
            self.assertIn("filefoldertree", info)

    def test_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src"
            src_dir.mkdir()
            files = [src_dir / f"f{i}.txt" for i in range(3)]
            for f in files:
                f.write_bytes(b"data")

            bdir = str(Path(tmp) / "backup")
            result = run_differential_backup(bdir, [str(f) for f in files])

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["backed_up"]), 3)

    def test_backs_up_existing_directory_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "orig" / "dir1"
            src_dir.mkdir(parents=True)
            (src_dir / "a.txt").write_bytes(b"a")
            (src_dir / "nested").mkdir()
            (src_dir / "nested" / "b.txt").write_bytes(b"b")

            bdir = str(Path(tmp) / "backup")
            result = run_differential_backup(bdir, [str(src_dir)])

            self.assertTrue(result["ok"])
            self.assertTrue((Path(bdir) / Path(str(src_dir)).as_posix().lstrip("/") / "a.txt").exists())
            self.assertTrue((Path(bdir) / Path(str(src_dir)).as_posix().lstrip("/") / "nested" / "b.txt").exists())


# ── Phase 11: apply_final_mapping ────────────────────────────────────────────

class TestApplyFinalMapping(TestCase):
    def _ready_backup(self, tmp: str) -> str:
        bdir = str(Path(tmp) / "backup")
        init_backup_dir(bdir)
        finalize_backup_dir(bdir)
        return bdir

    def _entry(self, target: str, source: str, action: str = "replace") -> dict:
        return {
            "path": target,
            "request": {
                "path": source,
                "action": action,
                "mixed_id": "x:y",
                "hashtype": "sha256",
                "hashvalue": "",
            },
        }

    def test_replace_overwrites_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.txt"
            src.write_bytes(b"new content")
            dest = Path(tmp) / "dest.txt"
            dest.write_bytes(b"old content")

            bdir = self._ready_backup(tmp)
            result = apply_final_mapping([self._entry(str(dest), str(src))], bdir)

            self.assertTrue(result["ok"])
            self.assertEqual(dest.read_bytes(), b"new content")

    def test_create_makes_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.txt"
            src.write_bytes(b"created")
            dest = Path(tmp) / "new_dir" / "new.txt"

            bdir = self._ready_backup(tmp)
            result = apply_final_mapping([self._entry(str(dest), str(src), "create")], bdir)

            self.assertTrue(result["ok"])
            self.assertEqual(dest.read_bytes(), b"created")

    def test_delete_removes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "to_delete.txt"
            target.write_bytes(b"data")

            bdir = self._ready_backup(tmp)
            entry = {"path": str(target), "request": {"path": "!", "action": "delete", "mixed_id": "x:y", "hashtype": "sha256", "hashvalue": "0"}}
            result = apply_final_mapping([entry], bdir)

            self.assertTrue(result["ok"])
            self.assertFalse(target.exists())

    def test_delete_nonexistent_target_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = self._ready_backup(tmp)
            entry = {"path": str(Path(tmp) / "ghost.txt"), "request": {"path": "!", "action": "delete", "mixed_id": "x:y", "hashtype": "sha256", "hashvalue": "0"}}
            result = apply_final_mapping([entry], bdir)

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["skipped"]), 1)

    def test_gate_blocks_when_backup_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.txt"
            src.write_bytes(b"x")
            dest = Path(tmp) / "dest.txt"

            bdir = str(Path(tmp) / "nonexistent_backup")
            result = apply_final_mapping([self._entry(str(dest), str(src))], bdir)

            self.assertFalse(result["ok"])
            self.assertTrue(any("E_BACKUP_DIR_MISSING" in e for e in result["errors"]))

    def test_dry_run_does_not_modify_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src.txt"
            src.write_bytes(b"new")
            dest = Path(tmp) / "dest.txt"
            dest.write_bytes(b"old")

            bdir = self._ready_backup(tmp)
            result = apply_final_mapping([self._entry(str(dest), str(src))], bdir, dry_run=True)

            self.assertTrue(result["ok"])
            self.assertEqual(dest.read_bytes(), b"old")

    def test_source_not_found_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "dest.txt"
            bdir = self._ready_backup(tmp)

            result = apply_final_mapping(
                [self._entry(str(dest), "/nonexistent/src.txt")], bdir
            )
            self.assertFalse(result["ok"])
            self.assertTrue(any("E_SOURCE_NOT_FOUND" in e for e in result["errors"]))

    def test_delete_plus_replace_clears_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / "game" / "textures"
            target_dir.mkdir(parents=True)
            (target_dir / "old_file.png").write_bytes(b"old")

            src = Path(tmp) / "src" / "new_file.png"
            src.parent.mkdir()
            src.write_bytes(b"new")

            dest = target_dir / "new_file.png"
            bdir = self._ready_backup(tmp)

            # delete the old file
            del_entry = {
                "path": str(target_dir / "old_file.png"),
                "request": {
                    "path": "!",
                    "action": "delete",
                    "mixed_id": "x:y",
                    "hashtype": "sha256",
                    "hashvalue": "0",
                },
            }
            # replace (copy) the new file
            rep_entry = {
                "path": str(dest),
                "request": {
                    "path": str(src),
                    "action": "replace",
                    "mixed_id": "x:y",
                    "hashtype": "sha256",
                    "hashvalue": "",
                },
            }
            result = apply_final_mapping([del_entry, rep_entry], bdir)

            self.assertTrue(result["ok"])
            self.assertFalse((target_dir / "old_file.png").exists())
            self.assertEqual(dest.read_bytes(), b"new")

    def test_replace_copies_directory_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            src_dir = Path(tmp) / "src" / "dir1"
            src_dir.mkdir(parents=True)
            (src_dir / "a.txt").write_bytes(b"a")
            (src_dir / "nested").mkdir()
            (src_dir / "nested" / "b.txt").write_bytes(b"b")

            dest = Path(tmp) / "game" / "maps" / "dir1"
            bdir = self._ready_backup(tmp)
            result = apply_final_mapping([self._entry(str(dest), str(src_dir))], bdir)

            self.assertTrue(result["ok"])
            self.assertEqual((dest / "a.txt").read_bytes(), b"a")
            self.assertEqual((dest / "nested" / "b.txt").read_bytes(), b"b")


# ── Phase 12: restore_from_backup ─────────────────────────────────────────────

class TestRestoreFromBackup(TestCase):
    def test_restores_modified_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "orig" / "test.txt"
            orig.parent.mkdir()
            orig.write_bytes(b"original")

            bdir = str(Path(tmp) / "backup")
            run_differential_backup(bdir, [str(orig)])

            orig.write_bytes(b"modified")
            result = restore_from_backup(bdir, [str(orig)])

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["restored"]), 1)
            self.assertEqual(orig.read_bytes(), b"original")

    def test_skips_identical_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "orig" / "same.txt"
            orig.parent.mkdir()
            orig.write_bytes(b"same content")

            bdir = str(Path(tmp) / "backup")
            run_differential_backup(bdir, [str(orig)])

            result = restore_from_backup(bdir, [str(orig)])

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["restored"]), 0)
            self.assertEqual(len(result["skipped"]), 1)

    def test_gate_fails_without_backup_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = restore_from_backup(str(Path(tmp) / "nonexistent"))
            self.assertFalse(result["ok"])
            self.assertTrue(any("E_BACKUP_DIR_MISSING" in e for e in result["errors"]))

    def test_restore_all_when_no_target_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig1 = Path(tmp) / "orig" / "a.txt"
            orig2 = Path(tmp) / "orig" / "b.txt"
            orig1.parent.mkdir()
            orig1.write_bytes(b"aaa")
            orig2.write_bytes(b"bbb")

            bdir = str(Path(tmp) / "backup")
            run_differential_backup(bdir, [str(orig1), str(orig2)])

            orig1.write_bytes(b"aaa_modified")
            orig2.write_bytes(b"bbb_modified")

            result = restore_from_backup(bdir)

            self.assertTrue(result["ok"])
            self.assertEqual(len(result["restored"]), 2)
            self.assertEqual(orig1.read_bytes(), b"aaa")
            self.assertEqual(orig2.read_bytes(), b"bbb")


# ── Phase 13: dirty state / conflict / orphan governance ─────────────────────

class TestPhase13Governance(TestCase):
    def test_detect_dirty_state_for_error_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            init_backup_dir(bdir)  # status=error
            result = detect_dirty_state(bdir)
            self.assertTrue(result["dirty"])
            self.assertTrue(any("E_BACKUP_DIRTY_STATE" in e for e in result["errors"]))

    def test_detect_dirty_state_clean_after_finalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            bdir = str(Path(tmp) / "backup")
            init_backup_dir(bdir)
            (Path(bdir) / "file.txt").write_bytes(b"ok")
            finalize_backup_dir(bdir)
            result = detect_dirty_state(bdir)
            self.assertFalse(result["dirty"])
            self.assertEqual(result["errors"], [])

    def test_inspect_conflict_detects_backup_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "orig" / "x.txt"
            orig.parent.mkdir()
            orig.write_bytes(b"before")
            bdir = str(Path(tmp) / "backup")
            run_differential_backup(bdir, [str(orig)])

            mirrored = Path(bdir) / str(orig).lstrip("/")
            mirrored.write_bytes(b"tampered")

            result = inspect_conflict(bdir)
            self.assertFalse(result["clean"])
            self.assertTrue(any("E_ENTITY_CONFLICT" in c for c in result["conflicts"]))

    def test_restore_reports_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig = Path(tmp) / "game" / "keep.txt"
            orig.parent.mkdir(parents=True)
            orig.write_bytes(b"original")
            bdir = str(Path(tmp) / "backup")
            run_differential_backup(bdir, [str(orig)])

            orig.write_bytes(b"changed")
            orphan = Path(tmp) / "game" / "new_orphan.txt"
            orphan.write_bytes(b"orphan")

            result = restore_from_backup(bdir)
            self.assertTrue(result["ok"])
            self.assertIn(str(orphan), result.get("orphans", []))
            self.assertTrue(any("E_EXTERNAL_FILE_ORPHAN" in w for w in result.get("warnings", [])))

    def test_delete_orphan_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            orphan = Path(tmp) / "orphan.txt"
            orphan.write_bytes(b"x")
            result = delete_orphan_files([str(orphan)])
            self.assertTrue(result["ok"])
            self.assertFalse(orphan.exists())
            self.assertIn(str(orphan), result["deleted"])
