"""Aggregator: merge multiple kmm_rule JSON files into a single aggregated_rule_set.

This module implements the aggregation pipeline defined in
``repo_memo/RULE_AGGREGATION_DESIGN.md`` (sections 2-7). It is logically
independent of ``engine.py`` and relies only on shared infrastructure
(``iojson``, ``validation``, ``paths``).

Pipeline overview (6 steps):
    1. Load all kmm_rule files (validate root structure)
    2. Build permission maps (game_permissions, sub_permissions) — first pass
    3. Per-file concretization and injection — second pass
    4. Cross-file merge — third pass
    5. Permission filtering — fourth pass
    6. Validate via ``validate_aggregated_rule_set`` and optionally write output
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .iojson import load_json_file, write_json_file
from .paths import split_mixed_id
from .validation import validate_aggregated_rule_set

__all__ = ["aggregate"]


# ---------------------------------------------------------------------------
# Step 2 — Load all kmm_rule files
# ---------------------------------------------------------------------------

def _load_kmm_rules(kmm_rule_paths: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Load every kmm_rule file, validating top-level structure.

    Each file must be a dict with a ``"mod"`` key that is a list.
    Errors are accumulated per file; remaining files are still processed.
    Returns ``(loaded_rule_dicts, errors)``.
    """
    loaded: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in kmm_rule_paths:
        try:
            data = load_json_file(path)
        except Exception as exc:
            errors.append(f"E_KMM_RULE_LOAD_FAILED: {path}: {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(
                f"E_KMM_RULE_INVALID: {path}: "
                f"expected dict, got {type(data).__name__}"
            )
            continue
        mod_list = data.get("mod")
        if not isinstance(mod_list, list):
            errors.append(
                f"E_KMM_RULE_INVALID: {path}: "
                f"'mod' key is missing or not a list"
            )
            continue
        loaded.append(data)
    return loaded, errors


# ---------------------------------------------------------------------------
# Step 3 — Build permission maps (first pass over all files)
# ---------------------------------------------------------------------------

