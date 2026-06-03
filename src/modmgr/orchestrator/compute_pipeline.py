"""Compute pipeline — managed filter + compute."""

from __future__ import annotations

import copy
from typing import Any

from ..engine import compute_mapping
from ._common import ProgressCallback


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


# ── Compute ────────────────────────────────────────────────────────────


def compute(
    data: dict,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict:
    """Compute the file mapping from a pre-aggregated rule set dict.

    Pure computation — no I/O. Caller (dispatch) handles DataPort.fetch
    before and DataPort.push after.

    Args:
        data: DataPort.fetch() result with keys:
            - ``database``
            - ``aggregated_rule_set``
            - ``branch_decisions`` (optional)
            - ``managed_entries`` (optional)
        on_progress: Optional progress callback.

    Returns:
        A dict with keys:
        - ``mapping_result``: raw result from ``compute_mapping``
        - ``trees``: mapping trees
        - ``errors``: error list
        - ``warnings``: warning list
        - ``final_mapping``: resolved mapping list
    """
    database = data.get("database", {})
    aggregated_rule_set = data.get("aggregated_rule_set")
    branch_decisions = data.get("decisions", {}).get("branch_decisions")
    managed_entries = data.get("decisions", {}).get("managed_entries")

    # ── Validate rule input ────────────────────────────────────────────
    if not aggregated_rule_set:
        return {
            "mapping_result": {},
            "trees": [],
            "errors": ["E_NO_RULE_INPUT: aggregated_rule_set is required"],
            "warnings": [],
            "final_mapping": [],
        }

    agg_warnings: list[str] = []

    # ── Apply managed filter before computation ───────────────────────────
    filtered_database = _apply_managed_filter(database, managed_entries)

    # ── Computation phase ─────────────────────────────────────────────────
    if on_progress is not None:
        on_progress("compute", 0, 1, "Computing mapping...")

    mapping_result = compute_mapping(
        aggregated_rule_set=aggregated_rule_set,
        database=filtered_database,
        branch_decisions=branch_decisions or {},
    )

    if on_progress is not None:
        on_progress("compute", 1, 1, "Mapping computation complete")

    return {
        "mapping_result": mapping_result,
        "trees": mapping_result.get("trees", []),
        "errors": mapping_result.get("errors", []),
        "warnings": agg_warnings + mapping_result.get("warnings", []),
        "final_mapping": mapping_result.get("final_mapping", []),
    }
