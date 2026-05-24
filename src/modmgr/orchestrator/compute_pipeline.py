"""Compute pipeline — managed filter + compute + compute_ws."""

from __future__ import annotations

import copy
from typing import Any

from ..bootstrap import discover_user_config
from ..engine import compute_mapping
from ._common import (
    PipelineResult,
    ProgressCallback,
    _get_workspace_manager,
    _resolve_database,
    _sha256_dict,
    _utcnow,
)


# ── Managed entries filter ────────────────────────────────────────────


def _apply_managed_filter(
    database: dict[str, Any],
    managed_entries: dict[str, dict[str, list[str]]] | None,
) -> dict[str, Any]:
    """用 managed_entries 过滤 database 中的条目.

    Args:
        database: 完整 database 结构（含 game[], mod[]）
        managed_entries: 可选，{ "game": { appid: [路径列表] }, "mod": { mixed_id: [路径列表] } }

    Returns:
        过滤后的 database 深拷贝。若 managed_entries 为 None，返回原 database 的深拷贝.

    规则：
    - 对 game[]：若 managed_entries.game[appid] 存在 → 仅保留 basepath 在列表中的条目
    - 对 mod[]：若 managed_entries.mod[mixed_id] 存在 → 仅保留 path 在列表中的条目
    - 不在 managed_entries 中的 appid/mixed_id → 全部保留
    - 若 managed_entries 为 None → 返回 database 的深拷贝
    """
    if managed_entries is None:
        return copy.deepcopy(database)

    result = copy.deepcopy(database)

    # ── Filter games ───────────────────────────────────────────────────────
    game_filter = managed_entries.get("game", {})
    if game_filter:
        filtered_games = []
        for g in result.get("game", []):
            appid_str = str(g.get("appid", ""))
            if appid_str in game_filter:
                # Only keep if basepath is in the allowed list
                if g.get("basepath") in game_filter[appid_str]:
                    filtered_games.append(g)
            else:
                # Not in managed_entries → keep all entries for this appid
                filtered_games.append(g)
        result["game"] = filtered_games

    # ── Filter mods ────────────────────────────────────────────────────────
    mod_filter = managed_entries.get("mod", {})
    if mod_filter:
        filtered_mods = []
        for m in result.get("mod", []):
            mixed_id = str(m.get("mixed_id", ""))
            if mixed_id in mod_filter:
                # Only keep if path is in the allowed list
                if m.get("path") in mod_filter[mixed_id]:
                    filtered_mods.append(m)
            else:
                # Not in managed_entries → keep all entries for this mixed_id
                filtered_mods.append(m)
        result["mod"] = filtered_mods

    return result


# ── Phase helpers ─────────────────────────────────────────────────────


def compute(
    database: dict,
    *,
    aggregated_rule_set: dict | None = None,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    managed_entries: dict | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Compute the file mapping from a pre-aggregated rule set dict.

    Args:
        database: Game database dict.
        aggregated_rule_set: Pre-aggregated rule set dict. When ``None``,
            returns an error.
        action_orders: Optional ``{mixed_id: int}`` overrides.
        branch_decisions: Optional explicit branch decisions.
        managed_entries: Optional dict to filter database entries before
            computing. Format: ``{"game": {appid: [basepaths]}, "mod": {mixed_id: [paths]}}``.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.  ``backup_result`` and ``apply_result`` are
        always ``None`` from this function.
    """
    # ── Validate rule input ────────────────────────────────────────────
    if not aggregated_rule_set:
        return PipelineResult(
            ok=False,
            errors=["E_NO_RULE_INPUT: aggregated_rule_set is required"],
        )
    aggregated = aggregated_rule_set
    agg_errors: list[str] = []
    agg_warnings: list[str] = []

    # ── Apply managed filter before computation ───────────────────────────
    filtered_database = _apply_managed_filter(database, managed_entries)

    # ── Computation phase ─────────────────────────────────────────────────
    if on_progress is not None:
        on_progress("compute", 0, 1, "Computing mapping...")

    mapping_result = compute_mapping(
        aggregated_rule_set=aggregated,
        database=filtered_database,
        branch_decisions=branch_decisions or {},
    )

    if on_progress is not None:
        on_progress("compute", 1, 1, "Mapping computation complete")

    return PipelineResult(
        ok=not mapping_result.get("errors"),
        errors=mapping_result.get("errors", []),
        warnings=agg_warnings + mapping_result.get("warnings", []),
        trees=mapping_result.get("trees", []),
        final_mapping=mapping_result.get("final_mapping", []),
        mapping_result=mapping_result,
    )


# ── Workspace-aware entry points ──────────────────────────────────────


def compute_ws(
    workspace_id: str,
    *,
    config_index: str,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Compute mapping in a workspace context.

    Reads ``aggregated_rule.json`` and ``decisions.json`` from the
    workspace, resolves the bound database, and computes the mapping.
    Results (mapping + SVG + fingerprints) are written back to the
    workspace directory.

    Args:
        workspace_id: Target workspace identifier.
        config_index: Path to user_config.json.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.  ``backup_result`` and ``apply_result`` are
        always ``None`` from this function.
    """
    user_config, _ = discover_user_config(config_index=config_index)
    wm = _get_workspace_manager(user_config)

    if not wm.exists(workspace_id):
        return PipelineResult(
            ok=False,
            errors=[f"workspace '{workspace_id}' not found"],
        )

    # ── Load workspace context ────────────────────────────────────────
    meta = wm.read_meta(workspace_id)
    database_name = meta["database_name"]

    if not wm.has_aggregated_rule(workspace_id):
        return PipelineResult(
            ok=False,
            errors=["no aggregated rule set in workspace — aggregate rules first"],
        )
    aggregated_rule_set = wm.read_aggregated_rule(workspace_id)

    decisions = (
        wm.read_decisions(workspace_id) if wm.has_decisions(workspace_id) else {}
    )

    # ── Resolve and load database ─────────────────────────────────────
    try:
        database = _resolve_database(database_name, user_config)
    except Exception as exc:
        return PipelineResult(ok=False, errors=[str(exc)])

    # ── Compute ───────────────────────────────────────────────────────
    result = compute(
        database=database,
        aggregated_rule_set=aggregated_rule_set,
        branch_decisions=decisions.get("branch_decisions"),
        managed_entries=decisions.get("managed_entries"),
        on_progress=on_progress,
    )

    if not result.ok:
        return result

    # ── Write results back to workspace ───────────────────────────────
    wm.write_mapping(workspace_id, result.mapping_result)

    # Compute and write data fingerprints for cache invalidation
    fingerprints = {
        "schema_namespace": "KMM_WorkspaceFingerprints",
        "schema_version": "knighthana@0.1.0",
        "kmmrule": _sha256_dict(aggregated_rule_set),
        "database": _sha256_dict(database),
        "computed_at": _utcnow(),
    }
    wm.write_fingerprints(workspace_id, fingerprints)

    # Generate and write SVG
    if result.trees:
        try:
            from ..forest_visual import visualize_payload

            svg = visualize_payload({"trees": result.trees}, "svg")
            wm.write_svg(workspace_id, svg)
        except Exception:
            pass  # SVG generation is non-critical

    return result
