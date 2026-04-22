"""Input validation for aggregated rule set and database structures per M1 Phase 1 specification."""

from __future__ import annotations

from typing import Any

from .paths import split_mixed_id


def _is_none_destin(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() == "none"


def validate_aggregated_rule_set(aggregated_rule_set: Any) -> list[str]:
    """Validate aggregated rule set structure and constraints.

    Returns list of error strings (empty means valid).

    Checks:
    1. aggregated_rule_set must be a dict
    2. aggregated_rule_set['mod'] must be a list
    3. Each mod entry must have 'mixed_id' as string
    4. All mixed_id must be unique
    5. All mixed_id must be in appid:modid format
    6. actionlist items must have 'from' and 'into' if not action=='hold'
    7. 'destin' must be appid:modid format or 'none' when provided
    """
    errors: list[str] = []

    # Check top-level structure
    if not isinstance(aggregated_rule_set, dict):
        return [f"E_AGGREGATED_RULE_SET_INVALID: aggregated_rule_set must be dict, got {type(aggregated_rule_set).__name__}"]

    if "mod" not in aggregated_rule_set:
        return [f"E_AGGREGATED_RULE_SET_INVALID: aggregated_rule_set missing 'mod' key"]

    mods = aggregated_rule_set["mod"]
    if not isinstance(mods, list):
        return [f"E_AGGREGATED_RULE_SET_INVALID: aggregated_rule_set['mod'] must be list, got {type(mods).__name__}"]

    # Track seen mixed_ids for uniqueness
    seen_mixed_ids: set[str] = set()

    for idx, mod_obj in enumerate(mods):
        if not isinstance(mod_obj, dict):
            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: aggregated_rule_set['mod'][{idx}] must be dict, got {type(mod_obj).__name__}")
            continue

        # Check mixed_id
        mixed_id = mod_obj.get("mixed_id")
        if not isinstance(mixed_id, str):
            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['mixed_id'] must be string, got {type(mixed_id).__name__ if mixed_id is not None else 'null'}")
            continue

        if not mixed_id:
            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['mixed_id'] cannot be empty string")
            continue

        # Check mixed_id format
        if split_mixed_id(mixed_id) is None:
            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['mixed_id'] {mixed_id!r} must be appid:modid format")
            continue

        # Check uniqueness
        if mixed_id in seen_mixed_ids:
            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['mixed_id'] {mixed_id!r} is not unique")
            continue
        seen_mixed_ids.add(mixed_id)

        # Check destin if present
        destin = mod_obj.get("def_destin")
        if destin and isinstance(destin, str):
            if not _is_none_destin(destin) and split_mixed_id(destin) is None:
                errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['def_destin'] {destin!r} must be appid:modid format or 'none'")

        # Check actionlist
        actionlist = mod_obj.get("actionlist", [])
        if not isinstance(actionlist, list):
            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'] must be list, got {type(actionlist).__name__}")
            continue

        for item_idx, item in enumerate(actionlist):
            if not isinstance(item, dict):
                errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] must be dict, got {type(item).__name__}")
                continue

            action = item.get("action", mod_obj.get("def_action", "hold"))
            if action == "hold":
                continue

            # Non-hold and non-delete actions require 'from' and 'into' as list[string]
            # delete is special: from/from_type are ignored, so they can be missing
            if action != "delete":
                from_list = item.get("from")
                if not isinstance(from_list, list) or not from_list or not all(isinstance(f, str) for f in from_list):
                    errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] action={action!r} requires 'from' list[string] field")
            
            into_list = item.get("into")
            if not isinstance(into_list, list) or not into_list or not all(isinstance(t, str) for t in into_list):
                errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] action={action!r} requires 'into' list[string] field")
                continue  # Skip further checks if into is invalid

            # Non-hold and non-delete actions require from_type and into_type
            if action != "delete":
                from_type = item.get("from_type")
                if from_type not in {"file", "path"}:
                    errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] action={action!r} requires 'from_type' in {{file, path}}")
                
                into_type = item.get("into_type")
                if into_type not in {"file", "path"}:
                    errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] action={action!r} requires 'into_type' in {{file, path}}")
                    continue  # Skip further checks if into_type is invalid

                # Rule 1: if from is multi-value or contains glob, into cannot be multi-value
                from_is_multi = len(from_list) > 1 if isinstance(from_list, list) else False
                from_has_glob = any("*" in f or "?" in f or "[" in f for f in (from_list if isinstance(from_list, list) else []))
                into_is_multi = len(into_list) > 1
                if (from_is_multi or from_has_glob) and into_is_multi:
                    errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] forbids multi-source to multi-target in single action")

                # Rule 4: into_type=file requires from_type=file
                if into_type == "file" and from_type != "file":
                    errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] into_type=file requires from_type=file")

                # Rule 5: _type=path requires all paths end with /
                if from_type == "path":
                    for f_idx, f in enumerate(from_list if isinstance(from_list, list) else []):
                        if not f.endswith("/"):
                            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] from[{f_idx}] from_type=path requires path to end with /")
                if into_type == "path":
                    for t_idx, t in enumerate(into_list):
                        if not t.endswith("/"):
                            errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] into[{t_idx}] into_type=path requires path to end with /")
            elif action == "delete":
                # delete: only check into_type
                into_type = item.get("into_type")
                if into_type not in {"file", "path"}:
                    errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] action={action!r} requires 'into_type' in {{file, path}}")
                else:
                    # Rule 5 for delete: into_type=path requires all paths end with /
                    if into_type == "path":
                        for t_idx, t in enumerate(into_list):
                            if not t.endswith("/"):
                                errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}] into[{t_idx}] into_type=path requires path to end with /")

            # Check destin in actionlist item
            if "destin" in item:
                destin_item = item["destin"]
                if isinstance(destin_item, str) and destin_item:
                    if not _is_none_destin(destin_item) and split_mixed_id(destin_item) is None:
                        errors.append(f"E_AGGREGATED_RULE_SET_INVALID: mod[{idx}]['actionlist'][{item_idx}]['destin'] {destin_item!r} must be appid:modid format or 'none'")

    return errors


