from __future__ import annotations

from copy import deepcopy
from typing import Any

from .paths import normalize_posix, split_mixed_id
from .steam_scanner import GameInfo, SteamLibraryInfo, SteamScanner


def _ensure_steamapps(path: str) -> str:
    normalized = normalize_posix(path)
    if normalized.endswith("/steamapps"):
        return normalized
    return normalized + "/steamapps"


def _ensure_database_shape(database: dict[str, Any]) -> None:
    database.setdefault("OS", {"workingpathstyle": "linux", "steamlibpathstyle": "linux"})
    database.setdefault("steamlib", [])
    database.setdefault("game", [])
    database.setdefault("dommod", [])


def _dommod_index(database: dict[str, Any]) -> dict[str, dict[str, Any]]:
    idx: dict[str, dict[str, Any]] = {}
    for item in database.get("dommod", []):
        if not isinstance(item, dict):
            continue
        mixed_id = item.get("mixed_id")
        if isinstance(mixed_id, str) and mixed_id:
            idx[mixed_id] = item
    return idx


def _build_dommod_from_games(games: list[dict[str, Any]], old_dommod: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    old_dommod = old_dommod or {}
    dommods: list[dict[str, Any]] = []
    for game in games:
        appid = str(game.get("appid", ""))
        modpath = game.get("modpath")
        mods_found = game.get("mods_found", [])
        if not appid or not isinstance(modpath, str):
            continue
        normalized_modpath = normalize_posix(modpath)
        for modid in mods_found if isinstance(mods_found, list) else []:
            modid_str = str(modid)
            mixed_id = f"{appid}:{modid_str}"
            prev = old_dommod.get(mixed_id, {})
            localdate = prev.get("localdate", game.get("localdate", 0))
            dommods.append(
                {
                    "mixed_id": mixed_id,
                    "localdate": localdate if isinstance(localdate, (int, float)) else 0,
                    "path": f"{normalized_modpath}/{modid_str}",
                }
            )
    return dommods


def _merge_libraries(auto_libraries: list[SteamLibraryInfo], manual_libraries: list[SteamLibraryInfo]) -> list[SteamLibraryInfo]:
    merged: dict[str, SteamLibraryInfo] = {}

    for lib in auto_libraries:
        key = _ensure_steamapps(lib.path)
        merged[key] = SteamLibraryInfo(
            path=key,
            contains_libraryfolders_vdf=lib.contains_libraryfolders_vdf,
            games_found=sorted(set(lib.games_found or [])),
        )

    # Manual entries override same-path automatic metadata.
    for lib in manual_libraries:
        key = _ensure_steamapps(lib.path)
        merged[key] = SteamLibraryInfo(
            path=key,
            contains_libraryfolders_vdf=lib.contains_libraryfolders_vdf,
            games_found=sorted(set(lib.games_found or [])),
        )

    return list(merged.values())


def _scan_from_libraries(
    scanner: SteamScanner,
    libraries: list[SteamLibraryInfo],
    *,
    greedy_parsing: bool,
) -> dict[str, Any]:
    game_map: dict[str, dict[str, Any]] = {}
    steamlibs_out: list[dict[str, Any]] = []
    warnings: list[str] = []

    for lib in libraries:
        path = _ensure_steamapps(lib.path)
        scoped_ids = set(str(x) for x in (lib.games_found or []))

        discovered_games = scanner.discover_games_in_library(path)
        per_library_ids = sorted(set(scoped_ids | set(discovered_games.keys())))

        steamlibs_out.append(
            {
                "path": path,
                "contains_libraryfolders_vdf": bool(lib.contains_libraryfolders_vdf),
                "game": per_library_ids,
            }
        )

        for appid, game_info in discovered_games.items():
            should_parse = greedy_parsing or not scoped_ids or appid in scoped_ids
            mods = scanner.discover_mods_for_game(appid, game_info.modpath) if should_parse else []
            if appid in game_map:
                warnings.append(
                    f"W_DUPLICATE_APPID: appid {appid} found in multiple libraries: "
                    f"{game_map[appid].get('basepath', '')} and {game_info.basepath}"
                )
                # Keep first occurrence — do not overwrite
            else:
                game_map[appid] = {
                    "appid": game_info.appid,
                    "name": game_info.name,
                    "localdate": 0,
                    "basepath": normalize_posix(game_info.basepath),
                    "modpath": normalize_posix(game_info.modpath),
                    "mods_found": mods,
                }

    games_out = [game_map[k] for k in sorted(game_map.keys())]
    dommods_out = _build_dommod_from_games(games_out)

    return {
        "OS": {
            "workingpathstyle": scanner.working_pathstyle,
            "steamlibpathstyle": scanner.steamlib_pathstyle,
        },
        "steamlib": steamlibs_out,
        "game": games_out,
        "dommod": dommods_out,
        "warnings": warnings,
    }


def discover_with_fallback(
    *,
    working_pathstyle: str = "linux",
    manual_override_steamlibs: list[dict[str, Any]] | None = None,
    greedy_parsing: bool = False,
    manual_only: bool = False,
) -> dict[str, Any]:
    scanner = SteamScanner(working_pathstyle=working_pathstyle)

    if manual_only:
        auto_libraries = []
    else:
        try:
            auto_libraries = scanner.discover_steam_libraries()
        except Exception:
            auto_libraries = []

    manual_libraries: list[SteamLibraryInfo] = []
    for item in manual_override_steamlibs or []:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            continue
        manual_libraries.append(
            SteamLibraryInfo(
                path=_ensure_steamapps(path),
                contains_libraryfolders_vdf=bool(item.get("contains_libraryfolders_vdf", False)),
                games_found=[str(x) for x in item.get("game", []) if str(x)],
            )
        )

    libraries = _merge_libraries(auto_libraries, manual_libraries)
    if not libraries:
        raise ValueError("No usable working directory; provide at least one manual steam library path")

    return _scan_from_libraries(scanner, libraries, greedy_parsing=greedy_parsing)


def list_steamlibs(database: dict[str, Any]) -> list[dict[str, Any]]:
    _ensure_database_shape(database)
    return deepcopy(database["steamlib"])


def add_manual_steamlib(
    database: dict[str, Any],
    *,
    path: str,
    contains_libraryfolders_vdf: bool = False,
) -> tuple[bool, str]:
    _ensure_database_shape(database)
    target = _ensure_steamapps(path)

    for lib in database["steamlib"]:
        if normalize_posix(str(lib.get("path", ""))) == target:
            lib["contains_libraryfolders_vdf"] = bool(lib.get("contains_libraryfolders_vdf", False) or contains_libraryfolders_vdf)
            lib.setdefault("game", [])
            return False, "steam library already exists"

    database["steamlib"].append(
        {
            "path": target,
            "contains_libraryfolders_vdf": contains_libraryfolders_vdf,
            "game": [],
        }
    )
    return True, "steam library added"


def remove_manual_steamlib(database: dict[str, Any], *, path: str) -> tuple[bool, str]:
    _ensure_database_shape(database)
    target = _ensure_steamapps(path)

    removed = False
    removed_appids: set[str] = set()
    kept_steamlib: list[dict[str, Any]] = []

    for lib in database["steamlib"]:
        lib_path = normalize_posix(str(lib.get("path", "")))
        if lib_path == target:
            removed = True
            removed_appids.update(str(x) for x in lib.get("game", []) if str(x))
            continue
        kept_steamlib.append(lib)

    if not removed:
        return False, "steam library not found"

    for game in database["game"]:
        appid = str(game.get("appid", ""))
        modpath = normalize_posix(str(game.get("modpath", "")))
        basepath = normalize_posix(str(game.get("basepath", "")))
        if modpath.startswith(target + "/") or basepath.startswith(target + "/"):
            removed_appids.add(appid)

    database["steamlib"] = kept_steamlib
    database["game"] = [g for g in database["game"] if str(g.get("appid", "")) not in removed_appids]

    for lib in database["steamlib"]:
        lib["game"] = [x for x in lib.get("game", []) if str(x) not in removed_appids]

    database["dommod"] = [
        d
        for d in database["dommod"]
        if str(d.get("mixed_id", "")).split(":", 1)[0] not in removed_appids
    ]

    return True, "steam library removed"


def update_manual_steamlib(database: dict[str, Any], *, old_path: str, new_path: str) -> tuple[bool, str]:
    _ensure_database_shape(database)
    old_norm = _ensure_steamapps(old_path)
    new_norm = _ensure_steamapps(new_path)

    for lib in database["steamlib"]:
        if normalize_posix(str(lib.get("path", ""))) == new_norm and new_norm != old_norm:
            return False, "new steam library path already exists"

    target_lib: dict[str, Any] | None = None
    for lib in database["steamlib"]:
        if normalize_posix(str(lib.get("path", ""))) == old_norm:
            target_lib = lib
            break

    if target_lib is None:
        return False, "steam library not found"

    target_lib["path"] = new_norm

    for game in database["game"]:
        for key in ("basepath", "modpath"):
            value = game.get(key)
            if isinstance(value, str):
                normalized = normalize_posix(value)
                if normalized == old_norm:
                    game[key] = new_norm
                elif normalized.startswith(old_norm + "/"):
                    game[key] = new_norm + normalized[len(old_norm):]

    for dom in database["dommod"]:
        value = dom.get("path")
        if isinstance(value, str):
            normalized = normalize_posix(value)
            if normalized.startswith(old_norm + "/"):
                dom["path"] = new_norm + normalized[len(old_norm):]

    return True, "steam library updated"


def _remove_game_membership(database: dict[str, Any], appid: str) -> None:
    for lib in database.get("steamlib", []):
        games = [str(x) for x in lib.get("game", [])]
        lib["game"] = [x for x in games if x != appid]


def _add_game_membership(database: dict[str, Any], appid: str, modpath: str) -> None:
    normalized_modpath = normalize_posix(modpath)
    for lib in database.get("steamlib", []):
        lib_path = normalize_posix(str(lib.get("path", "")))
        if normalized_modpath.startswith(lib_path + "/workshop/content/"):
            games = [str(x) for x in lib.get("game", [])]
            if appid not in games:
                games.append(appid)
                lib["game"] = sorted(set(games))


def list_games(database: dict[str, Any], *, steamlib_path: str | None = None) -> list[dict[str, Any]]:
    _ensure_database_shape(database)
    if steamlib_path is None:
        return deepcopy(database["game"])

    target = _ensure_steamapps(steamlib_path)
    out: list[dict[str, Any]] = []
    for game in database["game"]:
        modpath = game.get("modpath")
        if isinstance(modpath, str) and normalize_posix(modpath).startswith(target + "/"):
            out.append(deepcopy(game))
    return out


def add_manual_game(
    database: dict[str, Any],
    *,
    appid: str,
    name: str,
    basepath: str,
    modpath: str,
    mods_found: list[str] | None = None,
    localdate: int | float = 0,
) -> tuple[bool, str]:
    _ensure_database_shape(database)
    appid = str(appid)

    if any(str(g.get("appid", "")) == appid for g in database["game"]):
        return False, "game already exists"

    mods = sorted(set(str(m) for m in (mods_found or [])))
    game = {
        "appid": appid,
        "name": name,
        "localdate": localdate,
        "basepath": normalize_posix(basepath),
        "modpath": normalize_posix(modpath),
        "mods_found": mods,
    }
    database["game"].append(game)
    _add_game_membership(database, appid, game["modpath"])

    old_dommod = _dommod_index(database)
    database["dommod"] = _build_dommod_from_games(database["game"], old_dommod)
    return True, "game added"


def remove_manual_game(database: dict[str, Any], *, appid: str) -> tuple[bool, str]:
    _ensure_database_shape(database)
    appid = str(appid)

    before = len(database["game"])
    database["game"] = [g for g in database["game"] if str(g.get("appid", "")) != appid]
    if len(database["game"]) == before:
        return False, "game not found"

    _remove_game_membership(database, appid)
    database["dommod"] = [
        d for d in database["dommod"] if str(d.get("mixed_id", "")).split(":", 1)[0] != appid
    ]
    return True, "game removed"


def update_manual_game(database: dict[str, Any], *, appid: str, updates: dict[str, Any]) -> tuple[bool, str]:
    _ensure_database_shape(database)
    appid = str(appid)

    target: dict[str, Any] | None = None
    for game in database["game"]:
        if str(game.get("appid", "")) == appid:
            target = game
            break

    if target is None:
        return False, "game not found"

    allowed = {"name", "localdate", "basepath", "modpath", "mods_found"}
    for key, value in updates.items():
        if key not in allowed:
            continue
        if key in {"basepath", "modpath"} and isinstance(value, str):
            target[key] = normalize_posix(value)
        elif key == "mods_found" and isinstance(value, list):
            target[key] = sorted(set(str(m) for m in value))
        else:
            target[key] = value

    _remove_game_membership(database, appid)
    if isinstance(target.get("modpath"), str):
        _add_game_membership(database, appid, target["modpath"])

    old_dommod = _dommod_index(database)
    database["dommod"] = _build_dommod_from_games(database["game"], old_dommod)
    return True, "game updated"


def verify_database_integrity(database: dict[str, Any]) -> list[str]:
    _ensure_database_shape(database)
    issues: list[str] = []

    game_by_appid: dict[str, dict[str, Any]] = {
        str(g.get("appid", "")): g for g in database["game"] if isinstance(g, dict)
    }
    dom_by_mixed = _dommod_index(database)

    for appid, game in game_by_appid.items():
        mods = [str(m) for m in game.get("mods_found", []) if str(m)]
        modpath = game.get("modpath")
        if not isinstance(modpath, str):
            continue
        normalized_modpath = normalize_posix(modpath)
        for modid in mods:
            mixed_id = f"{appid}:{modid}"
            expected_path = f"{normalized_modpath}/{modid}"
            dom = dom_by_mixed.get(mixed_id)
            if dom is None:
                issues.append(f"missing dommod for {mixed_id}")
                continue
            dom_path = dom.get("path")
            if not isinstance(dom_path, str) or normalize_posix(dom_path) != expected_path:
                issues.append(f"dommod path mismatch for {mixed_id}")

    for mixed_id in dom_by_mixed:
        parts = split_mixed_id(mixed_id)
        if parts is None:
            issues.append(f"invalid dommod mixed_id: {mixed_id}")
            continue
        appid, modid = parts
        game = game_by_appid.get(appid)
        if game is None:
            issues.append(f"dommod references missing game: {mixed_id}")
            continue
        mods = [str(m) for m in game.get("mods_found", [])]
        if modid not in mods:
            issues.append(f"dommod references missing mod entry: {mixed_id}")

    return sorted(set(issues))


def liveupdate_database(
    database: dict[str, Any],
    *,
    working_pathstyle: str = "linux",
    greedy_parsing: bool = False,
) -> dict[str, Any]:
    _ensure_database_shape(database)
    if not database["steamlib"]:
        raise ValueError("No steam libraries configured")

    old_db = deepcopy(database)
    scanner = SteamScanner(working_pathstyle=working_pathstyle)
    libraries = [
        SteamLibraryInfo(
            path=str(lib.get("path", "")),
            contains_libraryfolders_vdf=bool(lib.get("contains_libraryfolders_vdf", False)),
            games_found=[str(x) for x in lib.get("game", []) if str(x)],
        )
        for lib in old_db["steamlib"]
    ]

    updated = _scan_from_libraries(scanner, libraries, greedy_parsing=greedy_parsing)

    old_games = {str(g.get("appid", "")): g for g in old_db.get("game", [])}
    new_games = {str(g.get("appid", "")): g for g in updated.get("game", [])}

    old_ids = set(old_games.keys())
    new_ids = set(new_games.keys())
    both_ids = old_ids & new_ids

    mods_added: dict[str, list[str]] = {}
    mods_removed: dict[str, list[str]] = {}
    games_updated: list[str] = []

    for appid in sorted(both_ids):
        old_mods = set(str(x) for x in old_games[appid].get("mods_found", []))
        new_mods = set(str(x) for x in new_games[appid].get("mods_found", []))
        add = sorted(new_mods - old_mods)
        remove = sorted(old_mods - new_mods)
        if add:
            mods_added[appid] = add
        if remove:
            mods_removed[appid] = remove
        if old_games[appid] != new_games[appid]:
            games_updated.append(appid)

    return {
        "updated_database": updated,
        "changes": {
            "games_added": sorted(new_ids - old_ids),
            "games_removed": sorted(old_ids - new_ids),
            "games_updated": sorted(games_updated),
            "mods_added": mods_added,
            "mods_removed": mods_removed,
        },
        "warnings": updated.get("warnings", []),
        "errors": [],
    }


def regen_database(
    database: dict[str, Any],
    *,
    working_pathstyle: str = "linux",
    greedy_parsing: bool = False,
) -> dict[str, Any]:
    _ensure_database_shape(database)
    if not database["steamlib"]:
        raise ValueError("No steam libraries configured")

    scanner = SteamScanner(working_pathstyle=working_pathstyle)
    libraries = [
        SteamLibraryInfo(
            path=str(lib.get("path", "")),
            contains_libraryfolders_vdf=bool(lib.get("contains_libraryfolders_vdf", False)),
            games_found=[str(x) for x in lib.get("game", []) if str(x)],
        )
        for lib in database["steamlib"]
    ]

    rebuilt = _scan_from_libraries(scanner, libraries, greedy_parsing=greedy_parsing)
    return {
        "database": rebuilt,
        "stats": {
            "libraries_count": len(rebuilt.get("steamlib", [])),
            "games_count": len(rebuilt.get("game", [])),
            "mods_count": sum(len(g.get("mods_found", [])) for g in rebuilt.get("game", [])),
        },
        "errors": [],
        "warnings": rebuilt.get("warnings", []),
    }


__all__ = [
    "discover_with_fallback",
    "list_steamlibs",
    "add_manual_steamlib",
    "remove_manual_steamlib",
    "update_manual_steamlib",
    "list_games",
    "add_manual_game",
    "remove_manual_game",
    "update_manual_game",
    "verify_database_integrity",
    "liveupdate_database",
    "regen_database",
]
