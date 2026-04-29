import argparse
import sys
from pathlib import Path
from typing import Any

from .backup_ops import (
    apply_final_mapping,
    delete_orphan_files,
    detect_dirty_state,
    restore_from_backup,
    run_differential_backup,
)
from .database_ops import (
    add_manual_steamlib,
    list_steamlibs,
    liveupdate_database,
    regen_database,
    remove_manual_steamlib,
    update_manual_steamlib,
)
from .engine import compute_mapping
from .forest_visual import VisualizationError, visualize_payload
from .iojson import dumps_pretty, load_json_file, write_json_file


def _emit_error(message: str) -> int:
    return _emit_error_with_code(message, 2)


def _emit_error_with_code(message: str, code: int) -> int:
    print(dumps_pretty({"errors": [message]}, ensure_ascii=False, indent=2), file=sys.stderr)
    return code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute file mapping forest and final mapping.")
    parser.add_argument("--aggregated-rule-set", required=True, help="Path to aggregated_rule_set json")
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

    backup = sub.add_parser("backup", help="Back up target files before applying a mapping")
    backup.add_argument("--aggregated-rule-set", required=True, help="Path to aggregated_rule_set json")
    backup.add_argument("--database", required=True, help="Path to database json")
    backup.add_argument("--backup-dir", required=True, help="Directory to store backup")
    backup.add_argument("--decisions", help="Optional branch decisions json")
    backup.add_argument("--out", help="Write result json to file; stdout if omitted")

    apply_cmd = sub.add_parser("apply", help="Apply final mapping to disk (backup gate required)")
    apply_cmd.add_argument("--aggregated-rule-set", required=True, help="Path to aggregated_rule_set json")
    apply_cmd.add_argument("--database", required=True, help="Path to database json")
    apply_cmd.add_argument("--backup-dir", required=True, help="Path to existing backup directory")
    apply_cmd.add_argument("--decisions", help="Optional branch decisions json")
    apply_cmd.add_argument("--dry-run", action="store_true", help="Check gate but do not touch files")
    apply_cmd.add_argument("--out", help="Write result json to file; stdout if omitted")

    restore = sub.add_parser("restore", help="Restore files from a backup directory")
    restore.add_argument("--backup-dir", required=True, help="Path to backup directory")
    restore.add_argument("--files", nargs="*", help="Specific files to restore (default: all)")
    restore.add_argument(
        "--delete-orphans",
        action="store_true",
        help="Delete reported orphan files after restore",
    )
    restore.add_argument("--out", help="Write result json to file; stdout if omitted")

    return parser


def build_visualize_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render forest JSON to ascii/dot/svg/html.")
    parser.add_argument("--forest", required=True, help="Path to forest json or compute result json")
    parser.add_argument("--format", default="ascii", help="ascii | dot | svg | html")
    parser.add_argument(
        "--show-m1-details",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show action_order/provenance_ref/sidecar_ref details in output (default: enabled)",
    )
    parser.add_argument("--out", help="Write rendered output to file; stdout if omitted")
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


def _handle_backup(args: argparse.Namespace) -> int:
    try:
        aggregated_rule_set = load_json_file(args.aggregated_rule_set)
        database = load_json_file(args.database)
        decisions = load_json_file(args.decisions) if args.decisions else {}
    except Exception as exc:
        return _emit_error(f"failed to load inputs: {exc}")

    try:
        mapping_result = compute_mapping(
            aggregated_rule_set=aggregated_rule_set,
            database=database,
            branch_decisions=decisions,
        )
    except Exception as exc:
        return _emit_error(f"compute_mapping failed: {exc}")

    if mapping_result.get("errors"):
        return _emit_error(f"mapping has errors: {mapping_result['errors']}")

    final_mapping = mapping_result.get("final_mapping", [])
    if not final_mapping:
        return _emit_error("no final_mapping produced; resolve branch conflicts first")

    files_to_backup = [entry["path"] for entry in final_mapping if entry.get("path")]
    try:
        result = run_differential_backup(args.backup_dir, files_to_backup)
    except Exception as exc:
        return _emit_error(f"backup failed: {exc}")

    _print_or_write(result, args.out)
    return 0 if result.get("ok") else 2