def validate_database(database: Any) -> list[str]:
    """Validate database structure and constraints.

    Returns list of error strings (empty means valid).

    Checks:
    1. database must be a dict
    2. database['game'] must be list
    3. Each game entry must have 'appid' as string
    4. All appid must be unique
    5. game entries must have 'basepath' and 'modpath'
    """
    errors: list[str] = []

    # Check top-level structure
    if not isinstance(database, dict):
        return [f"E_DATABASE_INVALID: database must be dict, got {type(database).__name__}"]

    if "game" not in database:
        return [f"E_DATABASE_INVALID: database missing 'game' key"]

    games = database["game"]
    if not isinstance(games, list):
        return [f"E_DATABASE_INVALID: database['game'] must be list, got {type(games).__name__}"]

    # Track seen appids for uniqueness
    seen_appids: set[str] = set()

    for idx, game_obj in enumerate(games):
        if not isinstance(game_obj, dict):
            errors.append(f"E_DATABASE_INVALID: database['game'][{idx}] must be dict, got {type(game_obj).__name__}")
            continue

        # Check appid
        appid = game_obj.get("appid")
        if not isinstance(appid, str):
            errors.append(f"E_DATABASE_INVALID: game[{idx}]['appid'] must be string, got {type(appid).__name__ if appid is not None else 'null'}")
            continue

        if not appid:
            errors.append(f"E_DATABASE_INVALID: game[{idx}]['appid'] cannot be empty string")
            continue

        # Check uniqueness
        if appid in seen_appids:
            errors.append(f"E_DATABASE_INVALID: game[{idx}]['appid'] {appid!r} is not unique")
            continue
        seen_appids.add(appid)

        # Check required path fields
        basepath = game_obj.get("basepath")
        if not isinstance(basepath, str) or not basepath:
            errors.append(f"E_DATABASE_INVALID: game[{idx}]['basepath'] must be non-empty string")

        modpath = game_obj.get("modpath")
        if not isinstance(modpath, str) or not modpath:
            errors.append(f"E_DATABASE_INVALID: game[{idx}]['modpath'] must be non-empty string")

    return errors


__all__ = ["validate_aggregated_rule_set", "validate_database"]
