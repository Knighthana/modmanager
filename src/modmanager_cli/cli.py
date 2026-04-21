import argparse
import sys
from typing import Any

from .database_ops import (
    add_manual_steamlib,
    list_steamlibs,
    liveupdate_database,
    regen_database,
    remove_manual_steamlib,
    update_manual_steamlib,
)
from .engine import compute_mapping
from .iojson import dumps_pretty, load_json_file, write_json_file


def _emit_error(message: str) -> int:
    print(dumps_pretty({"errors": [message]}, ensure_ascii=False, indent=2), file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute file mapping forest and final mapping.")
    parser.add_argument("--config", required=True, help="Path to config json")
    parser.add_argument("--database", required=True, help="Path to database json")
    parser.add_argument("--decisions", help="Optional branch decision json")
    parser.add_argument("--out", help="Write result json to file; stdout if omitted")
    return parser


def build_db_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Database maintenance operations.")
    sub = parser.add_subparsers(dest="command", required=True)

    steamlib = sub.add_parser("steamlib", help="Manage steam libraries in database")
    steamlib_sub = steamlib.add_subparsers(dest="steamlib_command", required=True)

    steamlib_list = steamlib_sub.add_parser("list", help="List steam libraries")
    steamlib_list.add_argument("--database", required=True, help="Path to database json")
    steamlib_list.add_argument("--out", help="Write output json to file; stdout if omitted")

    steamlib_add = steamlib_sub.add_parser("add", help="Add one steam library")
    steamlib_add.add_argument("--database", required=True, help="Path to database json")
    steamlib_add.add_argument("--path", required=True, help="Steam library root or steamapps path")
    steamlib_add.add_argument(
        "--contains-libraryfolders-vdf",
        action="store_true",
        help="Mark this path as containing libraryfolders.vdf",
    )

    steamlib_remove = steamlib_sub.add_parser("remove", help="Remove one steam library")
    steamlib_remove.add_argument("--database", required=True, help="Path to database json")
    steamlib_remove.add_argument("--path", required=True, help="Steam library root or steamapps path")

    steamlib_update = steamlib_sub.add_parser("update", help="Update steam library path")
    steamlib_update.add_argument("--database", required=True, help="Path to database json")
    steamlib_update.add_argument("--old-path", required=True, help="Current steam library path")
    steamlib_update.add_argument("--new-path", required=True, help="New steam library path")

    liveupdate = sub.add_parser("liveupdate", help="Incremental update of game/dommod by steamlib")
    liveupdate.add_argument("--database", required=True, help="Path to database json")
    liveupdate.add_argument("--out", help="Write changes json to file; stdout if omitted")
    liveupdate.add_argument("--working-pathstyle", default="linux", choices=["linux", "windows"])
    liveupdate.add_argument("--greedy-parsing", action="store_true")

    regen = sub.add_parser("regen", help="Rebuild game/dommod from steamlib")
    regen.add_argument("--database", required=True, help="Path to database json")
    regen.add_argument("--out", help="Write result json to file; stdout if omitted")
    regen.add_argument("--working-pathstyle", default="linux", choices=["linux", "windows"])
    regen.add_argument("--greedy-parsing", action="store_true")

    return parser


def _print_or_write(payload: dict[str, Any], out_path: str | None) -> None:
    if out_path:
        write_json_file(out_path, payload, ensure_ascii=False, indent=2)
    else:
        print(dumps_pretty(payload, ensure_ascii=False, indent=2))


def _handle_steamlib(args: argparse.Namespace) -> int:
    try:
        database = load_json_file(args.database)
    except Exception as exc:
        return _emit_error(f"failed to load database: {exc}")

    if args.steamlib_command == "list":
        payload = {"steamlib": list_steamlibs(database), "errors": []}
        _print_or_write(payload, args.out)
        return 0

    if args.steamlib_command == "add":
        ok, message = add_manual_steamlib(
            database,
            path=args.path,
            contains_libraryfolders_vdf=args.contains_libraryfolders_vdf,
        )
    elif args.steamlib_command == "remove":
        ok, message = remove_manual_steamlib(database, path=args.path)
    else:
        ok, message = update_manual_steamlib(database, old_path=args.old_path, new_path=args.new_path)

    try:
        write_json_file(args.database, database, ensure_ascii=False, indent=2)
    except Exception as exc:
        return _emit_error(f"failed to write database: {exc}")
    payload = {"ok": ok, "message": message, "steamlib": list_steamlibs(database), "errors": []}
    _print_or_write(payload, None)
    return 0 if ok else 2


def _handle_liveupdate(args: argparse.Namespace) -> int:
    try:
        database = load_json_file(args.database)
    except Exception as exc:
        return _emit_error(f"failed to load database: {exc}")

    try:
        result = liveupdate_database(
            database,
            working_pathstyle=args.working_pathstyle,
            greedy_parsing=args.greedy_parsing,
        )
    except Exception as exc:
        return _emit_error(f"liveupdate failed: {exc}")

    updated = result.get("updated_database", database)
    try:
        write_json_file(args.database, updated, ensure_ascii=False, indent=2)
    except Exception as exc:
        return _emit_error(f"failed to write database: {exc}")

    _print_or_write(result, args.out)
    return 0 if not result.get("errors") else 2


def _handle_regen(args: argparse.Namespace) -> int:
    try:
        database = load_json_file(args.database)
    except Exception as exc:
        return _emit_error(f"failed to load database: {exc}")

    try:
        result = regen_database(
            database,
            working_pathstyle=args.working_pathstyle,
            greedy_parsing=args.greedy_parsing,
        )
    except Exception as exc:
        return _emit_error(f"regen failed: {exc}")

    rebuilt = result.get("database", database)
    try:
        write_json_file(args.database, rebuilt, ensure_ascii=False, indent=2)
    except Exception as exc:
        return _emit_error(f"failed to write database: {exc}")

    _print_or_write(result, args.out)
    return 0 if not result.get("errors") else 2


def run_db_cli(argv: list[str]) -> int:
    parser = build_db_parser()
    args = parser.parse_args(argv)

    if args.command == "steamlib":
        return _handle_steamlib(args)
    if args.command == "liveupdate":
        return _handle_liveupdate(args)
    if args.command == "regen":
        return _handle_regen(args)

    return 2


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] in {"steamlib", "liveupdate", "regen"}:
        return run_db_cli(argv)

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_json_file(args.config)
        database = load_json_file(args.database)
        decisions = {}
        if args.decisions:
            decisions = load_json_file(args.decisions)
    except Exception as exc:
        return _emit_error(f"failed to load inputs: {exc}")

    try:
        result = compute_mapping(config=config, database=database, branch_decisions=decisions)
    except Exception as exc:
        return _emit_error(f"compute_mapping failed: {exc}")

    payload = dumps_pretty(result, ensure_ascii=False, indent=2)

    if args.out:
        try:
            write_json_file(args.out, result, ensure_ascii=False, indent=2)
        except Exception as exc:
            return _emit_error(f"failed to write output: {exc}")
    else:
        print(payload)

    return 0 if not result.get("errors", []) else 2


if __name__ == "__main__":
    raise SystemExit(main())
