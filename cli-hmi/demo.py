#!/usr/bin/env python3
"""Interactive demo orchestrator: aggregate → first-pass mapping → forest viz
→ branch-decision UI → second-pass mapping → final forest + final_mapping viz."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Import helpers (with src/ fallback for direct execution without PYTHONPATH)
# ---------------------------------------------------------------------------

def _ensure_src_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    src_str = str(src_dir)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)

    # Also ensure cli-hmi is importable (for rule_aggregator)
    hmi_dir = str(Path(__file__).resolve().parent)
    if hmi_dir not in sys.path:
        sys.path.insert(0, hmi_dir)


def _load_modules():
    _ensure_src_on_path()
    from modmanager.engine import compute_mapping
    from modmanager.forest_visual import visualize_payload
    from modmanager.iojson import load_json_file, write_json_file
    from rule_aggregator import aggregate_single_kmm_rule_file
    return compute_mapping, visualize_payload, load_json_file, write_json_file, aggregate_single_kmm_rule_file


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_KMM_RULE = str(
    _REPO_ROOT / "description" / "kmm_rule_RWR-khn_CT-castears-z2414_Replace.json.example"
)
_DEFAULT_DATABASE = str(_REPO_ROOT / "description" / "database.json.example")
_REPORTS_DIR = Path(__file__).resolve().parent / "reports"

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_RESET = "\033[0m"
_BOLD = "\033[1m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_GREEN = "\033[32m"
_RED = "\033[31m"
_DIM = "\033[2m"


def _c(text: str, *codes: str) -> str:
    return "".join(codes) + text + _RESET


def _hr(char: str = "─", width: int = 72) -> None:
    print(_c(char * width, _DIM))


def _section(title: str) -> None:
    _hr()
    print(_c(f"  {title}", _BOLD, _CYAN))
    _hr()


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def _print_summary(label: str, result: dict[str, Any]) -> None:
    errs = result.get("errors", [])
    warns = result.get("warnings", [])
    forest = result.get("trees", [])
    fm = result.get("final_mapping", [])

    print(f"\n{_c(label, _BOLD)}")
    print(f"  Forest nodes  : {_c(str(len(forest)), _CYAN)}")
    print(f"  Final mapping : {_c(str(len(fm)), _GREEN if fm else _YELLOW)}")
    print(f"  Warnings      : {_c(str(len(warns)), _YELLOW if warns else _DIM)}")
    print(f"  Errors        : {_c(str(len(errs)), _RED if errs else _DIM)}")
    if errs:
        for e in errs:
            print(f"    {_c('✗', _RED)} {e}")
    if warns:
        for w in warns:
            print(f"    {_c('⚠', _YELLOW)} {w}")


# ---------------------------------------------------------------------------
# Final-mapping table renderer
# ---------------------------------------------------------------------------

def _print_final_mapping(final_mapping: list[dict[str, Any]]) -> None:
    if not final_mapping:
        print(_c("  (empty — no entries to display)", _DIM))
        return
    for i, entry in enumerate(final_mapping, 1):
        target = entry.get("path", "?")
        req = entry.get("request", {})
        src = req.get("path", "?")
        action = req.get("action", "?")
        prov = req.get("provenance_ref", "?")
        order = req.get("action_order", "?")
        print(f"  {_c(str(i).rjust(3), _DIM)}. {_c(action.upper(), _CYAN)} "
              f"order={order} prov={prov}")
        print(f"       src : {_c(_shorten(src, 64), _DIM)}")
        print(f"       dst : {_c(_shorten(target, 64), _GREEN)}")


def _shorten(path: str, maxlen: int) -> str:
    if len(path) <= maxlen:
        return path
    return "…" + path[-(maxlen - 1):]


# ---------------------------------------------------------------------------
# Interactive branch-decision UI
# ---------------------------------------------------------------------------

def _collect_decisions(result: dict[str, Any], batch_mode: bool = False) -> dict[str, str]:
    forest = result.get("trees", [])
    branched = [n for n in forest if n.get("warning") == "W_FOREST_BRANCHING"]

    if not branched:
        print(_c("  No conflicts detected — no branch decisions needed.", _GREEN))
        return {}

    if batch_mode:
        # Auto-resolve: select first candidate for all conflicts
        print(_c(f"  {len(branched)} conflict(s) auto-resolved (batch mode):", _YELLOW))
        decisions: dict[str, str] = {}
        for idx, node in enumerate(branched, 1):
            target = node["path"]
            candidates: list[str] = node.get("candidates", [])
            if candidates:
                decisions[target] = candidates[0]
                if idx <= 3:  # Show first 3 for visibility
                    prov = "?"
                    for cr in node.get("changerequest", []):
                        if cr.get("path") == candidates[0]:
                            prov = cr.get("provenance_ref", "?")
                            break
                    print(f"    [{idx}] prov={prov} → {_shorten(candidates[0], 60)}")
        if len(branched) > 3:
            print(f"    ... and {len(branched) - 3} more")
        return decisions

    print(_c(f"\n  {len(branched)} conflict(s) require your decision:\n", _YELLOW))
    decisions: dict[str, str] = {}

    for idx, node in enumerate(branched, 1):
        target = node["path"]
        destin_mid = node.get("destin_mixed_id", "?")
        candidates: list[str] = node.get("candidates", [])
        changerequests: list[dict[str, Any]] = node.get("changerequest", [])

        print(_c(f"  [{idx}/{len(branched)}] Conflict at target:", _BOLD))
        print(f"    {_c(_shorten(target, 68), _YELLOW)}")
        print(f"    destin mod-id : {destin_mid}")
        print()
        print("    Candidates (choose one):")
        for ci, src_path in enumerate(candidates, 1):
            # Find matching changerequest for extra context
            prov = "?"
            order = "?"
            for cr in changerequests:
                if cr.get("path") == src_path:
                    prov = cr.get("provenance_ref", "?")
                    order = cr.get("action_order", "?")
                    break
            print(f"      {_c(str(ci), _BOLD)}) prov={prov}  order={order}")
            print(f"         {_c(_shorten(src_path, 62), _DIM)}")

        # Input loop
        while True:
            raw = input(f"\n    Enter choice [1-{len(candidates)}]: ").strip()
            if raw.isdigit():
                choice = int(raw)
                if 1 <= choice <= len(candidates):
                    decisions[target] = candidates[choice - 1]
                    print(_c(f"    ✓ Chose candidate {choice}", _GREEN))
                    break
            print(_c(f"    Invalid input — enter a number between 1 and {len(candidates)}.", _RED))

        print()

    return decisions


# ---------------------------------------------------------------------------
# decisions persist
# ---------------------------------------------------------------------------

def _save_decisions(decisions: dict[str, str], write_json_file: Any) -> str:
    _REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = _REPORTS_DIR / f"decisions-{ts}.json"
    write_json_file(str(out_path), decisions)
    return str(out_path)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Interactive demo: aggregate → compute → decide → visualize"
    )
    p.add_argument(
        "--kmm-rule",
        default=_DEFAULT_KMM_RULE,
        metavar="PATH",
        help="Path to kmm_rule JSON file (default: castears example)",
    )
    p.add_argument(
        "--database",
        default=_DEFAULT_DATABASE,
        metavar="PATH",
        help="Path to database JSON file",
    )
    p.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help="Optional path to write final result JSON",
    )
    p.add_argument(
        "--batch",
        action="store_true",
        help="Auto-resolve all conflicts (select first candidate); no interactive prompts",
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colour output",
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = _build_parser().parse_args()

    # Disable colour if requested or not a TTY
    if args.no_color or not sys.stdout.isatty():
        global _RESET, _BOLD, _CYAN, _YELLOW, _GREEN, _RED, _DIM
        _RESET = _BOLD = _CYAN = _YELLOW = _GREEN = _RED = _DIM = ""

    compute_mapping, visualize_payload, load_json_file, write_json_file, aggregate_single_kmm_rule_file = (
        _load_modules()
    )

    # ------------------------------------------------------------------
    # Phase 1 — load database
    # ------------------------------------------------------------------
    _section("Phase 1 — Load inputs")
    print(f"  kmm-rule : {_shorten(args.kmm_rule, 68)}")
    print(f"  database : {_shorten(args.database, 68)}")

    try:
        database = load_json_file(args.database)
    except Exception as exc:
        print(_c(f"\nFailed to load database: {exc}", _RED), file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Phase 2 — aggregate kmm_rule
    # ------------------------------------------------------------------
    _section("Phase 2 — Aggregate kmm_rule")
    aggregated_rule_set, agg_errors, agg_warnings = aggregate_single_kmm_rule_file(args.kmm_rule)

    if agg_warnings:
        for w in agg_warnings:
            print(_c(f"  ⚠ {w}", _YELLOW))
    if agg_errors:
        for e in agg_errors:
            print(_c(f"  ✗ {e}", _RED))
        print(_c("\nAggregation failed — cannot continue.", _RED), file=sys.stderr)
        return 1

    mod_keys = list(aggregated_rule_set.keys())
    print(_c(f"  OK — {len(mod_keys)} mod(s) aggregated: {', '.join(mod_keys)}", _GREEN))

    # ------------------------------------------------------------------
    # Phase 3 — first-pass compute_mapping (no decisions)
    # ------------------------------------------------------------------
    _section("Phase 3 — First-pass mapping (no branch decisions)")
    first_result = compute_mapping(
        aggregated_rule_set=aggregated_rule_set,
        database=database,
        branch_decisions={},
    )
    _print_summary("First-pass result:", first_result)

    # ------------------------------------------------------------------
    # Phase 4 — visualize forest BEFORE decision
    # ------------------------------------------------------------------
    _section("Phase 4 — Forest visualization (before decisions)")
    try:
        forest_ascii = visualize_payload(first_result, "ascii", show_m1_details=True)
        print(forest_ascii)
    except Exception as exc:
        print(_c(f"  Visualization error: {exc}", _YELLOW))

    # ------------------------------------------------------------------
    # Phase 5 — interactive branch-decision UI
    # ------------------------------------------------------------------
    _section("Phase 5 — Branch decision")
    decisions = _collect_decisions(first_result, batch_mode=args.batch)

    if decisions:
        decisions_path = _save_decisions(decisions, write_json_file)
        print(_c(f"  Decisions saved → {_shorten(decisions_path, 64)}", _DIM))
    else:
        decisions_path = None

    # ------------------------------------------------------------------
    # Phase 6 — second-pass compute_mapping (with decisions)
    # ------------------------------------------------------------------
    _section("Phase 6 — Second-pass mapping (with decisions applied)")
    second_result = compute_mapping(
        aggregated_rule_set=aggregated_rule_set,
        database=database,
        branch_decisions=decisions,
    )
    _print_summary("Second-pass result:", second_result)

    # ------------------------------------------------------------------
    # Phase 7 — final forest visualization
    # ------------------------------------------------------------------
    _section("Phase 7 — Final forest visualization")
    try:
        final_forest_ascii = visualize_payload(second_result, "ascii", show_m1_details=True)
        print(final_forest_ascii)
    except Exception as exc:
        print(_c(f"  Visualization error: {exc}", _YELLOW))

    # ------------------------------------------------------------------
    # Phase 8 — final_mapping table
    # ------------------------------------------------------------------
    _section("Phase 8 — Pruned mapping (final_mapping)")
    fm = second_result.get("final_mapping", [])
    _print_final_mapping(fm)

    # ------------------------------------------------------------------
    # Optional JSON output
    # ------------------------------------------------------------------
    if args.out:
        try:
            write_json_file(args.out, second_result)
            print(f"\n  Result written → {args.out}")
        except Exception as exc:
            print(_c(f"\nFailed to write output: {exc}", _RED), file=sys.stderr)

    _hr()
    status = _c("DONE — conflicts resolved", _GREEN) if not second_result.get("errors") else _c("DONE — errors remain", _YELLOW)
    print(f"  {status}")
    _hr()
    return 0


if __name__ == "__main__":
    sys.exit(main())
