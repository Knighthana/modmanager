import argparse

from .engine import compute_mapping
from .iojson import dumps_pretty, load_json_file, write_json_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute file mapping forest and final mapping.")
    parser.add_argument("--config", required=True, help="Path to config json")
    parser.add_argument("--database", required=True, help="Path to database json")
    parser.add_argument("--decisions", help="Optional branch decision json")
    parser.add_argument("--out", help="Write result json to file; stdout if omitted")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = load_json_file(args.config)
    database = load_json_file(args.database)
    decisions = {}
    if args.decisions:
        decisions = load_json_file(args.decisions)

    result = compute_mapping(config=config, database=database, branch_decisions=decisions)
    payload = dumps_pretty(result, ensure_ascii=False, indent=2)

    if args.out:
        write_json_file(args.out, result, ensure_ascii=False, indent=2)
    else:
        print(payload)

    return 0 if not result["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
