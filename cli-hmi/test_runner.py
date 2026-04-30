#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class _Ansi:
    GREEN = "\033[32m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    RESET = "\033[0m"


def _supports_color() -> bool:
    if not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR") is not None:
        return False
    return True


def _color(text: str, color: str) -> str:
    if not _supports_color():
        return text
    return f"{color}{text}{_Ansi.RESET}"


class DetailedResult(unittest.TextTestResult):
    def __init__(self, stream, descriptions, verbosity):
        super().__init__(stream, descriptions, verbosity)
        self.successes: list[str] = []

    def addSuccess(self, test):  # noqa: N802
        super().addSuccess(test)
        self.successes.append(test.id())


@dataclass
class RunReport:
    scope: str
    total: int
    passed: int
    failed: int
    errors: int
    skipped: int
    duration_sec: float
    successes: list[str]
    failures: list[dict[str, str]]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _tests_dir() -> Path:
    return _repo_root() / "tests"


def _discover_modules() -> list[str]:
    return sorted(p.stem for p in _tests_dir().glob("test_*.py"))


def _build_suite(scope: str, module_name: str | None = None) -> unittest.TestSuite:
    loader = unittest.TestLoader()
    repo_root = _repo_root()
    if str(repo_root / "src") not in sys.path:
        sys.path.insert(0, str(repo_root / "src"))
    if str(_tests_dir()) not in sys.path:
        sys.path.insert(0, str(_tests_dir()))

    if scope == "all":
        return loader.discover(str(_tests_dir()), pattern="test_*.py", top_level_dir=str(_tests_dir()))

    if scope == "module" and module_name:
        return loader.loadTestsFromName(module_name)

    raise ValueError("unsupported test scope")


def _run_suite(scope: str, module_name: str | None = None) -> RunReport:
    suite = _build_suite(scope, module_name)
    stream = sys.stdout
    runner = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=DetailedResult)

    started = time.time()
    result: DetailedResult = runner.run(suite)
    ended = time.time()

    failures: list[dict[str, str]] = []
    for failed_test, traceback_text in result.failures:
        failures.append(
            {
                "test": failed_test.id(),
                "type": "failure",
                "traceback": traceback_text,
                "rerun_command": f"python -m unittest {failed_test.id()}",
            }
        )
    for failed_test, traceback_text in result.errors:
        failures.append(
            {
                "test": failed_test.id(),
                "type": "error",
                "traceback": traceback_text,
                "rerun_command": f"python -m unittest {failed_test.id()}",
            }
        )

    total = result.testsRun
    failed_count = len(result.failures)
    error_count = len(result.errors)
    skipped_count = len(result.skipped)
    passed = total - failed_count - error_count - skipped_count

    return RunReport(
        scope=scope if scope == "all" else f"module:{module_name}",
        total=total,
        passed=passed,
        failed=failed_count,
        errors=error_count,
        skipped=skipped_count,
        duration_sec=ended - started,
        successes=list(result.successes),
        failures=failures,
    )


def _print_report(report: RunReport) -> None:
    print("\n" + "=" * 72)
    print(_color("TEST SUMMARY", _Ansi.CYAN))
    print("=" * 72)
    print(f"Scope:   {report.scope}")
    print(f"Total:   {report.total}")
    print(_color(f"Passed:  {report.passed}", _Ansi.GREEN))
    print(_color(f"Failed:  {report.failed}", _Ansi.RED if report.failed else _Ansi.GREEN))
    print(_color(f"Errors:  {report.errors}", _Ansi.RED if report.errors else _Ansi.GREEN))
    print(_color(f"Skipped: {report.skipped}", _Ansi.YELLOW if report.skipped else _Ansi.GREEN))
    print(f"Time:    {report.duration_sec:.3f}s")

    print("\nPASS DETAILS")
    if report.successes:
        for test_id in report.successes:
            print(_color(f"  + {test_id}", _Ansi.GREEN))
    else:
        print("  (none)")

    print("\nFAIL DETAILS")
    if report.failures:
        for item in report.failures:
            print(_color(f"  - [{item['type']}] {item['test']}", _Ansi.RED))
            print(f"    rerun: {item['rerun_command']}")
    else:
        print(_color("  (none)", _Ansi.GREEN))


def _ensure_report_dir() -> Path:
    report_dir = _repo_root() / "cli-hmi" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def _report_to_json(report: RunReport) -> dict[str, Any]:
    return {
        "scope": report.scope,
        "total": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "errors": report.errors,
        "skipped": report.skipped,
        "duration_sec": report.duration_sec,
        "successes": report.successes,
        "failures": report.failures,
    }


def _report_to_markdown(report: RunReport) -> str:
    lines: list[str] = []
    lines.append("# Test Run Report")
    lines.append("")
    lines.append(f"- Scope: {report.scope}")
    lines.append(f"- Total: {report.total}")
    lines.append(f"- Passed: {report.passed}")
    lines.append(f"- Failed: {report.failed}")
    lines.append(f"- Errors: {report.errors}")
    lines.append(f"- Skipped: {report.skipped}")
    lines.append(f"- Duration: {report.duration_sec:.3f}s")
    lines.append("")
    lines.append("## Pass Details")
    if report.successes:
        for test_id in report.successes:
            lines.append(f"- {test_id}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Fail Details")
    if report.failures:
        for item in report.failures:
            lines.append(f"- [{item['type']}] {item['test']}")
            lines.append(f"  - rerun: `{item['rerun_command']}`")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def _export_report(report: RunReport) -> tuple[Path, Path]:
    report_dir = _ensure_report_dir()
    ts = time.strftime("%Y%m%d-%H%M%S")
    json_path = report_dir / f"test-report-{ts}.json"
    md_path = report_dir / f"test-report-{ts}.md"

    json_path.write_text(json.dumps(_report_to_json(report), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_report_to_markdown(report), encoding="utf-8")
    return json_path, md_path


def _choose_module(modules: list[str]) -> str | None:
    print("\nAvailable test modules:")
    for idx, module in enumerate(modules, start=1):
        print(f"  {idx}. {module}")

    raw = input("Select module number (blank to cancel): ").strip()
    if not raw:
        return None
    try:
        num = int(raw)
    except ValueError:
        print("Invalid number.")
        return None
    if num < 1 or num > len(modules):
        print("Out of range.")
        return None
    return modules[num - 1]


def main() -> int:
    print("modmanager interactive test runner")
    print(f"Repo root: {_repo_root()}")

    last_report: RunReport | None = None

    while True:
        print("\n" + "-" * 72)
        print("1) Run ALL tests")
        print("2) Run tests by module")
        print("3) Show test modules")
        print("4) Export last report (JSON + Markdown)")
        print("0) Exit")

        choice = input("Choose [0-4]: ").strip()

        if choice == "0":
            return 0

        if choice == "1":
            report = _run_suite("all")
            _print_report(report)
            last_report = report
            continue

        if choice == "2":
            modules = _discover_modules()
            selected = _choose_module(modules)
            if not selected:
                continue
            report = _run_suite("module", selected)
            _print_report(report)
            last_report = report
            continue

        if choice == "3":
            modules = _discover_modules()
            print("\nDiscovered modules:")
            for module in modules:
                print(f"  - {module}")
            continue

        if choice == "4":
            if not last_report:
                print("No report in memory. Run tests first.")
                continue
            json_path, md_path = _export_report(last_report)
            print(f"Saved JSON: {json_path}")
            print(f"Saved Markdown: {md_path}")
            continue

        print("Invalid choice.")


if __name__ == "__main__":
    raise SystemExit(main())
