from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import (
    build_game_index,
    is_numeric_modid,
    mod_root_from_mixed_id,
    normalize_posix,
)
from .validation import validate_aggregated_rule_set, validate_database


VALID_ACTIONS = {"hold", "replace", "create", "delete", "rename_then_replace", "clear_then_copy"}


@dataclass
class RuleItem:
    actor_mixed_id: str
    destin_mixed_id: str
    action: str
    source_path: str | None
    into_path: str | None
    nwname: str | None


def _norm(path: str) -> str:
    return normalize_posix(path)


def _is_none_destin(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() == "none"


def _normalize_ref_string(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return "404"


def _normalize_action_order(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _build_change_request(
    *,
    path: str,
    action: str,
    mixed_id: str,
    hashtype: str,
    hashvalue: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "path": path,
        "action": action,
        "action_order": _normalize_action_order(item.get("action_order")),
        "provenance_ref": _normalize_ref_string(item.get("provenance_ref")),
        "sidecar_ref": _normalize_ref_string(item.get("sidecar_ref")),
        "mixed_id": mixed_id,
        "hashtype": hashtype,
        "hashvalue": hashvalue,
    }


def _sort_request_key(r: dict[str, Any]) -> tuple[int, int, str]:
    mid = r.get("mixed_id", "")
    modid = mid.split(":", 1)[1] if ":" in mid else mid
    is_custom = 0 if modid.isdigit() else 1
    numeric_key = int(modid) if modid.isdigit() else 0
    return (is_custom, numeric_key, modid)


def _pick_request_by_action_order(
    target: str,
    ordered: list[dict[str, Any]],
    branch_decisions: dict[str, Any],
    errors: list[str],
) -> dict[str, Any] | None:
    chosen_source = branch_decisions.get(target)
    candidates = [r.get("path", "") for r in ordered]
    if chosen_source:
        chosen = next((r for r in ordered if r.get("path") == chosen_source), None)
        if chosen is None:
            errors.append(
                f"E_BRANCH_DECISION_INVALID_SOURCE: {target}: "
                f"{chosen_source!r} not in candidates {candidates!r}"
            )
            return None
        return chosen

    orders = [_normalize_action_order(r.get("action_order")) for r in ordered]
    if any(v == 0 for v in orders):
        errors.append(
            f"E_ACTION_ORDER_CONFLICT: {target}: branching candidates contain action_order=0"
        )
        return None

    max_order = max(orders)
    top = [r for r in ordered if _normalize_action_order(r.get("action_order")) == max_order]
    if len(top) != 1:
        errors.append(
            f"E_ACTION_ORDER_CONFLICT: {target}: non-unique highest action_order={max_order}"
        )
        return None
    return top[0]


def _resolve_effective_leaf_request(
    target: str,
    mapping: dict[str, dict[str, Any]],
    branch_decisions: dict[str, Any],
    errors: list[str],
    visiting: set[str] | None = None,
) -> dict[str, Any] | None:
    visiting = visiting or set()
    if target in visiting:
        errors.append(f"E_ACTION_ORDER_RESOLVE_CYCLE: {target}")
        return None

    node = mapping.get(target)
    if not node:
        return None

    requests = node.get("changerequest", [])
    if not requests:
        return None

    ordered = sorted(requests, key=_sort_request_key)
    if len(ordered) == 1:
        chosen = ordered[0]
    else:
        chosen = _pick_request_by_action_order(target, ordered, branch_decisions, errors)
        if chosen is None:
            return None

    src_path = chosen.get("path", "")
    if isinstance(src_path, str) and src_path and src_path != "!" and src_path in mapping:
        visiting.add(target)
        resolved = _resolve_effective_leaf_request(src_path, mapping, branch_decisions, errors, visiting)
        visiting.discard(target)
        return resolved

    return chosen


def _expand_sources(source_root: str, source_expr: str, source_type: str = "file") -> list[str]:
    source_root_path = Path(source_root)
    pattern_path = normalize_posix(source_expr)
    has_glob = any(ch in pattern_path for ch in "*?[]")
    if not has_glob:
        candidate = source_root_path / pattern_path
        return [str(candidate)] if candidate.exists() else []

    matches: list[str] = []
    if not source_root_path.exists():
        return []
    for found in sorted(source_root_path.glob(pattern_path), key=lambda p: normalize_posix(str(p.relative_to(source_root_path)))):
        if source_type == "path":
            if not found.is_dir():
                continue
        else:
            if not found.is_file():
                continue
        matches.append(str(found))
    return matches


def _target_for(
    dest_root: str,
    into_expr: str,
    source_file: str,
    nwname: str | None,
    *,
    from_type: str = "file",
    into_type: str = "path",
) -> str:
    dest = Path(dest_root) / normalize_posix(into_expr)
    if from_type == "path" and into_type == "path":
        return str(dest / Path(source_file).name)
    name = nwname if nwname else Path(source_file).name
    return str(dest / name)


def _check_filefoldertree_transition(old_tree: dict[str, Any], new_tree: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def walk(old_node: dict[str, Any], new_node: dict[str, Any], pfx: str) -> None:
        node_name = old_node.get("name", "")
        path = f"{pfx}/{node_name}" if pfx else str(node_name)

        for key in ("name", "type"):
            if old_node.get(key) != new_node.get(key):
                errors.append(f"E_TREE_NODE_MUTATION: {path}: {key} changed")

        old_children = old_node.get("children", []) if old_node.get("type") == "folder" else []
        new_children = new_node.get("children", []) if new_node.get("type") == "folder" else []
        old_sig = [(c.get("name"), c.get("type")) for c in old_children]
        new_sig = [(c.get("name"), c.get("type")) for c in new_children]
        if old_sig != new_sig:
            errors.append(f"E_TREE_STRUCTURE_MUTATION: {path}")
            return

        if old_node.get("type") == "file":
            old_backuped = bool(old_node.get("isbackuped", False))
            new_backuped = bool(new_node.get("isbackuped", False))
            if old_backuped and not new_backuped:
                errors.append(f"E_TREE_ATTR_BACKWARD: {path}: isbackuped true->false")

            old_hashtype = str(old_node.get("hashtype", "invalid"))
            new_hashtype = str(new_node.get("hashtype", "invalid"))
            if old_hashtype != "invalid" and new_hashtype == "invalid":
                errors.append(f"E_TREE_ATTR_BACKWARD: {path}: hashtype valid->invalid")

            old_hash = str(old_node.get("hashvalue", "0"))
            new_hash = str(new_node.get("hashvalue", "0"))
            if old_hash != "0" and new_hash == "0":
                errors.append(f"E_TREE_ATTR_BACKWARD: {path}: hashvalue valid->0")

        for old_child, new_child in zip(old_children, new_children):
            walk(old_child, new_child, path)

    walk(old_tree, new_tree, "")
    return errors


def validate_branch_decisions_schema(branch_decisions: Any) -> list[str]:
    """Validate the structure of branch_decisions.

    Expected schema::

        {"<target_path>": "<chosen_source_path>", ...}

    Returns a list of error code strings (empty means valid).
    """
    if not isinstance(branch_decisions, dict):
        return [f"E_BRANCH_DECISION_INVALID_SCHEMA: must be an object, got {type(branch_decisions).__name__}"]
    errs: list[str] = []
    for k, v in branch_decisions.items():
        if not isinstance(k, str):
            errs.append(f"E_BRANCH_DECISION_INVALID_SCHEMA: key {k!r} must be a string")
        if not isinstance(v, str):
            errs.append(f"E_BRANCH_DECISION_INVALID_SCHEMA: value for key {k!r} must be a string, got {type(v).__name__}")
    return errs


def find_cycles(edges: dict[str, set[str]]) -> list[list[str]]:
    """Return a list of all distinct cycles found in *edges*.

    Each cycle is represented as a list of node strings forming the loop,
    e.g. ``["a", "b", "c", "a"]`` where the last element repeats the first.
    Only the minimal entry-point cycle is recorded per DFS path.
    """
    visiting: list[str] = []          # current DFS stack (ordered)
    visiting_set: set[str] = set()    # fast lookup
    visited: set[str] = set()         # fully processed
    cycles: list[list[str]] = []
    seen_cycle_keys: set[frozenset[str]] = set()

    def dfs(node: str) -> None:
        if node in visiting_set:
            # extract the cycle starting from where `node` appears on the stack
            idx = visiting.index(node)
            cycle = visiting[idx:] + [node]
            key = frozenset(cycle)
            if key not in seen_cycle_keys:
                seen_cycle_keys.add(key)
                cycles.append(cycle)
            return
        if node in visited:
            return
        visiting.append(node)
        visiting_set.add(node)
        for nxt in sorted(edges.get(node, set())):
            dfs(nxt)
        visiting.pop()
        visiting_set.discard(node)
        visited.add(node)

    for node in sorted(edges.keys()):
        dfs(node)
    return cycles


def validate_forest_roots(
    forest: list[dict[str, Any]],
    mod_index: dict[str, Any],
) -> list[str]:
    """Return warnings for any forest root node whose destination mod is
    listed as a ``sub`` of another mod.

    In the mapping forest every top-level node is a *root* — the final
    destination of its changerequest chain.  Sub-mods are, by design,
    pure sources; they should never appear as the final destination of a
    chain.  A violation indicates a likely configuration error.

    Also emits ``W_GAMEBASE_NOT_ROOT`` when gamebase (numeric modid ``0``)
    does **not** appear among the root ``destin_mixed_id`` values *and* the
    forest is non-empty (acceptance check).
    """
    warnings: list[str] = []
    if not forest:
        return warnings

    # Build set of all mixed_ids that appear in someone's ``sub`` list.
    sub_mods: set[str] = set()
    for mod_obj in mod_index.values():
        for s in mod_obj.get("sub", []):
            if isinstance(s, str):
                sub_mods.add(s)

    # Collect root destin_mixed_ids from the forest.
    root_destins: set[str] = set()
    for node in forest:
        dmid = node.get("destin_mixed_id", "")
        if dmid:
            root_destins.add(dmid)

    # Sub-mod appearing as root → configuration error.
    for dmid in sorted(root_destins):
        if dmid in sub_mods:
            warnings.append(f"W_SUB_AS_ROOT: {dmid}")

    # Acceptance check: gamebase (modid == '0') should be in roots when
    # the forest is non-empty.
    has_gamebase = any(
        dmid.split(":", 1)[1] == "0"
        for dmid in root_destins
        if ":" in dmid
    )
    if not has_gamebase:
        warnings.append("W_GAMEBASE_NOT_ROOT: gamebase (modid 0) is absent from forest roots")

    return warnings


def compute_mapping(aggregated_rule_set: dict[str, Any], database: dict[str, Any], branch_decisions: dict[str, Any] | None = None) -> dict[str, Any]:
    branch_decisions = branch_decisions or {}

    # ── input structure validation ──────────────────────────────────────────────
    aggregated_rule_set_errors = validate_aggregated_rule_set(aggregated_rule_set)
    if aggregated_rule_set_errors:
        return {"warnings": [], "errors": aggregated_rule_set_errors, "forest": [], "final_mapping": []}

    database_errors = validate_database(database)
    if database_errors:
        return {"warnings": [], "errors": database_errors, "forest": [], "final_mapping": []}

    # ── branch_decisions schema check ──────────────────────────────────────────
    schema_errors = validate_branch_decisions_schema(branch_decisions)
    if schema_errors:
        return {"warnings": [], "errors": schema_errors, "forest": [], "final_mapping": []}
    warnings: list[str] = []
    errors: list[str] = []

    game_index = build_game_index(database)
    mods = [m for m in aggregated_rule_set.get("mod", []) if isinstance(m, dict)]
    mod_index = {m.get("mixed_id", ""): m for m in mods if isinstance(m.get("mixed_id"), str)}

    valid_actor_mods: set[str] = set()
    for mixed_id, mod_obj in mod_index.items():
        if not mixed_id or ":" not in mixed_id:
            warnings.append(f"W_INVALID_MIXED_ID: {mixed_id!r}")
            continue
        if not is_numeric_modid(mixed_id):
            root = mod_root_from_mixed_id(mixed_id, game_index)
            if not root or not Path(root).exists():
                warnings.append(f"W_LOCAL_MOD_MISSING: {mixed_id}")
                continue
        valid_actor_mods.add(mixed_id)

    clear_copy_dirs: dict[str, str] = {}
    mapping: dict[str, dict[str, Any]] = {}
    edges: dict[str, set[str]] = {}

    for actor_id, mod_obj in mod_index.items():
        if actor_id not in valid_actor_mods:
            continue
        def_destin = mod_obj.get("def_destin", "")
        def_action = mod_obj.get("def_action", "hold")
        actionlist = mod_obj.get("actionlist", [])
        source_root = mod_root_from_mixed_id(actor_id, game_index)
        if not source_root:
            warnings.append(f"W_MISSING_SOURCE_ROOT: {actor_id}")
            continue

        for idx, item in enumerate(actionlist):
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", def_action))
            destin = str(item.get("destin", def_destin))
            if action not in VALID_ACTIONS:
                warnings.append(f"W_INVALID_ACTION: {actor_id}#{idx}:{action}")
                continue
            if action == "hold":
                continue

            if _is_none_destin(destin):
                warnings.append(f"W_DESTIN_NONE_SKIPPED: {actor_id}#{idx}:action={action}:destin=none")
                continue

            if destin in mod_index and destin != actor_id:
                target_sub = mod_index[destin].get("sub", [])
                if actor_id not in target_sub:
                    warnings.append(f"W_SUB_NOT_RECOGNIZED: {actor_id} -> {destin}")
                    continue

            dest_root = mod_root_from_mixed_id(destin, game_index)
            if not dest_root:
                warnings.append(f"W_MISSING_DEST_ROOT: {actor_id}#{idx}:{destin}")
                continue

            into_list = item.get("into")
            if not isinstance(into_list, list) or not into_list:
                warnings.append(f"W_MISSING_INTO: {actor_id}#{idx}")
                continue

            if action == "clear_then_copy":
                # For clear_then_copy, use first into entry for key
                into_key = into_list[0] if into_list else ""
                key = _norm(str(Path(dest_root) / _norm(into_key)))
                prev = clear_copy_dirs.get(key)
                if prev and prev != actor_id:
                    errors.append(f"E_CLEAR_THEN_COPY_CONFLICT: {key}: {prev} vs {actor_id}")
                    continue
                clear_copy_dirs[key] = actor_id

            if action == "delete":
                # delete rules: iterate over into list, each entry is a deletion target
                # from/from_type are ignored for delete
                into_type = item.get("into_type", "path")
                for into_target in into_list:
                    target = _norm(str(Path(dest_root) / _norm(into_target)))
                    mapping.setdefault(target, {"path": target, "destin_mixed_id": destin, "changerequest": []})
                    mapping[target]["changerequest"].append(
                        _build_change_request(
                            path="!",
                            action="delete",
                            mixed_id=actor_id,
                            hashtype="sha256",
                            hashvalue="0",
                            item=item,
                        )
                    )
                continue

            # For non-delete actions, process from list
            from_list = item.get("from")
            if not isinstance(from_list, list) or not from_list:
                warnings.append(f"W_MISSING_FROM: {actor_id}#{idx}")
                continue

            nwname = item.get("nwname") if action == "rename_then_replace" else None
            if action == "rename_then_replace" and (not isinstance(nwname, str) or not nwname):
                warnings.append(f"W_MISSING_NWNAME: {actor_id}#{idx}")
                continue

            # Expand all sources from all from_list entries
            all_sources: list[str] = []
            from_type = item.get("from_type", "file")
            into_type = item.get("into_type", "path")
            for src_expr in from_list:
                sources = _expand_sources(source_root, src_expr, source_type=from_type)
                if not sources:
                    warnings.append(f"W_NO_SOURCE_MATCH: {actor_id}#{idx}:{src_expr}")
                else:
                    all_sources.extend(sources)
            
            if not all_sources:
                continue

            # For each into entry, process all sources
            for into_target in into_list:
                for src_file in all_sources:
                    target = _norm(
                        _target_for(
                            dest_root,
                            into_target,
                            src_file,
                            nwname if isinstance(nwname, str) else None,
                            from_type=from_type,
                            into_type=into_type,
                        )
                    )
                    if action == "create" and Path(target).exists():
                        warnings.append(f"W_CREATE_TARGET_EXISTS_OVERWRITE: {target}")

                    mapping.setdefault(target, {"path": target, "destin_mixed_id": destin, "changerequest": []})
                    mapping[target]["changerequest"].append(
                        _build_change_request(
                            path=_norm(src_file),
                            action=action,
                            mixed_id=actor_id,
                            hashtype="sha256",
                            hashvalue="",
                            item=item,
                        )
                    )
                    edges.setdefault(_norm(src_file), set()).add(target)

    for cycle in find_cycles(edges):
        chain = " -> ".join(cycle)
        errors.append(f"E_FILE_CIRCULAR_DEP: {chain}")

    # ── validate branch_decisions keys against actual branched targets ──────────
    branched_targets: set[str] = {
        t for t, n in mapping.items() if len(n["changerequest"]) > 1
    }
    for key in branch_decisions:
        if isinstance(key, str) and key not in branched_targets:
            warnings.append(f"W_BRANCH_DECISION_SUPERFLUOUS: {key}")

    unresolved_branch_paths: list[str] = []
    final_mapping: list[dict[str, Any]] = []
    forest: list[dict[str, Any]] = []

    for target, node in sorted(mapping.items(), key=lambda kv: kv[0]):
        requests = node["changerequest"]
        destin_mid = node.get("destin_mixed_id", "")
        if len(requests) <= 1:
            forest.append({"path": target, "destin_mixed_id": destin_mid, "changerequest": requests})
            continue

        ordered = sorted(requests, key=_sort_request_key)
        candidates = [r.get("path", "") for r in ordered]
        forest.append(
            {
                "path": target,
                "destin_mixed_id": destin_mid,
                "changerequest": ordered,
                "warning": "W_FOREST_BRANCHING",
                "candidates": candidates,
            }
        )

    for target in sorted(mapping.keys()):
        leaf_request = _resolve_effective_leaf_request(target, mapping, branch_decisions, errors)
        if leaf_request is None:
            unresolved_branch_paths.append(target)
            continue

        if leaf_request.get("action") == "delete" or leaf_request.get("path") == "!":
            promoted = dict(leaf_request)
            promoted["action"] = "delete"
            promoted["path"] = "!"
            warnings.append(f"W_DELETE_LEAF_PROMOTED: {target}")
            final_mapping.append({"path": target, "request": promoted})
            continue

        final_mapping.append({"path": target, "request": leaf_request})

    if unresolved_branch_paths:
        for p in sorted(set(unresolved_branch_paths)):
            if p in branched_targets:
                warnings.append(f"W_FOREST_BRANCHING_UNRESOLVED: {p}")

    if unresolved_branch_paths:
        final_mapping = []

    if errors:
        final_mapping = []

    warnings.extend(validate_forest_roots(forest, mod_index))

    return {
        "warnings": warnings,
        "errors": errors,
        "forest": forest,
        "final_mapping": final_mapping,
    }


__all__ = ["compute_mapping", "validate_branch_decisions_schema", "find_cycles", "validate_forest_roots", "_check_filefoldertree_transition"]
