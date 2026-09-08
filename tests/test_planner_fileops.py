"""Tests for planner_fileops.py — bakignore filtering behavior.

Semantics per 2026-09-08 adjudication (see
user_memo/audit_logs/2026-09-08_fileops-spec-audit.md):

- bakignore applies to the SOURCE side only (BACKUP intent):
  mapping entries / file lists whose path component ends with a
  bakignore suffix are excluded.
- The derived target backup_dir is an OUTPUT container and must NEVER
  be filtered by bakignore — even when its suffix is in the list
  (auto-sync puts the current baksuffix in bakignore by design).
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from modmgr.orchestrator.entry import Intent, TaskRequest
from modmgr.orchestrator.fileops.planner.planner import plan_fileops

APPID = "270150"
CONTENTID = "2606099273"


def _build_steam_fixture(root: Path) -> None:
    """Create a minimal Steam workshop fixture with ACF files on disk."""
    steamapps = root / "steamapps"
    common = steamapps / "common" / "RunningWithRifles"
    mod = steamapps / "workshop" / "content" / APPID / CONTENTID
    common.mkdir(parents=True)
    mod.mkdir(parents=True)

    # Create a mod file
    (mod / "test_mod_file.txt").write_text("content")
    (mod / "data.bin").write_text("binary")

    # Create appmanifest ACF (needed for app backup stability check)
    (steamapps / f"appmanifest_{APPID}.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"' + APPID + '"\n\t"StateFlags"\t\t"4"\n\t"buildid"\t\t"22924257"\n}\n'
    )

    # Create appworkshop ACF (needed for content backup hex_id)
    ws_dir = steamapps / "workshop"
    ws_dir.mkdir(exist_ok=True)
    (ws_dir / f"appworkshop_{APPID}.acf").write_text(
        '"AppWorkshop"\n{\n\t"WorkshopItemsInstalled"\n\t{\n'
        '\t\t"' + CONTENTID + '"\n\t\t{\n\t\t\t"timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t}\n\t"WorkshopItemDetails"\n\t{\n'
        '\t\t"' + CONTENTID + '"\n\t\t{\n\t\t\t"latest_timeupdated"\t\t"1716297600"\n\t\t}\n'
        '\t}\n}'
    )


def _make_database(root: Path) -> dict:
    return {
        "schema_namespace": "KMM_Database",
        "schema_version": "knighthana@0.1.0",
        "OS": {"workingpathstyle": "linux", "steamlibpathstyle": "linux"},
        "steamlib": [{"path": str(root) + "/", "contains_libraryfolders_vdf": False}],
        "game": [{
            "appid": APPID,
            "name": "RunningWithRifles",
            "basepath": str(root / "steamapps" / "common" / "RunningWithRifles") + "/",
            "modpath": str(root / "steamapps" / "workshop" / "content" / APPID) + "/",
            "mods_found": [CONTENTID],
        }],
        "mod": [
            {
                "mixed_id": f"{APPID}:{CONTENTID}",
                "path": str(root / "steamapps" / "workshop" / "content" / APPID / CONTENTID) + "/",
            },
        ],
        "history": [],
    }


def _make_final_mapping(root: Path) -> list[dict]:
    mod_root = root / "steamapps" / "workshop" / "content" / APPID / CONTENTID
    return [
        {"path": str(mod_root / "test_mod_file.txt"), "game_name": "RunningWithRifles"},
        {"path": str(mod_root / "data.bin"), "game_name": "RunningWithRifles"},
    ]


def _default_user_config() -> dict:
    return {
        "schema_namespace": "KMM_UserConfig",
        "schema_version": "knighthana@0.1.0",
        "baksuffix": "kmmbackup",
        "bakignore": ["kmmbackup"],
    }


def _request(intent: Intent, flags: dict | None = None) -> TaskRequest:
    return TaskRequest(
        identity="cli",
        intent=intent,
        resolver_type="raw_dict",
        resolver_args={},
        flags=flags or {},
    )


def _bakignore_warnings(plan) -> list[str]:
    return [w for w in plan.warnings if "W_BAKIGNORE_FILTERED" in w]


class TestBakignoreSourceSideFiltering:
    """bakignore filters SOURCE-side entries, never the target backup_dir."""

    def test_backup_target_dir_not_filtered_by_matching_bakignore(self) -> None:
        """NEGATIVE TEST for the old wrong behavior: with default config
        (bakignore contains the current baksuffix) the derived target
        backup_dir must NOT be filtered — backup must remain operable."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            context = {
                "final_mapping": _make_final_mapping(root),
                "database": _make_database(root),
                "user_config": _default_user_config(),
            }

            plan = plan_fileops(_request(Intent.BACKUP), context)

            assert plan.backup_dirs, (
                f"target backup_dirs must survive bakignore matching, got {plan.backup_dirs}"
            )
            assert not _bakignore_warnings(plan), (
                f"target backup_dir must not produce bakignore warnings: {_bakignore_warnings(plan)}"
            )
            # All entries survive — they are not inside any backup container
            assert all(len(v) == 2 for v in plan.entries_by_backup_dir.values())

    def test_backup_filters_entries_inside_bakignore_suffixed_dirs(self) -> None:
        """Entries whose path lives inside a directory ending with a
        bakignore suffix (an old backup container) are excluded on the
        source side; the target backup_dir itself is untouched.

        Uses a custom baksuffix ("mybak") that the hardcoded .kmmbackup
        layer does NOT cover — that is exactly bakignore's raison d'être.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            # An "old backup container" from a previous custom baksuffix
            old_backup = (
                root / "steamapps" / "workshop" / "content" / APPID / CONTENTID
                / "2606099273.1716297600.mybak"
            )
            old_backup.mkdir()
            old_file = old_backup / "stale.bin"
            old_file.write_text("stale")

            context = {
                "final_mapping": [
                    {"path": str(root / "steamapps" / "workshop" / "content" / APPID / CONTENTID / "test_mod_file.txt")},
                    {"path": str(old_file)},
                ],
                "database": _make_database(root),
                "user_config": {
                    "schema_namespace": "KMM_UserConfig",
                    "schema_version": "knighthana@0.1.0",
                    "baksuffix": "mybak",
                    "bakignore": ["mybak", "kmmbackup"],
                },
            }

            plan = plan_fileops(_request(Intent.BACKUP), context)

            assert plan.backup_dirs, "target backup_dir must not be filtered"
            assert len(_bakignore_warnings(plan)) == 1, plan.warnings
            # The stale entry is excluded everywhere (file list + entries)
            for files in plan.backup_dirs.values():
                assert all(not p.endswith("stale.bin") for p in files)
            for entries in plan.entries_by_backup_dir.values():
                assert all(not e["path"].endswith("stale.bin") for e in entries)
            # The normal entry survives
            assert any(
                any(e["path"].endswith("test_mod_file.txt") for e in entries)
                for entries in plan.entries_by_backup_dir.values()
            )

    def test_bakignore_not_applied_to_apply(self) -> None:
        """APPLY with bakignore set → no filtering (bakignore is backup-only)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            context = {
                "final_mapping": _make_final_mapping(root),
                "database": _make_database(root),
                "user_config": _default_user_config(),
            }

            plan = plan_fileops(_request(Intent.APPLY, {"force": True}), context)

            assert not _bakignore_warnings(plan), (
                f"bakignore was incorrectly applied to APPLY intent: {_bakignore_warnings(plan)}"
            )

    def test_bakignore_not_applied_to_restore(self) -> None:
        """RESTORE with bakignore set → no filtering (bakignore is backup-only)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            context = {
                "final_mapping": _make_final_mapping(root),
                "database": _make_database(root),
                "user_config": _default_user_config(),
            }

            plan = plan_fileops(_request(Intent.RESTORE, {"force": True}), context)

            assert not _bakignore_warnings(plan), (
                f"bakignore was incorrectly applied to RESTORE intent: {_bakignore_warnings(plan)}"
            )


class TestModSideKmmignoreCollection:
    """.kmmignore files inside mod directories must be collected
    (regression: _derive_source_roots previously only returned basepaths,
    so mod-side .kmmignore was never honored in the production path)."""

    def test_mod_side_kmmignore_filters_entries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            mod_root = root / "steamapps" / "workshop" / "content" / APPID / CONTENTID
            (mod_root / ".kmmignore").write_text("data.bin\n")

            context = {
                "final_mapping": _make_final_mapping(root),
                "database": _make_database(root),
                "user_config": _default_user_config(),
            }

            plan = plan_fileops(_request(Intent.BACKUP), context)

            assert not plan.backup_dirs.get(list(plan.backup_dirs)[0], []) or all(
                not p.endswith("data.bin") for files in plan.backup_dirs.values() for p in files
            ), "data.bin must be filtered by mod-side .kmmignore"
            assert any("W_IGNORE_FILTERED" in w for w in plan.warnings), plan.warnings
            assert any(
                any(e["path"].endswith("test_mod_file.txt") for e in entries)
                for entries in plan.entries_by_backup_dir.values()
            ), "non-ignored entries must survive"

    def test_base_side_kmmignore_still_collected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            base_root = root / "steamapps" / "common" / "RunningWithRifles"
            (base_root / "game.cfg").write_text("cfg")
            (base_root / ".kmmignore").write_text("game.cfg\n")

            context = {
                "final_mapping": [
                    {"path": str(base_root / "game.cfg")},
                    {"path": str(root / "steamapps" / "workshop" / "content" / APPID / CONTENTID / "test_mod_file.txt")},
                ],
                "database": _make_database(root),
                "user_config": _default_user_config(),
            }

            plan = plan_fileops(_request(Intent.BACKUP), context)

            assert any("W_IGNORE_FILTERED" in w for w in plan.warnings), plan.warnings
            assert all(
                not p.endswith("game.cfg")
                for files in plan.backup_dirs.values() for p in files
            )
