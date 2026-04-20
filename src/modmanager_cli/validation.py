"""Input validation for config and database structures per M1 Phase 1 specification."""

from __future__ import annotations

from typing import Any

from .paths import split_mixed_id


def validate_config(config: Any) -> list[str]:
    """Validate config structure and constraints.

    Returns list of error strings (empty means valid).

    Checks:
    1. config must be a dict
    2. config['mod'] must be a list
    3. Each mod entry must have 'mixed_id' as string
    4. All mixed_id must be unique
    5. All mixed_id must be in appid:modid format
    6. actionlist items must have 'from' and 'into' if not action=='hold'
    7. 'destin' must be appid:modid format when provided
    """
    errors: list[str] = []

    # Check top-level structure
    if not isinstance(config, dict):
        return [f"E_CONFIG_INVALID: config must be dict, got {type(config).__name__}"]

    if "mod" not in config:
        return [f"E_CONFIG_INVALID: config missing 'mod' key"]

    mods = config["mod"]
    if not isinstance(mods, list):
        return [f"E_CONFIG_INVALID: config['mod'] must be list, got {type(mods).__name__}"]

    # Track seen mixed_ids for uniqueness
    seen_mixed_ids: set[str] = set()

    for idx, mod_obj in enumerate(mods):
        if not isinstance(mod_obj, dict):
            errors.append(f"E_CONFIG_INVALID: config['mod'][{idx}] must be dict, got {type(mod_obj).__name__}")
            continue

        # Check mixed_id
        mixed_id = mod_obj.get("mixed_id")
        if not isinstance(mixed_id, str):
            errors.append(f"E_CONFIG_INVALID: mod[{idx}]['mixed_id'] must be string, got {type(mixed_id).__name__ if mixed_id is not None else 'null'}")
            continue

        if not mixed_id:
            errors.append(f"E_CONFIG_INVALID: mod[{idx}]['mixed_id'] cannot be empty string")
            continue

        # Check mixed_id format
        if split_mixed_id(mixed_id) is None:
            errors.append(f"E_CONFIG_INVALID: mod[{idx}]['mixed_id'] {mixed_id!r} must be appid:modid format")
            continue

        # Check uniqueness
        if mixed_id in seen_mixed_ids:
            errors.append(f"E_CONFIG_INVALID: mod[{idx}]['mixed_id'] {mixed_id!r} is not unique")
            continue
        seen_mixed_ids.add(mixed_id)

        # Check destin if present
        destin = mod_obj.get("def_destin")
        if destin and isinstance(destin, str):
            if split_mixed_id(destin) is None:
                errors.append(f"E_CONFIG_INVALID: mod[{idx}]['def_destin'] {destin!r} must be appid:modid format")

        # Check actionlist
        actionlist = mod_obj.get("actionlist", [])
        if not isinstance(actionlist, list):
            errors.append(f"E_CONFIG_INVALID: mod[{idx}]['actionlist'] must be list, got {type(actionlist).__name__}")
            continue

        for item_idx, item in enumerate(actionlist):
            if not isinstance(item, dict):
                errors.append(f"E_CONFIG_INVALID: mod[{idx}]['actionlist'][{item_idx}] must be dict, got {type(item).__name__}")
                continue

            action = item.get("action", mod_obj.get("def_action", "hold"))
            if action == "hold":
                continue

            # Non-hold actions require 'from' and 'into'
            if "from" not in item or not isinstance(item.get("from"), str):
                errors.append(f"E_CONFIG_INVALID: mod[{idx}]['actionlist'][{item_idx}] action={action!r} requires 'from' string field")

            if "into" not in item or not isinstance(item.get("into"), str):
                errors.append(f"E_CONFIG_INVALID: mod[{idx}]['actionlist'][{item_idx}] action={action!r} requires 'into' string field")

            # Check destin in actionlist item
            if "destin" in item:
                destin_item = item["destin"]
                if isinstance(destin_item, str) and destin_item:
                    if split_mixed_id(destin_item) is None:
                        errors.append(f"E_CONFIG_INVALID: mod[{idx}]['actionlist'][{item_idx}]['destin'] {destin_item!r} must be appid:modid format")

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


__all__ = ["validate_config", "validate_database"]
