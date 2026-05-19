from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from run import execute_mapping

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def _resolve_inputs(args: argparse.Namespace) -> tuple[str | None, str | None, str | None]:
    aggregated_rule_set = args.aggregated_rule_set or os.getenv("HMI_AGGREGATED_RULE_SET")
    database = args.database or os.getenv("HMI_DATABASE")
    decisions = args.decisions or os.getenv("HMI_DECISIONS")
    return aggregated_rule_set, database, decisions


def _validate_paths(
    aggregated_rule_set: str | None,
    database: str | None,
    decisions: str | None,
) -> list[str]:
    errors: list[str] = []
    if not aggregated_rule_set:
        errors.append("missing aggregated_rule_set path (--aggregated-rule-set or HMI_AGGREGATED_RULE_SET)")
    if not database:
        errors.append("missing database path (--database or HMI_DATABASE)")

    for label, value in (
        ("aggregated_rule_set", aggregated_rule_set),
        ("database", database),
        ("decisions", decisions),
    ):
        if value and not Path(value).exists():
            errors.append(f"{label} path not found: {value}")

    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke test for temporary cli-hmi wrapper")
    parser.add_argument("--aggregated-rule-set", help="Path to real aggregated_rule_set json")
    parser.add_argument("--database", help="Path to real database json")
    parser.add_argument("--decisions", help="Optional path to decisions json")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    aggregated_rule_set, database, decisions = _resolve_inputs(args)

    path_errors = _validate_paths(aggregated_rule_set, database, decisions)
    if path_errors:
        print(f"{RED}[FAILED]{RESET} " + "; ".join(path_errors))
        return 2

    code, result = execute_mapping(aggregated_rule_set, database, decisions_path=decisions)

    required_keys = {"warnings", "errors", "trees", "final_mapping"}
    missing = [k for k in sorted(required_keys) if k not in result]
    if missing:
        print(f"{RED}[FAILED]{RESET} result missing keys: {', '.join(missing)}")
        return 2

    if code == 0 and not result.get("errors"):
        final_count = len(result.get("final_mapping", []))
        print(f"{GREEN}[SUCCESS]{RESET} core flow executed, final_mapping_count={final_count}")
        return 0

    print(f"{RED}[FAILED]{RESET} errors={result.get('errors', [])}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
