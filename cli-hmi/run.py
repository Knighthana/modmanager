from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from rule_aggregator import aggregate_single_kmm_rule_file


_DEFAULT_KMM_RULE = "description/kmm_rule_RWR-khn_CT-castears-z2414_Replace.json.example"


def _load_core_modules():
    """Load core modules with a local src fallback for demo usage."""
    try:
        from modmanager.engine import compute_mapping
        from modmanager.iojson import dumps_pretty, load_json_file, write_json_file
    except ModuleNotFoundError:
        repo_root = Path(__file__).resolve().parents[1]
        src_dir = repo_root / "src"
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)
        from modmanager.engine import compute_mapping
        from modmanager.iojson import dumps_pretty, load_json_file, write_json_file

    return compute_mapping, load_json_file, write_json_file, dumps_pretty


def _prompt_path(label: str, default: str | None = None, optional: bool = False) -> str | None:
    while True:
        suffix = f" [{default}]" if default else ""
        raw = input(f"{label}{suffix}: ").strip()
        if not raw:
            raw = default or ""
        if raw:
            return raw
        if optional:
            return None
        print("Input required.")


def execute_mapping(
    database_path: str,
    aggregated_rule_set_path: str | None = None,
    kmm_rule_path: str | None = None,
    decisions_path: str | None = None,
    out_path: str | None = None,
) -> tuple[int, dict[str, Any]]:
    compute_mapping, load_json_file, write_json_file, dumps_pretty = _load_core_modules()

    if bool(aggregated_rule_set_path) == bool(kmm_rule_path):
        payload = {"errors": ["provide exactly one of --aggregated-rule-set or --kmm-rule"]}
        return 2, payload

    try:
        if kmm_rule_path:
            aggregated_rule_set, agg_errors, agg_warnings = aggregate_single_kmm_rule_file(kmm_rule_path)
            if agg_errors:
                return 2, {"errors": agg_errors, "warnings": agg_warnings}
            if aggregated_rule_set is None:
                return 2, {"errors": ["aggregation failed with unknown reason"]}
        else:
            aggregated_rule_set = load_json_file(aggregated_rule_set_path)
            agg_warnings = []

        database = load_json_file(database_path)
        decisions = load_json_file(decisions_path) if decisions_path else {}
    except Exception as exc:
        payload = {"errors": [f"failed to load inputs: {exc}"]}
        return 2, payload

    try:
        result = compute_mapping(
            aggregated_rule_set=aggregated_rule_set,
            database=database,
            branch_decisions=decisions,
        )
    except Exception as exc:
        payload = {"errors": [f"compute_mapping failed: {exc}"]}
        return 2, payload

    warnings = list(result.get("warnings", []))
    warnings.extend(agg_warnings)
    result["warnings"] = warnings

    # Keep output concise for HMI usage.
    summary = {
        "warnings_count": len(result.get("warnings", [])),
        "errors_count": len(result.get("errors", [])),
        "forest_count": len(result.get("trees", [])),
        "final_mapping_count": len(result.get("final_mapping", [])),
    }
    result["summary"] = summary

    if out_path:
        try:
            write_json_file(out_path, result, ensure_ascii=False, indent=2)
        except Exception as exc:
            payload = {"errors": [f"failed to write output: {exc}"]}
            return 2, payload
    else:
        print(dumps_pretty(result, ensure_ascii=False, indent=2))

    return (0 if not result.get("errors") else 2), result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Temporary HMI wrapper for M1 compute_mapping")
    parser.add_argument("--aggregated-rule-set", help="Path to aggregated_rule_set json")
    parser.add_argument("--kmm-rule", help="Path to one kmm_rule json file (MVP: single file)")
    parser.add_argument("--database", help="Path to database json")
    parser.add_argument("--decisions", help="Optional path to branch decisions json")
    parser.add_argument("--out", help="Optional output json path")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for missing inputs interactively",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    aggregated_rule_set_path = args.aggregated_rule_set
    kmm_rule_path = args.kmm_rule
    database_path = args.database
    decisions_path = args.decisions

    need_prompt = args.interactive or not database_path or (not aggregated_rule_set_path and not kmm_rule_path)
    if need_prompt:
        kmm_rule_path = kmm_rule_path or _prompt_path("kmm_rule path (optional)", default=_DEFAULT_KMM_RULE, optional=True)
        if not kmm_rule_path:
            aggregated_rule_set_path = aggregated_rule_set_path or _prompt_path("aggregated_rule_set path")
        database_path = database_path or _prompt_path("database path")
        if decisions_path is None:
            decisions_path = _prompt_path("decisions path (optional)", optional=True)

    if not database_path or (not aggregated_rule_set_path and not kmm_rule_path):
        print(
            json.dumps(
                {"errors": ["--database and one of --aggregated-rule-set/--kmm-rule are required"]},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    if aggregated_rule_set_path and kmm_rule_path:
        print(
            json.dumps(
                {"errors": ["--aggregated-rule-set and --kmm-rule cannot be used together"]},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    code, payload = execute_mapping(
        aggregated_rule_set_path=aggregated_rule_set_path,
        kmm_rule_path=kmm_rule_path,
        database_path=database_path,
        decisions_path=decisions_path,
        out_path=args.out,
    )

    if code != 0:
        print(json.dumps({"errors": payload.get("errors", ["unknown error"])}, ensure_ascii=False), file=sys.stderr)

    return code


if __name__ == "__main__":
    raise SystemExit(main())
