"""orchestrator.py — Unified pipeline orchestration for mod management.

Provides:
  - ``ProgressCallback`` protocol for progress reporting.
  - ``PipelineResult`` dataclass to hold pipeline execution results.
  - ``compute()``  — aggregate rules → compute mapping.
  - ``backup()``   — differential backup of mapped files.
  - ``apply()``    — apply the final mapping to disk.
  - ``run()``      — full pipeline (aggregate → compute → backup → apply).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .backup_ops import apply_final_mapping, run_differential_backup
from .engine import compute_mapping
from .rule_aggregator import aggregate

__all__ = [
    "ProgressCallback",
    "PipelineResult",
    "compute",
    "backup",
    "apply",
    "run",
]


# ── Progress callback protocol ────────────────────────────────────────────────


class ProgressCallback(Protocol):
    """Progress notification callback.

    Args:
        step: Stage identifier ("scan" | "aggregate" | "compute" | "backup" |
              "apply" | "restore").
        finished: Number of completed items.
        total: Total number of items (-1 means unknown).
        message: Optional description text.
    """

    def __call__(self, step: str, finished: int, total: int, message: str = "") -> None:
        ...


# ── Data structures ───────────────────────────────────────────────────────────


@dataclass
class PipelineResult:
    """Holds the result of a pipeline execution.

    Attributes:
        ok: Whether the pipeline completed without errors.
        errors: Accumulated error messages.
        warnings: Accumulated warning messages.
        forest: Mapping forest from ``compute_mapping``.
        final_mapping: Final resolved mapping list.
        mapping_result: Raw result dict from ``compute_mapping``.
        backup_result: Result dict from ``run_differential_backup`` (if run).
        apply_result: Result dict from ``apply_final_mapping`` (if run).
    """

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    forest: list[dict[str, Any]] = field(default_factory=list)
    final_mapping: list[dict[str, Any]] = field(default_factory=list)
    mapping_result: dict[str, Any] = field(default_factory=dict)
    backup_result: dict[str, Any] | None = None
    apply_result: dict[str, Any] | None = None


# ── Phase helpers ─────────────────────────────────────────────────────────────


def compute(
    database: dict,
    kmm_rule_paths: list[str],
    user_config_path: str,
    *,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Aggregate rules and compute the file mapping.

    This is a combined step that first calls ``rule_aggregator.aggregate()``
    to merge all kmm_rule files, then calls ``engine.compute_mapping()`` to
    produce the final mapping.

    Args:
        database: Game database dict.
        kmm_rule_paths: List of paths to kmm_rule_*.json files.
        user_config_path: Path to user_config.json.
        action_orders: Optional ``{mixed_id: int}`` overrides.
        branch_decisions: Optional explicit branch decisions.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.  ``backup_result`` and ``apply_result`` are
        always ``None`` from this function.
    """
    # ── Aggregation phase ─────────────────────────────────────────────────
    if on_progress is not None:
        on_progress("aggregate", 0, 1, "Aggregating rules...")

    aggregated, agg_errors, agg_warnings = aggregate(
        kmm_rule_paths,
        user_config_path,
        action_orders=action_orders,
    )

    if on_progress is not None:
        on_progress("aggregate", 1, 1, "Rule aggregation complete")

    if aggregated is None or agg_errors:
        return PipelineResult(
            ok=False,
            errors=agg_errors,
            warnings=agg_warnings,
        )

    # ── Computation phase ─────────────────────────────────────────────────
    if on_progress is not None:
        on_progress("compute", 0, 1, "Computing mapping...")

    mapping_result = compute_mapping(
        aggregated_rule_set=aggregated,
        database=database,
        branch_decisions=branch_decisions or {},
    )

    if on_progress is not None:
        on_progress("compute", 1, 1, "Mapping computation complete")

    return PipelineResult(
        ok=not mapping_result.get("errors"),
        errors=mapping_result.get("errors", []),
        warnings=agg_warnings + mapping_result.get("warnings", []),
        forest=mapping_result.get("forest", []),
        final_mapping=mapping_result.get("final_mapping", []),
        mapping_result=mapping_result,
    )


