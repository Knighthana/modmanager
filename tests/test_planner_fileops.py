"""Tests for planner_fileops.py — bakignore filtering behavior."""

from __future__ import annotations

import tempfile
from pathlib import Path

from modmgr.orchestrator.entry import Intent, TaskRequest
from modmgr.orchestrator.planner_fileops import plan_fileops
from modmgr.orchestrator.resolver import CleanContext

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


class TestBakignoreFiltering:
    """plan_fileops bakignore filtering — backup only, suffix match."""

    def test_backup_filters_matching_suffix(self) -> None:
        """BACKUP with bakignore matching baksuffix → all dirs filtered."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            context = CleanContext(
                final_mapping=_make_final_mapping(root),
                database=_make_database(root),
                user_config={
                    "schema_namespace": "KMM_UserConfig",
                    "schema_version": "knighthana@0.1.0",
                    "baksuffix": "kmmbackup",
                    "bakignore": ["kmmbackup"],
                },
            )
            request = TaskRequest(
                identity="cli",
                intent=Intent.BACKUP,
                resolver_type="raw_dict",
                resolver_args={},
            )

            plan = plan_fileops(request, context)

            # All backup dirs end with ".kmmbackup" → matching bakignore → all filtered
            assert not plan.backup_dirs, f"Expected empty backup_dirs, got {plan.backup_dirs}"

            bakignore_warnings = [w for w in plan.warnings if "W_BAKIGNORE_FILTERED" in w]
            assert len(bakignore_warnings) == 1, f"Expected 1 bakignore warning, got {bakignore_warnings}"
            assert "excluded by bakignore" in bakignore_warnings[0]

    def test_backup_does_not_filter_non_matching_suffix(self) -> None:
        """BACKUP with bakignore not matching baksuffix → no filtering."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            context = CleanContext(
                final_mapping=_make_final_mapping(root),
                database=_make_database(root),
                user_config={
                    "schema_namespace": "KMM_UserConfig",
                    "schema_version": "knighthana@0.1.0",
                    "baksuffix": "otherbak",
                    "bakignore": ["kmmbackup"],
                },
            )
            request = TaskRequest(
                identity="cli",
                intent=Intent.BACKUP,
                resolver_type="raw_dict",
                resolver_args={},
            )

            plan = plan_fileops(request, context)

            # backup_dirs should not be empty (non-matching suffix)
            assert plan.backup_dirs, "Expected non-empty backup_dirs"

            bakignore_warnings = [w for w in plan.warnings if "W_BAKIGNORE_FILTERED" in w]
            assert len(bakignore_warnings) == 0, f"Got unexpected bakignore warnings: {bakignore_warnings}"

    def test_bakignore_not_applied_to_apply(self) -> None:
        """APPLY with bakignore set → no filtering (bakignore is backup-only)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            context = CleanContext(
                final_mapping=_make_final_mapping(root),
                database=_make_database(root),
                user_config={
                    "schema_namespace": "KMM_UserConfig",
                    "schema_version": "knighthana@0.1.0",
                    "baksuffix": "kmmbackup",
                    "bakignore": ["kmmbackup"],
                },
            )
            request = TaskRequest(
                identity="cli",
                intent=Intent.APPLY,
                resolver_type="raw_dict",
                resolver_args={},
                flags={"force": True},
            )

            plan = plan_fileops(request, context)

            # bakignore must NOT be applied for non-backup intents
            bakignore_warnings = [w for w in plan.warnings if "W_BAKIGNORE_FILTERED" in w]
            assert len(bakignore_warnings) == 0, (
                f"bakignore was incorrectly applied to APPLY intent: {bakignore_warnings}"
            )

    def test_bakignore_not_applied_to_restore(self) -> None:
        """RESTORE with bakignore set → no filtering (bakignore is backup-only)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _build_steam_fixture(root)

            context = CleanContext(
                final_mapping=_make_final_mapping(root),
                database=_make_database(root),
                user_config={
                    "schema_namespace": "KMM_UserConfig",
                    "schema_version": "knighthana@0.1.0",
                    "baksuffix": "kmmbackup",
                    "bakignore": ["kmmbackup"],
                },
            )
            request = TaskRequest(
                identity="cli",
                intent=Intent.RESTORE,
                resolver_type="raw_dict",
                resolver_args={},
                flags={"force": True},
            )

            plan = plan_fileops(request, context)

            bakignore_warnings = [w for w in plan.warnings if "W_BAKIGNORE_FILTERED" in w]
            assert len(bakignore_warnings) == 0, (
                f"bakignore was incorrectly applied to RESTORE intent: {bakignore_warnings}"
            )
