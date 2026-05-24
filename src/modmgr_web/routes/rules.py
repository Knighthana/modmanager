"""Rules routes — scan / read / affected-entries.

All endpoints operate on the local file system and return simple JSON
responses wrapped in the standard ``ApiResponse`` envelope.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from modmgr.bootstrap import discover_user_config
from modmgr.iojson import load_json_file
from modmgr.path_resolver import expand_path, resolve_directory_path, resolve_file_path
from ..adapters import resolve_config_index, adapt_dict_result, adapt_error
from ..schemas import (
    RulesAffectedEntriesRequest,
    RulesListSourcesRequest,
    RulesReadRequest,
    RulesScanBySourceRequest,
    RulesScanRequest,
)

router = APIRouter()


@router.post("/scan")
async def rules_scan(req: RulesScanRequest):
    """List ``*.kmmrule.json`` files in *dir* (non-recursive).

    Returns an ``ApiResponse`` with ``{ files: [{ name, path, size }] }``.
    """
    if not req.dir:
        return adapt_error("dir is required")

    try:
        scan_dir = resolve_directory_path(req.dir, Path(req.dir.rstrip("/")).name)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        return adapt_error(str(exc))

    try:
        entries = os.listdir(scan_dir)
    except PermissionError:
        return adapt_error(f"permission denied: {scan_dir}")
    except OSError as exc:
        return adapt_error(f"cannot list directory: {scan_dir}: {exc}")

    files: list[dict] = []
    for name in sorted(entries):
        if not name.endswith(".kmmrule.json"):
            continue
        full_path = str(Path(scan_dir) / name)
        try:
            st = os.stat(full_path)
            files.append({
                "name": name,
                "path": full_path,
                "size": st.st_size,
            })
        except OSError:
            # Skip files we cannot stat (permission, broken symlink, etc.)
            continue

    return adapt_dict_result({"files": files})


@router.post("/read")
async def rules_read(req: RulesReadRequest):
    """Read the raw text content of a file at *path*.

    Returns an ``ApiResponse`` with ``{ content, name, path, size }``.
    Returns ``ok: false`` if the file does not exist or cannot be read.
    """
    if not req.path:
        return adapt_error("path is required")

    try:
        file_path = resolve_file_path(req.path, Path(req.path).name)
    except (FileNotFoundError, IsADirectoryError, ValueError) as exc:
        return adapt_error(str(exc))

    try:
        p = Path(file_path)
        content = p.read_text(encoding="utf-8")
        st = p.stat()
        return adapt_dict_result({
            "content": content,
            "name": p.name,
            "path": str(p),
            "size": st.st_size,
        })
    except (OSError, UnicodeDecodeError) as exc:
        return adapt_error(f"cannot read file: {file_path}: {exc}")


@router.post("/affected-entries")
async def rules_affected_entries(req: RulesAffectedEntriesRequest):
    """Query the database for game/mod entries referenced by an aggregated rule set.

    Accepts ``{ aggregated_rule_path?, aggregated_rule_set?, database_name }``.
    The aggregated rule set can be provided either inline via
    ``aggregated_rule_set`` or by path via ``aggregated_rule_path``.
    Loads the rule set together with the database (resolved via
    ``database_name`` from user_config), and returns libraries/games/mods entries
    with ``libraryIndex`` and ``has_duplicate`` markers.
    """
    if not req.aggregated_rule_path and not req.aggregated_rule_set:
        return adapt_error("aggregated_rule_path or aggregated_rule_set is required")

    try:
        # Load aggregated rule set — prefer dict if provided, else load from file
        if req.aggregated_rule_set:
            agg_rules = req.aggregated_rule_set
        else:
            agg_rules = load_json_file(expand_path(req.aggregated_rule_path))
    except Exception as exc:
        return adapt_error(f"failed to load aggregated rule set: {exc}")

    # Load database from user_config via database_name
    try:
        user_config, _ = discover_user_config(config_index=resolve_config_index(req.config_index))
        db_entry = user_config.get("databases", {}).get(req.database_name)
        if db_entry:
            db_path = db_entry["path"]
            from modmgr.iojson import load_json_file as ljf
            database = ljf(db_path)
        else:
            database = {"steamlib": [], "game": [], "mod": []}
    except Exception:
        database = {"steamlib": [], "game": [], "mod": []}

    # Extract referenced appids and mixed_ids from the aggregated rule set
    referenced_mixed_ids: set[str] = set()
    referenced_appids: set[str] = set()
    nickname_by_mixed_id: dict[str, str] = {}
    for op in agg_rules.get("operation", []):
        mid = op.get("mixed_id", "")
        if mid:
            referenced_mixed_ids.add(mid)
            appid = mid.split(":")[0] if ":" in mid else ""
            if appid:
                referenced_appids.add(appid)
            nick = op.get("nickname", "")
            if nick:
                nickname_by_mixed_id[mid] = nick

    # Build library index: match game basepath by prefix against steamlib paths
    basepath_to_lib_idx: dict[str, int] = {}
    steamlib_list = database.get("steamlib", []) or []
    for idx, lib in enumerate(steamlib_list):
        bp = lib.get("path", "")
        if bp:
            basepath_to_lib_idx[bp.rstrip("/")] = idx

    # Collect libraries
    libraries: list[dict] = []
    lib_indices_used: set[int] = set()
    # Synthetic library entries for basepaths not found in steamlib
    synthetic_libs: dict[str, int] = {}

    # Process games
    games_list = database.get("game", []) or []
    game_appid_counts: dict[str, int] = {}
    for g in games_list:
        appid = str(g.get("appid", ""))
        if appid:
            game_appid_counts[appid] = game_appid_counts.get(appid, 0) + 1

    games_out: list[dict] = []
    for g in games_list:
        appid = str(g.get("appid", ""))
        # Only include games referenced by the aggregated rules
        if appid not in referenced_appids:
            continue
        basepath = g.get("basepath", "")
        # Prefix match: find which steamlib contains this game
        lib_idx = -1
        for lib_path, li in basepath_to_lib_idx.items():
            if basepath.startswith(lib_path):
                lib_idx = li
                break
        # Fallback: create a synthetic library entry for this basepath
        if lib_idx < 0 and basepath:
            parts = basepath.rstrip("/").rsplit("/steamapps/", 1)
            if len(parts) == 2:
                derived_path = parts[0] + "/steamapps/"
                if derived_path not in synthetic_libs:
                    synthetic_libs[derived_path] = len(steamlib_list) + len(synthetic_libs)
                lib_idx = synthetic_libs[derived_path]
        if lib_idx >= 0:
            lib_indices_used.add(lib_idx)
        games_out.append({
            "appid": appid,
            "name": g.get("name", ""),
            "basepath": basepath,
            "libraryIndex": lib_idx,
            "has_duplicate": game_appid_counts.get(appid, 0) > 1,
        })

    # Process mods
    mods_list = database.get("mod", []) or []
    mod_mixed_id_counts: dict[str, int] = {}
    for m in mods_list:
        mid = str(m.get("mixed_id", ""))
        if mid:
            mod_mixed_id_counts[mid] = mod_mixed_id_counts.get(mid, 0) + 1

    mods_out: list[dict] = []
    for m in mods_list:
        mixed_id = str(m.get("mixed_id", ""))
        # Only include mods referenced by the aggregated rules
        if mixed_id not in referenced_mixed_ids:
            continue
        game_appid = mixed_id.split(":")[0] if ":" in mixed_id else ""
        # Find the correct game entry: match by modpath prefix (same steamapps root)
        game_entry = None
        for g in database.get("game", []):
            if str(g.get("appid", "")) == game_appid:
                modpath = g.get("modpath", "")
                if modpath and m.get("path", "").startswith(modpath):
                    game_entry = g
                    break
        if not game_entry:
            # Fallback: match by appid only
            for g in database.get("game", []):
                if str(g.get("appid", "")) == game_appid:
                    game_entry = g
                    break
        basepath = game_entry.get("basepath", "") if game_entry else ""
        game_idx = next((i for i, g in enumerate(games_out) if g["appid"] == game_appid), -1)
        lib_idx = -1
        for lib_path, li in basepath_to_lib_idx.items():
            if basepath.startswith(lib_path):
                lib_idx = li
                break
        # Fallback: use synthetic library if basepath not in steamlib
        if lib_idx < 0 and basepath:
            parts = basepath.rstrip("/").rsplit("/steamapps/", 1)
            if len(parts) == 2:
                derived_path = parts[0] + "/steamapps/"
                lib_idx = synthetic_libs.get(derived_path, -1)
        if lib_idx >= 0:
            lib_indices_used.add(lib_idx)
        mods_out.append({
            "mixed_id": mixed_id,
            "nickname": nickname_by_mixed_id.get(mixed_id, m.get("nickname", "")),
            "path": m.get("path", ""),
            "libraryIndex": lib_idx,
            "gameIndex": game_idx,
            "has_duplicate": mod_mixed_id_counts.get(mixed_id, 0) > 1,
        })

    # Build library list (only libraries that have referenced entries)
    for idx, lib in enumerate(steamlib_list):
        if idx in lib_indices_used:
            lib_path = lib.get("path", "")
            game_count = sum(1 for g in games_out if g["libraryIndex"] == idx)
            mod_count = sum(1 for m in mods_out if m["libraryIndex"] == idx)
            libraries.append({
                "index": idx,
                "path": lib_path,
                "game_count": game_count,
                "mod_count": mod_count,
            })

    # Add synthetic library entries (basepaths not in steamlib)
    for derived_path, lib_idx in synthetic_libs.items():
        game_count = sum(1 for g in games_out if g["libraryIndex"] == lib_idx)
        mod_count = sum(1 for m in mods_out if m["libraryIndex"] == lib_idx)
        libraries.append({
            "index": lib_idx,
            "path": derived_path,
            "game_count": game_count,
            "mod_count": mod_count,
        })

    return {
        "ok": True,
        "data": {
            "libraries": libraries,
            "games": games_out,
            "mods": mods_out,
        },
        "errors": [],
        "warnings": [],
    }


@router.post("/list-sources")
async def rules_list_sources(req: RulesListSourcesRequest):
    """List available rule source names from user_config.

    Returns source_names array — the keys of user_config.rule_sources.
    """
    config, _ = discover_user_config(config_index=resolve_config_index(req.config_index))
    rule_sources = config.get("rule_sources", {})
    if not isinstance(rule_sources, dict):
        rule_sources = {}
    source_names = sorted(rule_sources.keys())  # sorted for stable order
    return adapt_dict_result({"source_names": source_names})


@router.post("/scan-by-source")
async def rules_scan_by_source(req: RulesScanBySourceRequest):
    """Scan rule files for a named source.

    Reads rule_sources[name].paths from user_config, expands paths,
    scans directories for *.kmmrule.json files, collects direct file refs,
    deduplicates by path, and returns file list.

    Warnings are returned for paths that don't exist.
    """
    config, _ = discover_user_config(config_index=resolve_config_index(req.config_index))
    rule_sources = config.get("rule_sources", {})

    if not isinstance(rule_sources, dict) or req.source_name not in rule_sources:
        return adapt_error(f"E_SOURCE_NOT_FOUND: '{req.source_name}'")

    source = rule_sources[req.source_name]
    paths = source.get("paths", []) if isinstance(source, dict) else []

    files: list[dict] = []
    warnings: list[str] = []
    seen: set[str] = set()

    for raw_path in paths:
        try:
            expanded = expand_path(raw_path)
        except Exception:
            warnings.append(f"W_PATH_NOT_FOUND: failed to expand '{raw_path}'")
            continue

        p = Path(expanded)

        if p.is_file():
            # Direct file reference — user knows what they want, don't gate on extension
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                st = p.stat()
                files.append({
                    "name": p.name,
                    "path": str(p),
                    "size": st.st_size,
                })
        elif expanded.endswith("/"):
            # Directory scan
            if p.is_dir():
                try:
                    for entry in sorted(p.iterdir()):
                        if entry.name.endswith(".kmmrule.json") and entry.is_file():
                            key = str(entry.resolve())
                            if key not in seen:
                                seen.add(key)
                                st = entry.stat()
                                files.append({
                                    "name": entry.name,
                                    "path": str(entry),
                                    "size": st.st_size,
                                })
                except PermissionError:
                    warnings.append(f"W_PATH_NOT_FOUND: permission denied: {expanded}")
                except OSError as exc:
                    warnings.append(f"W_PATH_NOT_FOUND: cannot list: {expanded}: {exc}")
            else:
                warnings.append(f"W_PATH_NOT_FOUND: directory not found: {expanded}")

    return {
        "ok": True,
        "data": {
            "source_name": req.source_name,
            "files": files,
        },
        "errors": [],
        "warnings": warnings,
    }