def _build_permission_maps(
    loaded_rules: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build ``game_permissions`` and ``sub_permissions`` from all rules.

    ``game_permissions[appid]`` → set of modids that can write to game base.
    ``sub_permissions[dom_mixed_id]`` → set of actor mixed_ids that are
    recognised sub-mods.

    Both are unions across every input file.
    """
    game_permissions: dict[str, set[str]] = {}
    sub_permissions: dict[str, set[str]] = {}

    for rule in loaded_rules:
        # --- game[] ---
        for game_entry in rule.get("game", []):
            if not isinstance(game_entry, dict):
                continue
            appid = game_entry.get("appid", "")
            if not isinstance(appid, str):
                continue
            modids = game_entry.get("modid", [])
            if not isinstance(modids, list):
                continue
            perms = game_permissions.setdefault(appid, set())
            for mid in modids:
                if isinstance(mid, str):
                    perms.add(mid)

        # --- mod[].sub[] ---
        for mod_entry in rule.get("mod", []):
            if not isinstance(mod_entry, dict):
                continue
            mixed_id = mod_entry.get("mixed_id", "")
            if not isinstance(mixed_id, str) or not mixed_id:
                continue
            sub_list = mod_entry.get("sub", [])
            if not isinstance(sub_list, list):
                continue
            perms = sub_permissions.setdefault(mixed_id, set())
            for sub_entry in sub_list:
                if isinstance(sub_entry, str):
                    perms.add(sub_entry)

    return game_permissions, sub_permissions


# ---------------------------------------------------------------------------
# Step 4 — Per-file concretization and injection (second pass)
# ---------------------------------------------------------------------------

def _process_file(
    rule: dict[str, Any],
    file_path: str,
    action_orders: dict[str, int] | None,
    sidecar_refs: dict[str, dict[str, dict[int, str]]] | None,
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, str],
    dict[str, list[str]],
    dict[str, list[str]],
    list[str],
]:
    """Process a single kmm_rule file.

    For each mod entry:
      * concretize ``action`` / ``destin`` via ``def_action`` / ``def_destin``
      * filter ``hold`` actions
      * filter ``destin="none"`` actions
      * inject ``provenance_ref``, ``action_order``, ``sidecar_ref``

    Returns:
        ``(processed_actions, nicknames, previews, readmes, warnings)``
        each keyed by ``mixed_id``.
    """
    processed: dict[str, list[dict[str, Any]]] = {}
    nicknames: dict[str, str] = {}
    previews: dict[str, list[str]] = {}
    readmes: dict[str, list[str]] = {}
    warnings: list[str] = []

    file_abs_path = str(Path(file_path).resolve())
    _has_action_orders = action_orders is not None
    _has_sidecar_refs = sidecar_refs is not None
    action_orders = action_orders or {}
    sidecar_refs = sidecar_refs or {}

    for mod_entry in rule.get("mod", []):
        if not isinstance(mod_entry, dict):
            continue

        mixed_id = mod_entry.get("mixed_id", "")
        if not isinstance(mixed_id, str) or not mixed_id:
            continue

        def_destin = mod_entry.get("def_destin", "")
        def_action = mod_entry.get("def_action", "hold")

        # --- collect metadata ---
        nicknames[mixed_id] = mod_entry.get("nickname", "")

        raw_preview = mod_entry.get("preview", [])
        previews[mixed_id] = (
            [str(p) for p in raw_preview] if isinstance(raw_preview, list) else []
        )

        raw_readme = mod_entry.get("readme", [])
        readmes[mixed_id] = (
            [str(r) for r in raw_readme] if isinstance(raw_readme, list) else []
        )

        # --- process actionlist ---
        actionlist = mod_entry.get("actionlist", [])
        if not isinstance(actionlist, list):
            actionlist = []

        # sidecar_ref sub-map for this file → mixed_id
        file_sidecar = sidecar_refs.get(file_abs_path, {})
        mixed_sidecar = file_sidecar.get(mixed_id, {})

        actions_for_mod: list[dict[str, Any]] = []

        for action_idx, action_item in enumerate(actionlist):
            if not isinstance(action_item, dict):
                continue

            # 4a. Concretize action & destin
            action = action_item.get("action", def_action)
            destin = action_item.get("destin", def_destin)

            # 4b. Filter hold
            if action == "hold":
                continue

            # 4c. Filter destin=none
            if isinstance(destin, str) and destin.strip().lower() == "none":
                warnings.append(
                    f"W_DESTIN_NONE_SKIPPED: {file_path}: "
                    f"mixed_id={mixed_id}, action_idx={action_idx}"
                )
                continue

            # 4d. Inject provenance_ref
            # 4e. Inject action_order
            act_order = action_orders.get(mixed_id, 0)
            if _has_action_orders and mixed_id not in action_orders:
                warnings.append(
                    f"W_ACTION_ORDER_DEFAULTED: {file_path}: "
                    f"mixed_id={mixed_id}, action_idx={action_idx}, "
                    f"defaulted to 0"
                )

            # 4f. Inject sidecar_ref
            side_val: str = mixed_sidecar.get(action_idx, "404")
            if _has_sidecar_refs and action_idx not in mixed_sidecar:
                warnings.append(
                    f"W_SIDECAR_REF_DEFAULTED: {file_path}: "
                    f"mixed_id={mixed_id}, action_idx={action_idx}, "
                    f"defaulted to '404'"
                )

            # 4g. Build output action dict (only kept fields)
            processed_action: dict[str, Any] = {
                "action": action,
                "destin": destin,
                "action_order": act_order,
                "provenance_ref": file_abs_path,
                "sidecar_ref": side_val,
            }

            # Conditionally copy optional fields from original item
            for field in ("from", "from_type", "into", "into_type", "nwname"):
                if field in action_item:
                    processed_action[field] = action_item[field]

            # 4h. Fix trailing slashes for path-type from/into lists
            #     (only when from_type/into_type is "path", not "file")
            _from_type = processed_action.get("from_type")
            _into_type = processed_action.get("into_type")

            if _from_type == "path":
                raw_from = processed_action.get("from", [])
                fixed_from: list[str] = []
                for _entry in raw_from:
                    if isinstance(_entry, str):
                        _has_glob = any(ch in _entry for ch in "*?[]")
                        if not _has_glob and not _entry.endswith("/"):
                            _fixed = _entry + "/"
                            warnings.append(
                                f"W_PATH_TRAILING_SLASH_FIXED: "
                                f"{mixed_id}#{action_idx}:from[{_entry}]→{_fixed}"
                            )
                            fixed_from.append(_fixed)
                        else:
                            fixed_from.append(_entry)
                    else:
                        fixed_from.append(_entry)
                processed_action["from"] = fixed_from

            if _into_type == "path":
                raw_into = processed_action.get("into", [])
                fixed_into: list[str] = []
                for _entry in raw_into:
                    if isinstance(_entry, str):
                        if _entry.endswith("/") or _entry.endswith("."):
                            fixed_into.append(_entry)
                        else:
                            _fixed = _entry + "/"
                            warnings.append(
                                f"W_PATH_TRAILING_SLASH_FIXED: "
                                f"{mixed_id}#{action_idx}:into[{_entry}]→{_fixed}"
                            )
                            fixed_into.append(_fixed)
                    else:
                        fixed_into.append(_entry)
                processed_action["into"] = fixed_into

            actions_for_mod.append(processed_action)

        if actions_for_mod:
            # Extend (multiple mod entries with same mixed_id in one file)
            existing = processed.setdefault(mixed_id, [])
            existing.extend(actions_for_mod)
        else:
            # Still add an entry so cross-file merge knows about this mixed_id,
            # even if all actions were filtered (empty actionlist after filter).
            processed.setdefault(mixed_id, [])

    return processed, nicknames, previews, readmes, warnings


# ---------------------------------------------------------------------------
# Step 5 — Cross-file merge (third pass)
# ---------------------------------------------------------------------------

def _merge_operations(
    all_processed: list[dict[str, list[dict[str, Any]]]],
    all_nicknames: list[dict[str, str]],
    all_previews: list[dict[str, list[str]]],
    all_readmes: list[dict[str, list[str]]],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, str],
    dict[str, list[str]],
    dict[str, list[str]],
    list[str],
]:
    """Merge per-file processed data into single operation entries.

    * ``actionlist``: concatenated in file order.
    * ``preview`` / ``readme``: extended + deduplicated.
    * ``nickname``: last non-empty wins (default ``""``).
    """
    merged_actions: dict[str, list[dict[str, Any]]] = {}
    merged_nicknames: dict[str, str] = {}
    merged_previews: dict[str, list[str]] = {}
    merged_readmes: dict[str, list[str]] = {}
    warnings: list[str] = []

    num_files = len(all_processed)

    for file_idx in range(num_files):
        processed = all_processed[file_idx]
        nicknames = all_nicknames[file_idx]
        previews = all_previews[file_idx]
        readmes = all_readmes[file_idx]

        # --- actionlist: concatenate in file order ---
        for mixed_id, actions in processed.items():
            if mixed_id in merged_actions:
                merged_actions[mixed_id].extend(actions)
            else:
                merged_actions[mixed_id] = list(actions)

        # --- nickname: last non-empty wins ---
        for mixed_id, nick in nicknames.items():
            if nick:  # skip empty strings
                if (
                    mixed_id in merged_nicknames
                    and merged_nicknames[mixed_id]
                    and merged_nicknames[mixed_id] != nick
                ):
                    warnings.append(
                        f"W_NICKNAME_CONFLICT: {mixed_id}: "
                        f"'{merged_nicknames[mixed_id]}' vs '{nick}', "
                        f"using latter"
                    )
                merged_nicknames[mixed_id] = nick
            elif mixed_id not in merged_nicknames:
                # first file provides empty nickname → still record it
                merged_nicknames[mixed_id] = nick

        # --- preview: extend + dedup ---
        for mixed_id, prev in previews.items():
            if mixed_id in merged_previews:
                existing = merged_previews[mixed_id]
                for p in prev:
                    if p not in existing:
                        existing.append(p)
            else:
                merged_previews[mixed_id] = list(prev)

        # --- readme: extend + dedup ---
        for mixed_id, read in readmes.items():
            if mixed_id in merged_readmes:
                existing = merged_readmes[mixed_id]
                for r in read:
                    if r not in existing:
                        existing.append(r)
            else:
                merged_readmes[mixed_id] = list(read)

    # Ensure every mixed_id that appears in actions has defaults for metadata
    for mixed_id in merged_actions:
        merged_nicknames.setdefault(mixed_id, "")
        merged_previews.setdefault(mixed_id, [])
        merged_readmes.setdefault(mixed_id, [])

    return merged_actions, merged_nicknames, merged_previews, merged_readmes, warnings


# ---------------------------------------------------------------------------
# Step 6 — Permission filtering (fourth pass)
# ---------------------------------------------------------------------------

def _filter_permissions(
    merged_actions: dict[str, list[dict[str, Any]]],
    merged_nicknames: dict[str, str],
    merged_previews: dict[str, list[str]],
    merged_readmes: dict[str, list[str]],
    game_permissions: dict[str, set[str]],
    sub_permissions: dict[str, set[str]],
) -> tuple[dict[str, list[dict[str, Any]]], list[str], list[str]]:
    """Filter actions that fail permission checks.

    * Base-target actions (``destin`` modid == ``"0"``) require the actor's
      modid to be in ``game_permissions[appid]``.
    * Sub-mod-target actions require the actor's full ``mixed_id`` to be in
      ``sub_permissions[destin]``.
    * Failed actions are removed and logged as errors.
    * Operations that end up with empty actionlists get a warning.
    """
    errors: list[str] = []
    warnings: list[str] = []

    for mixed_id in list(merged_actions.keys()):
        actions = merged_actions[mixed_id]
        filtered: list[dict[str, Any]] = []

        for action in actions:
            destin = action.get("destin", "")
            actor_parts = split_mixed_id(mixed_id)
            destin_parts = split_mixed_id(destin)

            # If either mixed_id is unparseable, skip permission check
            # (validation will catch these later).
            if actor_parts is None or destin_parts is None:
                filtered.append(action)
                continue

            _actor_appid, actor_modid = actor_parts
            _target_appid, target_modid = destin_parts

            if target_modid == "0":
                # --- base permission check ---
                perms = game_permissions.get(_target_appid, set())
                if actor_modid not in perms:
                    errors.append(
                        f"E_PERMISSION_DENIED_BASE: {mixed_id} -> {destin}"
                    )
                    continue  # remove this action
            else:
                # --- sub permission check ---
                perms = sub_permissions.get(destin, set())
                if mixed_id not in perms:
                    errors.append(
                        f"E_PERMISSION_DENIED_SUB: {mixed_id} -> {destin}"
                    )
                    continue  # remove this action

            filtered.append(action)

        if not filtered:
            warnings.append(
                f"W_EMPTY_ACTIONLIST_AFTER_FILTER: {mixed_id}"
            )

        merged_actions[mixed_id] = filtered

    return merged_actions, errors, warnings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate(
    kmm_rule_paths: list[str],
    *,
    action_orders: dict[str, int] | None = None,
    sidecar_refs: dict[str, dict[str, dict[int, str]]] | None = None,
    output_path: str | None = None,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Aggregate multiple kmm_rule JSON files into a single aggregated_rule_set.

    This is the main entry point for the aggregation pipeline defined in
    ``repo_memo/RULE_AGGREGATION_DESIGN.md``.

    Args:
        kmm_rule_paths:
            List of paths to ``kmm_rule_*.json`` files.
        action_orders:
            Optional mapping ``{mixed_id: int}`` — injected into every action
            of the corresponding operation.
        sidecar_refs:
            Optional 3-level mapping
            ``{file_abs_path: {mixed_id: {action_index: sidecar_ref}}}``
            for injecting sidecar references.
        output_path:
            If provided, the aggregated rule set is written to this path.

    Returns:
        ``(aggregated_rule_set_or_None, errors, warnings)``.
        When ``errors`` is non-empty the first element is ``None``.
    """
    all_errors: list[str] = []
    all_warnings: list[str] = []

    # ------------------------------------------------------------------
    # Step 1 — Load all kmm_rule files
    # ------------------------------------------------------------------
    loaded_rules, errs = _load_kmm_rules(kmm_rule_paths)
    all_errors.extend(errs)
    if not loaded_rules:
        return None, all_errors, all_warnings

    # ------------------------------------------------------------------
    # Step 2 — Build permission maps (first pass)
    # ------------------------------------------------------------------
    game_permissions, sub_permissions = _build_permission_maps(loaded_rules)

    # ------------------------------------------------------------------
    # Step 3 — Per-file concretization and injection (second pass)
    # ------------------------------------------------------------------
    all_processed: list[dict[str, list[dict[str, Any]]]] = []
    all_nicknames: list[dict[str, str]] = []
    all_previews: list[dict[str, list[str]]] = []
    all_readmes: list[dict[str, list[str]]] = []

    for file_path, rule in zip(kmm_rule_paths, loaded_rules):
        processed, nicknames_, previews_, readmes_, warns = _process_file(
            rule, file_path, action_orders, sidecar_refs,
        )
        all_processed.append(processed)
        all_nicknames.append(nicknames_)
        all_previews.append(previews_)
        all_readmes.append(readmes_)
        all_warnings.extend(warns)

    # ------------------------------------------------------------------
    # Step 4 — Cross-file merge (third pass)
    # ------------------------------------------------------------------
    merged_actions, merged_nicknames, merged_previews, merged_readmes, warns = (
        _merge_operations(
            all_processed, all_nicknames, all_previews, all_readmes,
        )
    )
    all_warnings.extend(warns)

    # ------------------------------------------------------------------
    # Step 5 — Permission filtering (fourth pass)
    # ------------------------------------------------------------------
    merged_actions, errs, warns = _filter_permissions(
        merged_actions,
        merged_nicknames,
        merged_previews,
        merged_readmes,
        game_permissions,
        sub_permissions,
    )
    all_errors.extend(errs)
    all_warnings.extend(warns)

    # ------------------------------------------------------------------
    # Step 6 — Build output, validate, optionally write
    # ------------------------------------------------------------------
    operations: list[dict[str, Any]] = []
    # Preserve deterministic ordering: insertion order of mixed_ids
    for mixed_id in merged_actions:
        op: dict[str, Any] = {
            "mixed_id": mixed_id,
            "nickname": merged_nicknames.get(mixed_id, ""),
            "preview": merged_previews.get(mixed_id, []),
            "readme": merged_readmes.get(mixed_id, []),
            "actionlist": merged_actions[mixed_id],
        }
        operations.append(op)

    result: dict[str, Any] = {
        "schema_namespace": "KMM_RuleSet",
        "schema_version": "knighthana@0.1.0",
        "operation": operations,
    }

    # Validate
    val_errors = validate_aggregated_rule_set(result)
    if val_errors:
        all_errors.extend(val_errors)
        return None, all_errors, all_warnings

    # Write output
    if output_path is not None:
        try:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            write_json_file(output_path, result)
        except Exception as exc:
            all_errors.append(
                f"E_OUTPUT_WRITE_FAILED: {output_path}: {exc}"
            )
            return None, all_errors, all_warnings

    return result, all_errors, all_warnings
