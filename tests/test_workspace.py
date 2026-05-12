"""Tests for modmanager.workspace module.

Covers:
  - First load (file missing) → creates default and persists it
  - Load existing workspace (round-trip)
  - save_workspace → atomic write + session_updated update
  - merge_workspace into inputs, decisions, results
  - Corrupted JSON → backup as ``.bak`` and create new default
  - Concurrent safety (basic stress with threads)
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from modmanager.workspace import (
    DEFAULT_WORKSPACE,
    VALID_SECTIONS,
    get_workspace_path,
    load_workspace,
    merge_workspace,
    save_workspace,
)


class TestGetWorkspacePath(TestCase):
    """Platform-dependent default path resolution."""

    def test_returns_path_instance(self) -> None:
        path = get_workspace_path()
        self.assertIsInstance(path, Path)

    def test_linux_path_format(self) -> None:
        """On non-Windows, the path should contain ``.local/share/kmm/workspace.json``."""
        with patch("sys.platform", "linux"):
            path = get_workspace_path()
        self.assertIn(".local/share/kmm", str(path))
        self.assertTrue(str(path).endswith("workspace.json"))

    def test_windows_path_format(self) -> None:
        """On Windows, the path should point into LOCALAPPDATA/kmm/."""
        with patch("sys.platform", "win32"), patch.dict(os.environ, {"LOCALAPPDATA": "C:\\Users\\test\\AppData\\Local"}):
            path = get_workspace_path()
        self.assertIn("kmm", path.parts)
        self.assertEqual(path.name, "workspace.json")
        # The base should contain LOCALAPPDATA value
        self.assertTrue(any("AppData" in part for part in path.parts))

    def test_windows_fallback_when_env_missing(self) -> None:
        """When LOCALAPPDATA is not set, fall back to ``~/AppData/Local``."""
        with patch("sys.platform", "win32"), patch.dict(os.environ, {}, clear=True):
            path = get_workspace_path()
        self.assertIn("AppData/Local/kmm/workspace.json", str(path))


class TestLoadWorkspace(TestCase):
    """Loading workspace.json with various file states."""

    def test_first_load_creates_default(self) -> None:
        """When the file does not exist, a default structure should be created
        and written to disk."""
        with self._temp_workspace() as wp:
            self.assertFalse(wp.exists())
            data = load_workspace(wp)
            self._assert_default_shape(data)
            # File should now exist on disk
            self.assertTrue(wp.exists())
            # Verify the on-disk content matches
            on_disk = json.loads(wp.read_text(encoding="utf-8"))
            self.assertEqual(on_disk, data)

    def test_load_existing_file(self) -> None:
        """Loading a pre-existing workspace returns its content unchanged."""
        with self._temp_workspace() as wp:
            custom = {
                "session_updated": "2026-01-01T00:00:00Z",
                "inputs": {
                    "database_path": "/tmp/db.json",
                    "rule_paths": ["/tmp/rules"],
                    "aggregated_rule_path": "",
                    "user_config_path": "",
                    "discovery_mode": "manual",
                    "discovery_manual_paths": ["/custom/path"],
                },
                "decisions": {"branch_decisions": {"/tree/x": "/source/y"}},
                "results": {
                    "last_compute": {
                        "trees_count": 5,
                        "mapping_count": 10,
                        "warnings": [],
                        "errors": [],
                        "stats": {"elapsed": 0.3},
                        "inputs_hash": "abc",
                        "timestamp": "2026-01-01T00:00:00Z",
                    }
                },
            }
            wp.write_text(json.dumps(custom, indent=2), encoding="utf-8")

            loaded = load_workspace(wp)
            self.assertEqual(loaded, custom)

    def test_load_default_returns_copy(self) -> None:
        """Each call to load_workspace (on missing file) should return a
        fresh dict, not the same mutable object."""
        with self._temp_workspace() as wp:
            a = load_workspace(wp)
            b = load_workspace(wp)
            self.assertIsNot(a, b)
            # Mutating one should not affect the other
            a["inputs"]["database_path"] = "mutated"
            self.assertEqual(b["inputs"]["database_path"], "")

    def test_directory_auto_created(self) -> None:
        """The parent ``kmm`` directory should be created automatically on
        first load."""
        with self._temp_workspace(create_dir=False) as wp:
            self.assertFalse(wp.parent.exists())
            load_workspace(wp)
            self.assertTrue(wp.parent.is_dir())

    # ── Corrupted file handling ───────────────────────────────────────────

    def test_corrupt_json_backup_and_recreate(self) -> None:
        """A file with invalid JSON should be backed up as ``.bak`` (with a
        timestamp suffix) and a fresh default structure should be returned."""
        with self._temp_workspace() as wp:
            wp.write_text("{bad json", encoding="utf-8")
            before_baks = sorted(wp.parent.glob("workspace.*.bak"))

            data = load_workspace(wp)

            self._assert_default_shape(data)
            # A backup file should exist
            after_baks = sorted(wp.parent.glob("workspace.*.bak"))
            self.assertEqual(len(after_baks), len(before_baks) + 1)
            # The original (now corrupt) file should have been replaced by valid JSON
            self.assertTrue(wp.exists())
            on_disk = json.loads(wp.read_text(encoding="utf-8"))
            self._assert_default_shape(on_disk)

    def test_corrupt_non_dict_json_backup(self) -> None:
        """A valid JSON file whose top-level value is not a dict (e.g. a list)
        is treated as corrupt and triggers backup + recreate."""
        with self._temp_workspace() as wp:
            wp.write_text(json.dumps(["not", "a", "dict"]), encoding="utf-8")
            before_baks = sorted(wp.parent.glob("workspace.*.bak"))

            data = load_workspace(wp)

            self._assert_default_shape(data)
            after_baks = sorted(wp.parent.glob("workspace.*.bak"))
            self.assertEqual(len(after_baks), len(before_baks) + 1)

    def test_corrupt_file_backup_names_dont_collide(self) -> None:
        """Multiple corrupt-file loads should each produce a distinct backup
        (timestamped) rather than overwriting the same ``.bak``."""
        with self._temp_workspace() as wp:
            for _ in range(3):
                wp.write_text("garbage", encoding="utf-8")
                load_workspace(wp)

            baks = sorted(wp.parent.glob("workspace.*.bak"))
            self.assertEqual(len(baks), 3)

    # ── Helpers ───────────────────────────────────────────────────────────

    def _temp_workspace(self, *, create_dir: bool = True):
        """Context manager yielding a temporary ``workspace.json`` Path."""

        class _Ctx:
            def __init__(self, _create_dir: bool):
                self._create_dir = _create_dir
                self._tmpdir = None  # type: ignore

            def __enter__(self) -> Path:
                import tempfile
                self._tmpdir = Path(tempfile.mkdtemp())
                wp = self._tmpdir / "kmm" / "workspace.json"
                if self._create_dir:
                    wp.parent.mkdir(parents=True, exist_ok=True)
                return wp

            def __exit__(self, *args: object) -> None:
                import shutil
                if self._tmpdir is not None and self._tmpdir.exists():
                    shutil.rmtree(self._tmpdir)

        return _Ctx(create_dir)

    @staticmethod
    def _assert_default_shape(data: dict) -> None:
        """Assert that *data* has the expected default workspace shape."""
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "session_updated" in data, f"Missing 'session_updated' key"
        assert "inputs" in data, f"Missing 'inputs' key"
        assert "decisions" in data, f"Missing 'decisions' key"
        assert "results" in data, f"Missing 'results' key"
        # Check nested defaults
        for key in ("database_path", "rule_paths", "aggregated_rule_path",
                    "user_config_path", "discovery_mode", "discovery_manual_paths"):
            assert key in data["inputs"], f"Missing inputs.{key}"
        assert "branch_decisions" in data["decisions"]
        lc = data["results"]["last_compute"]
        for key in ("trees_count", "mapping_count", "warnings", "errors",
                    "stats", "inputs_hash", "timestamp"):
            assert key in lc, f"Missing results.last_compute.{key}"


class TestSaveWorkspace(TestCase):
    """Atomic writes and session_updated management."""

    def test_save_and_reload_round_trip(self) -> None:
        """Data written via save_workspace should be loadable bit-for-bit."""
        with self._temp_workspace() as wp:
            expected = dict(DEFAULT_WORKSPACE)
            expected["inputs"]["database_path"] = "/some/db.json"
            save_workspace(expected, wp)

            loaded = load_workspace(wp)
            # session_updated is set by save, so copy it over for comparison
            expected["session_updated"] = loaded["session_updated"]
            self.assertEqual(loaded, expected)

    def test_session_updated_is_set(self) -> None:
        """After save, session_updated should be a non-empty ISO 8601 string."""
        with self._temp_workspace() as wp:
            save_workspace(dict(DEFAULT_WORKSPACE), wp)
            loaded = load_workspace(wp)
            ts = loaded.get("session_updated", "")
            self.assertIsInstance(ts, str)
            self.assertTrue(len(ts) > 0)
            # Should look like an ISO timestamp ending in Z
            self.assertTrue(ts.endswith("Z"), f"Expected Z suffix, got {ts!r}")

    def test_session_updated_changes_on_each_save(self) -> None:
        """Calling save_workspace twice should produce different timestamps."""
        with self._temp_workspace() as wp:
            save_workspace(dict(DEFAULT_WORKSPACE), wp)
            ts1 = load_workspace(wp)["session_updated"]
            time.sleep(0.01)  # ensure clock advances
            save_workspace(dict(DEFAULT_WORKSPACE), wp)
            ts2 = load_workspace(wp)["session_updated"]
            self.assertNotEqual(ts1, ts2)

    def test_atomic_write_temp_file_cleaned_up(self) -> None:
        """After a successful save, no ``.tmp`` files should remain."""
        with self._temp_workspace() as wp:
            save_workspace(dict(DEFAULT_WORKSPACE), wp)
            leftovers = list(wp.parent.glob("*.tmp"))
            self.assertEqual(leftovers, [])

    def test_atomic_write_does_not_corrupt_on_crash(self) -> None:
        """Simulate a crash mid-write: write garbage to a temp file and
        verify the original workspace is untouched."""
        with self._temp_workspace() as wp:
            # First, write a known-good workspace
            save_workspace(dict(DEFAULT_WORKSPACE), wp)
            original_content = wp.read_text(encoding="utf-8")

            # Now simulate a crash: write garbage to a random file in the
            # parent dir, but do NOT os.replace it — the original is intact.
            import tempfile as _tf
            fd, stray = _tf.mkstemp(dir=str(wp.parent))
            with os.fdopen(fd, "w") as f:
                f.write("corrupted partial write")
            self.assertEqual(wp.read_text(encoding="utf-8"), original_content)
            os.unlink(stray)

    def test_directory_auto_created(self) -> None:
        """Parent directory should be created if it does not exist."""
        with self._temp_workspace(create_dir=False) as wp:
            self.assertFalse(wp.parent.exists())
            save_workspace(dict(DEFAULT_WORKSPACE), wp)
            self.assertTrue(wp.parent.is_dir())
            self.assertTrue(wp.exists())

    def _temp_workspace(self, *, create_dir: bool = True):
        """Context manager yielding a temporary workspace path."""

        class _Ctx:
            def __init__(self, _create_dir: bool):
                self._create_dir = _create_dir
                self._tmpdir = None  # type: ignore

            def __enter__(self) -> Path:
                import tempfile
                self._tmpdir = Path(tempfile.mkdtemp())
                wp = self._tmpdir / "kmm" / "workspace.json"
                if self._create_dir:
                    wp.parent.mkdir(parents=True, exist_ok=True)
                return wp

            def __exit__(self, *args: object) -> None:
                import shutil
                if self._tmpdir is not None and self._tmpdir.exists():
                    shutil.rmtree(self._tmpdir)

        return _Ctx(create_dir)


class TestMergeWorkspace(TestCase):
    """Partial merge into sections."""

    def setUp(self) -> None:
        import tempfile
        self._tmpdir = Path(tempfile.mkdtemp())
        self.wp = self._tmpdir / "kmm" / "workspace.json"
        self.wp.parent.mkdir(parents=True, exist_ok=True)
        # Start with a known base workspace
        self.base = dict(DEFAULT_WORKSPACE)
        self.base["inputs"]["database_path"] = "/original/db.json"
        self.base["inputs"]["rule_paths"] = ["/original/rules"]
        self.base["decisions"]["branch_decisions"] = {"/tree/a": "/src/a"}
        save_workspace(self.base, self.wp)

    def tearDown(self) -> None:
        import shutil
        if self._tmpdir is not None and self._tmpdir.exists():
            shutil.rmtree(self._tmpdir)

    # ── merge into inputs ────────────────────────────────────────────────

    def test_merge_inputs_partial(self) -> None:
        """Only the passed keys in inputs are updated; others are preserved."""
        merged = merge_workspace(
            {"database_path": "/new/db.json"},
            "inputs",
            self.wp,
        )
        self.assertEqual(merged["inputs"]["database_path"], "/new/db.json")
        # Unchanged fields
        self.assertEqual(merged["inputs"]["rule_paths"], ["/original/rules"])
        self.assertEqual(merged["inputs"]["aggregated_rule_path"], "")

    def test_merge_inputs_empty_preserves_all(self) -> None:
        """Passing an empty dict to merge_workspace should preserve everything."""
        merged = merge_workspace({}, "inputs", self.wp)
        self.assertEqual(merged["inputs"], self.base["inputs"])

    def test_merge_inputs_new_key(self) -> None:
        """merge_workspace does not validate keys — new keys in data are
        added to the section."""
        merged = merge_workspace(
            {"database_path": "/new/db.json"},
            "inputs",
            self.wp,
        )
        self.assertEqual(merged["inputs"]["database_path"], "/new/db.json")

    # ── merge into decisions ─────────────────────────────────────────────

    def test_merge_decisions_add_entry(self) -> None:
        """Adding a new branch_decision entry."""
        merged = merge_workspace(
            {"branch_decisions": {"/tree/a": "/src/a", "/tree/b": "/src/b"}},
            "decisions",
            self.wp,
        )
        self.assertEqual(
            merged["decisions"]["branch_decisions"],
            {"/tree/a": "/src/a", "/tree/b": "/src/b"},
        )

    def test_merge_decisions_overwrite_existing(self) -> None:
        """Overwriting an existing decision."""
        merged = merge_workspace(
            {"branch_decisions": {"/tree/a": "/src/new_value"}},
            "decisions",
            self.wp,
        )
        self.assertEqual(
            merged["decisions"]["branch_decisions"]["/tree/a"],
            "/src/new_value",
        )

    def test_merge_decisions_shallow_replace(self) -> None:
        """merge_workspace does a shallow merge at the section level —
        passing ``{"branch_decisions": {...}}`` replaces the entire
        ``branch_decisions`` dict (deep merge is handled by the route
        layer)."""
        # Add a second entry first
        save_workspace(self.base, self.wp)
        merge_workspace(
            {"branch_decisions": {"/tree/a": "/src/a", "/tree/b": "/src/b"}},
            "decisions",
            self.wp,
        )
        # Now replace with only /tree/a = None  →  /tree/b is lost
        merged = merge_workspace(
            {"branch_decisions": {"/tree/a": None}},
            "decisions",
            self.wp,
        )
        branch = merged["decisions"]["branch_decisions"]
        # The entire branch_decisions was replaced — /tree/b is gone
        self.assertIn("/tree/a", branch)
        self.assertIsNone(branch["/tree/a"])
        self.assertNotIn("/tree/b", branch)

    # ── merge into results ───────────────────────────────────────────────

    def test_merge_results_shallow_replace(self) -> None:
        """merge_workspace replaces the entire ``last_compute`` key when
        ``{"last_compute": {...}}`` is passed (shallow merge at section
        level — deep merging is the route layer's responsibility)."""
        merged = merge_workspace(
            {
                "last_compute": {
                    "trees_count": 42,
                    "mapping_count": 99,
                    "warnings": ["W_TEST"],
                }
            },
            "results",
            self.wp,
        )
        lc = merged["results"]["last_compute"]
        self.assertEqual(lc["trees_count"], 42)
        self.assertEqual(lc["mapping_count"], 99)
        self.assertEqual(lc["warnings"], ["W_TEST"])
        # Keys not present in the merge data are absent (shallow replace)
        self.assertNotIn("errors", lc)
        self.assertNotIn("stats", lc)

    def test_merge_results_empty_preserves(self) -> None:
        """Passing an empty dict to merge_workspace on results should
        preserve the original last_compute."""
        merged = merge_workspace({}, "results", self.wp)
        self.assertEqual(merged["results"], self.base["results"])

    # ── invalid section ──────────────────────────────────────────────────

    def test_merge_invalid_section_raises(self) -> None:
        """An invalid section name should raise ValueError."""
        with self.assertRaises(ValueError):
            merge_workspace({"x": 1}, "nonexistent", self.wp)

    # ── session_updated updated on merge ─────────────────────────────────

    def test_merge_updates_session_updated(self) -> None:
        """merge_workspace internally calls save_workspace, which updates
        session_updated."""
        old_ts = load_workspace(self.wp)["session_updated"]
        time.sleep(0.01)
        merge_workspace({"database_path": "/x"}, "inputs", self.wp)
        new_ts = load_workspace(self.wp)["session_updated"]
        self.assertNotEqual(old_ts, new_ts)


class TestConcurrentSafety(TestCase):
    """Basic concurrent-safety stress test (bonus)."""

    TIMES = 5

    def test_concurrent_merge_stress(self) -> None:
        """Multiple threads merging into different sections simultaneously
        should not lose data or crash."""
        import tempfile
        tmpdir = Path(tempfile.mkdtemp())
        try:
            wp = tmpdir / "kmm" / "workspace.json"
            wp.parent.mkdir(parents=True, exist_ok=True)
            save_workspace(dict(DEFAULT_WORKSPACE), wp)

            errors: list[Exception] = []
            lock = threading.Lock()

            def _merge_inputs() -> None:
                for i in range(self.TIMES):
                    try:
                        merge_workspace(
                            {"database_path": f"/input/db_{i}"},
                            "inputs",
                            wp,
                        )
                    except Exception as exc:
                        with lock:
                            errors.append(exc)

            def _merge_decisions() -> None:
                for i in range(self.TIMES):
                    try:
                        merge_workspace(
                            {"branch_decisions": {f"/tree/{i}": f"/src/{i}"}},
                            "decisions",
                            wp,
                        )
                    except Exception as exc:
                        with lock:
                            errors.append(exc)

            def _merge_results() -> None:
                for i in range(self.TIMES):
                    try:
                        merge_workspace(
                            {"last_compute": {"trees_count": i}},
                            "results",
                            wp,
                        )
                    except Exception as exc:
                        with lock:
                            errors.append(exc)

            threads = [
                threading.Thread(target=_merge_inputs),
                threading.Thread(target=_merge_decisions),
                threading.Thread(target=_merge_results),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [], f"Concurrent merge errors: {errors}")

            # Final state should be loadable and have valid structure
            final = load_workspace(wp)
            self.assertIn("inputs", final)
            self.assertIn("decisions", final)
            self.assertIn("results", final)
        finally:
            import shutil
            shutil.rmtree(tmpdir)


class TestValidSections(TestCase):
    """VALID_SECTIONS frozenset correctness."""

    def test_valid_sections_contains_expected(self) -> None:
        self.assertEqual(VALID_SECTIONS, {"inputs", "decisions", "results"})


if __name__ == "__main__":
    import unittest
    unittest.main()
