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


VALID_ACTIONS = {"hold", "replace", "create", "delete"}


@dataclass
class RuleItem:
    actor_mixed_id: str
    destin_mixed_id: str
    action: str
    source_path: str | None
    into_path: str | None


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
    assert action != "hold", (
        f"E_INTERNAL: hold action must not appear in changerequest "
        f"(path={path!r}). This is a bug in the aggregator or engine pipeline."
    )
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
    nwname: str | None = None,
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


def compute_mapping(aggregated_rule_set: dict[str, Any], database: dict[str, Any], branch_decisions: dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute file mapping from an aggregated rule set.

    The input ``aggregated_rule_set`` uses the ``"operation"`` key (instead of
    ``"mod"``) and each action carries its own explicit ``action`` and ``destin``
    fields (inheritance has been resolved by the aggregator).  Permission checks
    (``sub``, ``game``) are the aggregator's responsibility and are no longer
    performed here.

    Args:
        aggregated_rule_set: The aggregated rule set produced by
            ``rule_aggregator.aggregate()``.
        database: The game database (for file-tree lookups and game index).
        branch_decisions: Optional explicit branch decisions for resolving
            multi-source targets.

    Returns:
        A dict with keys ``"warnings"``, ``"errors"``, ``"trees"``, and
        ``"final_mapping"``.
    """
    branch_decisions = branch_decisions or {}

    # ── input structure validation ──────────────────────────────────────────────
    aggregated_rule_set_errors = validate_aggregated_rule_set(aggregated_rule_set)
    if aggregated_rule_set_errors:
        return {"warnings": [], "errors": aggregated_rule_set_errors, "trees": [], "final_mapping": []}

    database_errors = validate_database(database)
    if database_errors:
        return {"warnings": [], "errors": database_errors, "trees": [], "final_mapping": []}

    # ── branch_decisions schema check ──────────────────────────────────────────
    schema_errors = validate_branch_decisions_schema(branch_decisions)
    if schema_errors:
        return {"warnings": [], "errors": schema_errors, "trees": [], "final_mapping": []}
    warnings: list[str] = []
    errors: list[str] = []

    game_index = build_game_index(database)
    operations = [m for m in aggregated_rule_set.get("operation", []) if isinstance(m, dict)]
    op_index = {m.get("mixed_id", ""): m for m in operations if isinstance(m.get("mixed_id"), str)}

    valid_actor_operations: set[str] = set()
    for mixed_id, op_obj in op_index.items():
        if not mixed_id or ":" not in mixed_id:
            warnings.append(f"W_INVALID_MIXED_ID: {mixed_id!r}")
            continue
        if not is_numeric_modid(mixed_id):
            root = mod_root_from_mixed_id(mixed_id, game_index)
            if not root or not Path(root).exists():
                warnings.append(f"W_LOCAL_MOD_MISSING: {mixed_id}")
                continue
        valid_actor_operations.add(mixed_id)

    mapping: dict[str, dict[str, Any]] = {}
    edges: dict[str, set[str]] = {}

    for actor_id, op_obj in op_index.items():
        if actor_id not in valid_actor_operations:
            continue
        actionlist = op_obj.get("actionlist", [])
        deleted_targets: set[str] = set()
        source_root = mod_root_from_mixed_id(actor_id, game_index)
        if not source_root:
            warnings.append(f"W_MISSING_SOURCE_ROOT: {actor_id}")
            continue

        for idx, item in enumerate(actionlist):
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", ""))
            destin = str(item.get("destin", ""))
            if action not in VALID_ACTIONS:
                warnings.append(f"W_INVALID_ACTION: {actor_id}#{idx}:{action}")
                continue
            if action == "hold":
                continue

            if _is_none_destin(destin):
                warnings.append(f"W_DESTIN_NONE_SKIPPED: {actor_id}#{idx}:action={action}:destin=none")
                continue

            dest_root = mod_root_from_mixed_id(destin, game_index)
            if not dest_root:
                warnings.append(f"W_MISSING_DEST_ROOT: {actor_id}#{idx}:{destin}")
                continue

            into_list = item.get("into")
            if not isinstance(into_list, list) or not into_list:
                warnings.append(f"W_MISSING_INTO: {actor_id}#{idx}")
                continue

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
                    deleted_targets.add(target)
                continue

            # For non-delete actions, process from list
            from_list = item.get("from")
            if not isinstance(from_list, list) or not from_list:
                warnings.append(f"W_MISSING_FROM: {actor_id}#{idx}")
                continue

            # Expand all sources from all from_list entries
            all_sources: list[str] = []
            from_type = item.get("from_type", "file")
            into_type = item.get("into_type", "path")
            for src_expr in from_list:
                sources = _expand_sources(source_root, src_expr, source_type=from_type)
                if not sources:
                    warnings.append(f"W_NO_SOURCE_MATCH: {actor_id}#{idx}:{src_expr} (resolved: {source_root}/{src_expr})")
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
                            None,
                            from_type=from_type,
                            into_type=into_type,
                        )
                    )
                    if action == "create" and Path(target).exists() and target not in deleted_targets:
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

    # ── same-mod dedup: within a single mixed_id's actionlist, later actions win ──
    for target, node in mapping.items():
        requests = node["changerequest"]
        if len(requests) <= 1:
            continue
        seen: dict[str, int] = {}
        deduped: list[dict[str, Any]] = []
        for req in requests:
            mid = req.get("mixed_id", "")
            if mid and mid in seen:
                # Replace previous entry from same mod — later action wins
                deduped[seen[mid]] = req
            else:
                if mid:
                    seen[mid] = len(deduped)
                deduped.append(req)
        node["changerequest"] = deduped

    # ── 构建 ForestTree 列表 ──
    trees = _build_forest_trees(mapping, edges)

    # ── 拓扑排序 ──
    sorted_trees = _topological_sort_by_refs(trees, warnings)

    # ── 验证 branch_decisions 的 key ──
    # branch_decisions 的 key 是 tree_root_path
    # 若 key 不在任何 tree 的 root_path 中 → W_BRANCH_DECISION_SUPERFLUOUS
    for key in branch_decisions:
        if isinstance(key, str) and key not in {t.root_path for t in sorted_trees}:
            warnings.append(f"W_BRANCH_DECISION_SUPERFLUOUS: {key}")

    # ── 从底向上解析 ──
    _resolve_trees_bottom_up(sorted_trees, branch_decisions, warnings, errors)

    # ── 构建输出（返回 trees + final_mapping）──
    return _build_output(sorted_trees, warnings, errors)


@dataclass
class ForestTree:
    """一棵独立根树。每棵树代表一个文件路径的操作集合。"""
    root_path: str
    destin_mixed_id: str
    changerequest: list[dict]
    refs: list[str]
    resolved: bool = False
    resolved_state: str | None = None


def _build_forest_trees(
    mapping: dict[str, dict],
    edges: dict[str, set[str]],
) -> list[ForestTree]:
    """从 mapping dict 构建 ForestTree 列表。

    每个 mapping 的 key 对应一棵树的 root_path。
    从 changerequest 中提取 refs：cr['path'] 若不在 mapping 中则不是引用。
    """
    trees: list[ForestTree] = []
    for target_path, node in sorted(mapping.items()):
        requests = node.get("changerequest", [])
        destin = node.get("destin_mixed_id", "")
        refs: list[str] = []
        for cr in requests:
            src = cr.get("path", "")
            if src and src != "!" and src in mapping:
                refs.append(src)
        refs = sorted(set(refs))
        trees.append(ForestTree(
            root_path=target_path,
            destin_mixed_id=destin,
            changerequest=requests,
            refs=refs,
        ))
    return trees


def _topological_sort_by_refs(
    trees: list[ForestTree],
    warnings: list[str],
) -> list[ForestTree]:
    """按引用关系拓扑排序：被引用者先于引用者。检测成环。

    若检测到环，发出 W_FOREST_CYCLE_DETECTED 警告并返回原列表。
    """
    tree_map = {t.root_path: t for t in trees}

    # 构建引用图（仅内部引用）
    ref_graph: dict[str, set[str]] = {}
    for t in trees:
        ref_graph[t.root_path] = {r for r in t.refs if r in tree_map}

    cycles = find_cycles(ref_graph)
    if cycles:
        for cycle in cycles:
            warnings.append(f"W_FOREST_CYCLE_DETECTED: {' -> '.join(cycle)}")
        return trees

    # Kahn 算法
    in_degree: dict[str, int] = {t.root_path: 0 for t in trees}
    dep_map: dict[str, list[str]] = {}  # ref → [dependers]

    for t in trees:
        for ref in t.refs:
            if ref not in tree_map:
                continue  # 外部引用，不影响拓扑序
            dep_map.setdefault(ref, []).append(t.root_path)
            in_degree[t.root_path] += 1

    queue = sorted(root for root, deg in in_degree.items() if deg == 0)
    sorted_paths: list[str] = []

    while queue:
        node = queue.pop(0)
        sorted_paths.append(node)
        for depender in dep_map.get(node, []):
            in_degree[depender] -= 1
            if in_degree[depender] == 0:
                queue.append(depender)
                queue.sort()

    if len(sorted_paths) != len(trees):
        return trees

    return [tree_map[p] for p in sorted_paths]


def _any_ancestor_deleted(path: str, tree_by_root: dict[str, ForestTree]) -> bool:
    """检查 *path* 的任一祖先目录是否对应一棵已删除的树。"""
    from pathlib import PurePosixPath
    p = PurePosixPath(path)
    for ancestor in p.parents:
        ancestor_str = str(ancestor)
        if ancestor_str in tree_by_root:
            if tree_by_root[ancestor_str].resolved_state == "deleted":
                return True
    return False


def _resolve_trees_bottom_up(
    trees: list[ForestTree],
    branch_decisions: dict[str, str],
    warnings: list[str],
    errors: list[str],
) -> None:
    """原地修改 trees，填充 resolved_state。

    按拓扑序处理每棵树：收集有效操作 → 应用用户决策 → 裁决。
    """
    tree_by_root: dict[str, ForestTree] = {t.root_path: t for t in trees}

    for tree in trees:
        if tree.resolved:
            continue

        # ── 收集有效操作 ──
        valid_requests: list[dict] = []
        for cr in tree.changerequest:
            src_path = cr.get("path", "")
            action = cr.get("action", "")

            # delete 操作永远有效（源是 "!"，不受其他树影响）
            if action == "delete":
                valid_requests.append(cr)
                continue

            # 非 delete 操作：检查源是否存在
            if src_path in tree_by_root:
                ref_tree = tree_by_root[src_path]
                if ref_tree.resolved_state == "deleted":
                    warnings.append(f"W_SOURCE_DELETED: {tree.root_path}: source {src_path} was deleted")
                    continue
                if ref_tree.resolved_state == "failed":
                    continue
            elif _any_ancestor_deleted(src_path, tree_by_root):
                warnings.append(f"W_SOURCE_DIRECTORY_DELETED: {src_path} (ancestor deleted)")
                continue

            valid_requests.append(cr)

        # ── 应用用户决策 ──
        user_decision = branch_decisions.get(tree.root_path)
        if user_decision is not None:
            if user_decision == "":
                tree.resolved_state = "skipped"
                tree.resolved = True
                continue
            if user_decision == "!":
                tree.resolved_state = "deleted"
                tree.resolved = True
                continue
            # 用户选了特定源路径
            chosen = next((cr for cr in valid_requests if cr.get("path") == user_decision), None)
            if chosen:
                valid_requests = [chosen]
            else:
                errors.append(f"E_BRANCH_DECISION_INVALID: {tree.root_path}: source {user_decision} not available")
                tree.resolved_state = "failed"
                tree.resolved = True
                continue

        # ── 裁决 ──
        if not valid_requests:
            tree.resolved_state = "failed"
            warnings.append(f"W_NO_VALID_OPERATION: {tree.root_path}: all sources unavailable")
        elif len(valid_requests) == 1:
            req = valid_requests[0]
            if req.get("action") == "delete":
                tree.resolved_state = "deleted"
            else:
                tree.resolved_state = "kept"
        else:
            tree.resolved_state = "pending"
            warnings.append(f"W_FOREST_BRANCHING: {tree.root_path}")

        tree.resolved = True


def _build_output(
    trees: list[ForestTree],
    warnings: list[str],
    errors: list[str],
) -> dict:
    """从解析后的 trees 构建最终输出 dict（含 trees 和 final_mapping）。"""

    # ── 检查是否有未决议的分岔 ──
    pending_trees = [t for t in trees if t.resolved_state == "pending"]
    if pending_trees:
        for t in pending_trees:
            warnings.append(f"W_FOREST_BRANCHING_UNRESOLVED: {t.root_path}")

    # ── 构建 trees 输出 ──
    trees_output: list[dict] = []
    for tree in trees:
        entry: dict = {
            "root_path": tree.root_path,
            "destin_mixed_id": tree.destin_mixed_id,
            "changerequest": tree.changerequest,
            "refs": tree.refs,
            "resolved_state": tree.resolved_state,
        }
        if tree.resolved_state == "pending":
            entry["warning"] = "W_FOREST_BRANCHING"
            entry["candidates"] = [cr.get("path", "") for cr in tree.changerequest]
        trees_output.append(entry)

    # ── 构建 final_mapping ──
    final_mapping: list[dict] = []
    for tree in trees:
        if tree.resolved_state in ("kept", "deleted"):
            if tree.resolved_state == "deleted":
                effective_request = {"path": "!", "action": "delete", "hashtype": "sha256", "hashvalue": "0"}
            else:
                effective_request = tree.changerequest[0]
            final_mapping.append({
                "path": tree.root_path,
                "request": effective_request,
            })

    if errors:
        final_mapping = []

    return {
        "warnings": warnings,
        "errors": errors,
        "trees": trees_output,
        "final_mapping": final_mapping,
    }


__all__ = [
    "ForestTree",
    "compute_mapping",
    "validate_branch_decisions_schema",
    "find_cycles",
    "_check_filefoldertree_transition",
]
