from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _load_core_modules():
    try:
        from modmanager_cli.iojson import load_json_file
        from modmanager_cli.validation import validate_aggregated_rule_set
    except ModuleNotFoundError:
        import sys

        repo_root = Path(__file__).resolve().parents[1]
        src_dir = repo_root / "src"
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
        from modmanager_cli.iojson import load_json_file
        from modmanager_cli.validation import validate_aggregated_rule_set

    return load_json_file, validate_aggregated_rule_set


def _collapse_slashes(path: str) -> str:
    return re.sub(r"/+", "/", path.replace("\\", "/").strip())


def _normalize_path_values(values: Any, path_type: str) -> Any:
    if not isinstance(values, list):
        return values

    normalized: list[Any] = []
    for item in values:
        if not isinstance(item, str):
            normalized.append(item)
            continue
        val = _collapse_slashes(item)
        if path_type == "path" and val and not val.endswith("/"):
            val = f"{val}/"
        normalized.append(val)
    return normalized


def _normalize_action_item(item: dict[str, Any], rule_file_abs_path: str) -> dict[str, Any]:
    normalized = dict(item)

    action_order = normalized.get("action_order", 0)
    if not isinstance(action_order, int):
        action_order = 0
    normalized["action_order"] = action_order

    provenance_ref = normalized.get("provenance_ref", "404")
    if not isinstance(provenance_ref, str) or not provenance_ref.strip():
        provenance_ref = "404"
    if provenance_ref == "404":
        provenance_ref = rule_file_abs_path
    normalized["provenance_ref"] = provenance_ref

    sidecar_ref = normalized.get("sidecar_ref", "404")
    if not isinstance(sidecar_ref, str) or not sidecar_ref.strip():
        sidecar_ref = "404"
    if sidecar_ref == "404":
        sidecar_ref = "undesignated"
    normalized["sidecar_ref"] = sidecar_ref

    from_type = normalized.get("from_type")
    into_type = normalized.get("into_type")
    normalized["from"] = _normalize_path_values(normalized.get("from"), from_type if isinstance(from_type, str) else "")
    normalized["into"] = _normalize_path_values(normalized.get("into"), into_type if isinstance(into_type, str) else "")

    return normalized


def aggregate_single_kmm_rule_file(kmm_rule_path: str) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Convert one kmm_rule file into an aggregated_rule_set-compatible object.

    Returns: (aggregated_rule_set_or_none, errors, warnings)
    """

    load_json_file, validate_aggregated_rule_set = _load_core_modules()

    warnings: list[str] = []
    errors: list[str] = []

    try:
        payload = load_json_file(kmm_rule_path)
    except Exception as exc:
        return None, [f"E_KMM_RULE_LOAD_FAILED: {exc}"], warnings

    if not isinstance(payload, dict):
        return None, ["E_KMM_RULE_INVALID: root must be object"], warnings

    mods = payload.get("mod")
    if not isinstance(mods, list):
        return None, ["E_KMM_RULE_INVALID: missing or invalid mod list"], warnings

    rule_file_abs_path = str(Path(kmm_rule_path).resolve())

    aggregated_mods: list[dict[str, Any]] = []
    for idx, mod in enumerate(mods):
        if not isinstance(mod, dict):
            errors.append(f"E_KMM_RULE_INVALID: mod[{idx}] must be object")
            continue

        normalized_mod = dict(mod)
        actionlist = normalized_mod.get("actionlist", [])
        if not isinstance(actionlist, list):
            errors.append(f"E_KMM_RULE_INVALID: mod[{idx}].actionlist must be list")
            continue

        normalized_actions: list[dict[str, Any]] = []
        for aidx, action_item in enumerate(actionlist):
            if not isinstance(action_item, dict):
                errors.append(f"E_KMM_RULE_INVALID: mod[{idx}].actionlist[{aidx}] must be object")
                continue

            normalized_action = _normalize_action_item(action_item, rule_file_abs_path)
            if normalized_action.get("provenance_ref") == rule_file_abs_path:
                warnings.append(f"W_PROVENANCE_REF_DEFAULTED: mod[{idx}].actionlist[{aidx}]")
            if normalized_action.get("sidecar_ref") == "undesignated":
                warnings.append(f"W_SIDECAR_REF_DEFAULTED: mod[{idx}].actionlist[{aidx}]")
            if action_item.get("action_order") != normalized_action.get("action_order"):
                warnings.append(f"W_ACTION_ORDER_DEFAULTED: mod[{idx}].actionlist[{aidx}]")
            normalized_actions.append(normalized_action)

        normalized_mod["actionlist"] = normalized_actions
        aggregated_mods.append(normalized_mod)

    if errors:
        return None, errors, warnings

    aggregated_rule_set = {
        "mod": aggregated_mods,
    }

    validation_errors = validate_aggregated_rule_set(aggregated_rule_set)
    if validation_errors:
        return None, validation_errors, warnings

    return aggregated_rule_set, errors, warnings


__all__ = ["aggregate_single_kmm_rule_file"]