def backup(
    mapping_result: dict[str, Any],
    backup_dir: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Run differential backup for files in the mapping result.

    Extracts the list of file paths from ``final_mapping`` within
    *mapping_result* and passes them to ``run_differential_backup``.

    Args:
        mapping_result: The raw result dict from ``compute_mapping``.
        backup_dir: Target backup directory.
        on_progress: Optional progress callback.

    Returns:
        The result dict from ``run_differential_backup``.
    """
    final_mapping_list: list[dict[str, Any]] = mapping_result.get("final_mapping", [])
    files_to_backup = [entry["path"] for entry in final_mapping_list if entry.get("path")]

    if not files_to_backup:
        return {"ok": True, "backed_up": [], "skipped": [], "errors": []}

    if on_progress is not None:
        on_progress("backup", 0, len(files_to_backup), "Starting differential backup...")

    result = run_differential_backup(backup_dir, files_to_backup)

    if on_progress is not None:
        on_progress("backup", len(files_to_backup), len(files_to_backup), "Backup complete")

    return result


def apply(
    final_mapping: list[dict[str, Any]],
    backup_dir: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Apply the final mapping to disk.

    Calls ``apply_final_mapping`` after verifying the backup gate.

    Args:
        final_mapping: The ``final_mapping`` list from ``compute_mapping``.
        backup_dir: Path to the backup directory (gate check).
        dry_run: When ``True`` only check the gate, do not modify files.
        on_progress: Optional progress callback.

    Returns:
        The result dict from ``apply_final_mapping``.
    """
    if on_progress is not None:
        on_progress("apply", 0, 1, "Applying final mapping...")

    result = apply_final_mapping(final_mapping, backup_dir, dry_run=dry_run)

    if on_progress is not None:
        on_progress("apply", 1, 1, "Apply complete")

    return result


def run(
    database: dict,
    kmm_rule_paths: list[str],
    user_config_path: str,
    backup_dir: str,
    *,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Execute the full pipeline: aggregate → compute → backup → apply.

    This is a convenience wrapper around ``compute()`` + ``backup()`` +
    ``apply()`` that provides continuous progress callbacks and short-circuits
    on failure.

    Args:
        database: Game database dict.
        kmm_rule_paths: List of paths to kmm_rule_*.json files.
        user_config_path: Path to user_config.json.
        backup_dir: Target backup directory.
        action_orders: Optional ``{mixed_id: int}`` overrides.
        branch_decisions: Optional explicit branch decisions.
        dry_run: When ``True`` skip actual file modifications.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult`` with all intermediate results populated.
    """
    # ── Step 1: Compute ───────────────────────────────────────────────────
    compute_result = compute(
        database,
        kmm_rule_paths,
        user_config_path,
        action_orders=action_orders,
        branch_decisions=branch_decisions,
        on_progress=on_progress,
    )

    if not compute_result.ok:
        return compute_result

    # dry_run 模式下跳过 backup 和 apply（仅计算，不碰磁盘）
    if dry_run:
        return PipelineResult(
            ok=compute_result.ok,
            errors=compute_result.errors,
            warnings=compute_result.warnings,
            forest=compute_result.forest,
            final_mapping=compute_result.final_mapping,
            mapping_result=compute_result.mapping_result,
            backup_result=None,
            apply_result=None,
        )

    # ── Step 2: Backup ────────────────────────────────────────────────────
    backup_result = backup(
        compute_result.mapping_result,
        backup_dir,
        on_progress=on_progress,
    )

    if not backup_result.get("ok"):
        errors = list(compute_result.errors)
        backup_errors = backup_result.get("errors", [])
        if isinstance(backup_errors, list):
            errors.extend(backup_errors)
        else:
            errors.append(str(backup_errors))
        return PipelineResult(
            ok=False,
            errors=errors,
            warnings=compute_result.warnings,
            forest=compute_result.forest,
            final_mapping=compute_result.final_mapping,
            mapping_result=compute_result.mapping_result,
            backup_result=backup_result,
        )

    # ── Step 3: Apply ─────────────────────────────────────────────────────
    apply_result = apply(
        compute_result.final_mapping,
        backup_dir,
        dry_run=dry_run,
        on_progress=on_progress,
    )

    # ── Assemble final result ─────────────────────────────────────────────
    all_errors: list[str] = list(compute_result.errors)
    all_warnings: list[str] = list(compute_result.warnings)

    for phase_result, key in [(backup_result, "errors"), (apply_result, "errors")]:
        if phase_result is not None:
            phase_errors = phase_result.get(key, [])
            if isinstance(phase_errors, list):
                all_errors.extend(phase_errors)
            elif phase_errors:
                all_errors.append(str(phase_errors))

    for phase_result, key in [(backup_result, "warnings"), (apply_result, "warnings")]:
        if phase_result is not None:
            phase_warnings = phase_result.get(key, [])
            if isinstance(phase_warnings, list):
                all_warnings.extend(phase_warnings)
            elif phase_warnings:
                all_warnings.append(str(phase_warnings))

    return PipelineResult(
        ok=not any(all_errors),
        errors=all_errors,
        warnings=all_warnings,
        forest=compute_result.forest,
        final_mapping=compute_result.final_mapping,
        mapping_result=compute_result.mapping_result,
        backup_result=backup_result,
        apply_result=apply_result,
    )