def _handle_apply(args: argparse.Namespace) -> int:
    try:
        aggregated_rule_set = load_json_file(args.aggregated_rule_set)
        database = load_json_file(args.database)
        decisions = load_json_file(args.decisions) if args.decisions else {}
    except Exception as exc:
        return _emit_error(f"failed to load inputs: {exc}")

    try:
        mapping_result = compute_mapping(
            aggregated_rule_set=aggregated_rule_set,
            database=database,
            branch_decisions=decisions,
        )
    except Exception as exc:
        return _emit_error(f"compute_mapping failed: {exc}")

    if mapping_result.get("errors"):
        return _emit_error(f"mapping has errors: {mapping_result['errors']}")

    final_mapping = mapping_result.get("final_mapping", [])
    if not final_mapping:
        return _emit_error("no final_mapping produced; resolve branch conflicts first")

    try:
        result = apply_final_mapping(final_mapping, args.backup_dir, dry_run=args.dry_run)
    except Exception as exc:
        return _emit_error(f"apply failed: {exc}")

    _print_or_write(result, args.out)
    return 0 if result.get("ok") else 2


def _handle_restore(args: argparse.Namespace) -> int:
    target_files = args.files or None
    dirty = detect_dirty_state(args.backup_dir)
    try:
        result = restore_from_backup(args.backup_dir, target_files)
    except Exception as exc:
        return _emit_error(f"restore failed: {exc}")

    if dirty.get("dirty"):
        warnings = list(result.get("warnings", []))
        warnings.extend(dirty.get("errors", []))
        result["warnings"] = warnings
        result["dirty_state"] = {
            "dirty": True,
            "partial_files": dirty.get("partial_files", []),
        }

    if args.delete_orphans and result.get("orphans"):
        delete_result = delete_orphan_files(result["orphans"])
        result["orphan_deletion"] = delete_result
        if not delete_result.get("ok", False):
            result["ok"] = False
            result_errors = list(result.get("errors", []))
            result_errors.extend(delete_result.get("errors", []))
            result["errors"] = result_errors

    _print_or_write(result, args.out)
    return 0 if result.get("ok") else 2


def _handle_visualize(args: argparse.Namespace) -> int:
    try:
        payload = load_json_file(args.forest)
    except Exception as exc:
        return _emit_error_with_code(f"failed to load forest input: {exc}", 2)

    try:
        rendered = visualize_payload(payload, args.format, show_m1_details=args.show_m1_details)
    except VisualizationError as exc:
        return _emit_error_with_code(str(exc), exc.code)
    except Exception as exc:
        return _emit_error_with_code(f"visualization failed: {exc}", 5)

    if args.out:
        try:
            Path(args.out).write_text(rendered, encoding="utf-8")
        except Exception as exc:
            return _emit_error_with_code(f"failed to write visualization output: {exc}", 6)
    else:
        print(rendered)
    return 0


def run_db_cli(argv: list[str]) -> int:
    parser = build_db_parser()
    args = parser.parse_args(argv)

    if args.command == "steamlib":
        return _handle_steamlib(args)
    if args.command == "liveupdate":
        return _handle_liveupdate(args)
    if args.command == "regen":
        return _handle_regen(args)
    if args.command == "backup":
        return _handle_backup(args)
    if args.command == "apply":
        return _handle_apply(args)
    if args.command == "restore":
        return _handle_restore(args)

    return 2


def main() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "visualize":
        parser = build_visualize_parser()
        args = parser.parse_args(argv[1:])
        return _handle_visualize(args)

    if argv and argv[0] in {"steamlib", "liveupdate", "regen", "backup", "apply", "restore"}:
        return run_db_cli(argv)

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        aggregated_rule_set = load_json_file(args.aggregated_rule_set)
        database = load_json_file(args.database)
        decisions = {}
        if args.decisions:
            decisions = load_json_file(args.decisions)
    except Exception as exc:
        return _emit_error(f"failed to load inputs: {exc}")

    try:
        result = compute_mapping(
            aggregated_rule_set=aggregated_rule_set,
            database=database,
            branch_decisions=decisions,
        )
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
