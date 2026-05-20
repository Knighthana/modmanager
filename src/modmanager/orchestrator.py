"""orchestrator.py — Unified pipeline orchestration for mod management.

Provides:
  - ``ProgressCallback`` protocol for progress reporting.
  - ``PipelineResult`` dataclass to hold pipeline execution results.
  - ``compute()``  — aggregate rules → compute mapping.
  - ``backup()``   — differential backup of mapped files.
  - ``apply()``    — apply the final mapping to disk.
  - ``restore()``  — restore files from backup (engine primitive).
  - ``run()``      — full pipeline (aggregate → compute → backup → apply).
  - ``compute_ws()`` — workspace-aware compute (reads rules/decisions from workspace).
  - ``backup_ws()``  — workspace-aware backup.
    - ``resolve_apply_ws()`` — resolve workspace inputs for apply.
    - ``orchestrate_apply()`` — workspace-aware apply orchestration.
  - ``restore_ws()`` — workspace-aware restore.
  - ``run_ws()``     — workspace-aware full pipeline.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .backup_dir_builder import build_backup_dirs, load_dir_suffixes
from .backup_ops import (
    _flatten_tree_file_hashes,
    _sha256_file,
    apply_final_mapping,
    check_backup_gate,
    load_backup_info,
    run_differential_backup,
)
from .bootstrap import discover_user_config
from .core.workspacemanager import WorkspaceManager
from .engine import compute_mapping
from .iojson import load_json_file
from .path_resolver import expand_path
from .paths import normalize_posix


__all__ = [
    "ProgressCallback",
    "PipelineResult",
    "compute",
    "backup",
    "apply",
    "restore",
    "run",
    "compute_ws",
    "backup_ws",
    "resolve_apply_ws",
    "orchestrate_apply",
    "restore_ws",
    "run_ws",
]


# ── bakignore helpers ─────────────────────────────────────────────────────────

_ignore_cache: dict[str, object] = {}


def _parse_gitignore_file(path: str):
    """用 gitignore-parser 解析 .kmmbakignore，返回判定函数。"""
    import gitignore_parser
    return gitignore_parser.parse_gitignore(path, base_dir=str(Path(path).parent))


def _any_path_component_ends_with(file_path: str, suffixes: list[str]) -> bool:
    """检查路径的任何一个目录组件是否以指定后缀结尾。"""
    parts = Path(normalize_posix(file_path)).parts
    return any(part.endswith(s) for s in suffixes for part in parts)


def _should_ignore(file_abs: str, contentid_root: str, dir_suffixes: list[str]) -> bool:
    """判定 file_abs 是否应被忽略。

    1. 目录级检查：路径任意组件以 dir_suffixes 中任一后缀结尾 → 忽略
    2. gitignore 级联：从文件目录向上走到 contentid_root，
       每层 .kmmbakignore 用 gitignore-parser 解析并缓存。
       子目录规则覆盖父目录（git 语义：后匹配优先）。
    """
    # 目录级
    if _any_path_component_ends_with(file_abs, dir_suffixes):
        return True

    # gitignore 级联：从文件所在目录往上走，最近匹配优先
    file_path = Path(file_abs)
    current = file_path.parent
    content_root_path = Path(contentid_root)

    while current != content_root_path.parent:
        ig = current / ".kmmbakignore"
        if ig.is_file():
            ig_str = str(ig)
            rules = _ignore_cache.get(ig_str)
            if rules is None:
                try:
                    rules = _parse_gitignore_file(ig_str)
                except Exception:
                    rules = lambda _: None
                _ignore_cache[ig_str] = rules
            try:
                result = rules(str(file_path))
            except Exception:
                result = None
            if result is True:
                return True   # 子目录判定忽略 → 立即生效，不看父级
            elif result is False:
                return False  # 子目录否定忽略 → 立即生效，不看父级
        if current == content_root_path:
            break
        current = current.parent

    return False


def _copy_kmmbakignore_chain(file_abs: str, contentid_root: str, backup_dir_str: str,
                             copied: set[str]) -> None:
    """从 file_abs 所在目录往上走到 contentid_root，
    每层 .kmmbakignore 拷贝进 backup_dir 对应位置。已拷贝的跳过。
    """
    file_path = Path(file_abs)
    current = file_path.parent
    content_root_path = Path(contentid_root)
    backup_path = Path(backup_dir_str)

    while current != content_root_path.parent:
        ig = current / ".kmmbakignore"
        if ig.is_file() and str(ig) not in copied:
            copied.add(str(ig))
            rel = ig.relative_to(content_root_path)
            dest = backup_path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(ig), str(dest))
        if current == content_root_path:
            break
        current = current.parent


# ── Managed entries filter ────────────────────────────────────────────────────


def _apply_managed_filter(
    database: dict[str, Any],
    managed_entries: dict[str, dict[str, list[str]]] | None,
) -> dict[str, Any]:
    """用 managed_entries 过滤 database 中的条目。

    Args:
        database: 完整 database 结构（含 game[], mod[]）
        managed_entries: 可选，{ "game": { appid: [路径列表] }, "mod": { mixed_id: [路径列表] } }

    Returns:
        过滤后的 database 深拷贝。若 managed_entries 为 None，返回原 database 的深拷贝。

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
        trees: Mapping trees from ``compute_mapping``.
        final_mapping: Final resolved mapping list.
        mapping_result: Raw result dict from ``compute_mapping``.
        backup_result: Result dict from ``run_differential_backup`` (if run).
        apply_result: Result dict from ``apply_final_mapping`` (if run).
    """

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    trees: list[dict[str, Any]] = field(default_factory=list)
    final_mapping: list[dict[str, Any]] = field(default_factory=list)
    mapping_result: dict[str, Any] = field(default_factory=dict)
    backup_result: dict[str, Any] | None = None
    apply_result: dict[str, Any] | None = None
    restore_result: dict[str, Any] | None = None
    backup_dir: str | None = None


def _generate_apply_preflight(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
) -> dict[str, Any]:
    """Generate an apply preflight manifest without executing file operations."""
    backup_dirs, dir_warnings = build_backup_dirs(final_mapping, database, user_config)

    manifest_dirs: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = list(dir_warnings)

    for backup_dir_str, dir_files in backup_dirs.items():
        path_set = {normalize_posix(str(p)) for p in dir_files}
        applicable_entries = sum(
            1
            for entry in final_mapping
            if normalize_posix(str(entry.get("path", ""))) in path_set
        )
        gate_errors = check_backup_gate(backup_dir_str)
        if gate_errors:
            errors.extend(gate_errors)
            warnings.append(
                f"W_BACKUP_GATE_FAILED: {backup_dir_str}: {'; '.join(gate_errors)}"
            )
        manifest_dirs.append(
            {
                "path": backup_dir_str,
                "gate_pass": not gate_errors,
                "gate_errors": gate_errors,
                "applicable_entries": applicable_entries,
            }
        )

    return {
        "ok": not errors,
        "backup_dirs": manifest_dirs,
        "errors": errors,
        "warnings": warnings,
        "diagnostics": {
            "total_backup_dirs": len(backup_dirs),
            "failed_backup_dirs": [d["path"] for d in manifest_dirs if not d["gate_pass"]],
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── Phase helpers ─────────────────────────────────────────────────────────────


def compute(
    database: dict,
    *,
    aggregated_rule_set: dict | None = None,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    managed_entries: dict | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Compute the file mapping from a pre-aggregated rule set dict.

    Args:
        database: Game database dict.
        aggregated_rule_set: Pre-aggregated rule set dict. When ``None``,
            returns an error.
        action_orders: Optional ``{mixed_id: int}`` overrides.
        branch_decisions: Optional explicit branch decisions.
        managed_entries: Optional dict to filter database entries before
            computing. Format: ``{"game": {appid: [basepaths]}, "mod": {mixed_id: [paths]}}``.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.  ``backup_result`` and ``apply_result`` are
        always ``None`` from this function.
    """
    # ── Validate rule input ────────────────────────────────────────────
    if not aggregated_rule_set:
        return PipelineResult(
            ok=False,
            errors=["E_NO_RULE_INPUT: aggregated_rule_set is required"],
        )
    aggregated = aggregated_rule_set
    agg_errors: list[str] = []
    agg_warnings: list[str] = []

    # ── Apply managed filter before computation ───────────────────────────
    filtered_database = _apply_managed_filter(database, managed_entries)

    # ── Computation phase ─────────────────────────────────────────────────
    if on_progress is not None:
        on_progress("compute", 0, 1, "Computing mapping...")

    mapping_result = compute_mapping(
        aggregated_rule_set=aggregated,
        database=filtered_database,
        branch_decisions=branch_decisions or {},
    )

    if on_progress is not None:
        on_progress("compute", 1, 1, "Mapping computation complete")

    return PipelineResult(
        ok=not mapping_result.get("errors"),
        errors=mapping_result.get("errors", []),
        warnings=agg_warnings + mapping_result.get("warnings", []),
        trees=mapping_result.get("trees", []),
        final_mapping=mapping_result.get("final_mapping", []),
        mapping_result=mapping_result,
    )


def backup(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """对 final_mapping 中的文件执行差异备份。

    内部调用 ``build_backup_dirs`` 推导备份目录，遍历各目录
    执行 ``run_differential_backup``，聚合结果。

    Args:
        final_mapping: ``final_mapping`` list from ``compute_mapping``.
        database: Game database dict.
        user_config: User configuration dict.
        dry_run: When ``True`` only report what would be backed up.
        on_progress: Optional progress callback.

    Returns:
        Result dict with ``ok``, ``backed_up``, ``skipped``, ``errors``,
        ``warnings``, ``dry_run``.
    """
    backup_dirs, dir_warnings = build_backup_dirs(final_mapping, database, user_config)

    all_backed_up: list[str] = []
    all_skipped: list[str] = []
    all_errors: list[str] = []
    all_warnings: list[str] = list(dir_warnings)
    total_files = sum(len(files) for files in backup_dirs.values())
    processed = 0

    for backup_dir_str, files in backup_dirs.items():
        if not files:
            continue
        if on_progress is not None:
            on_progress("backup", processed, total_files, backup_dir_str)

        # ── Apply bakignore filters ─────────────────────────────────────
        dir_suffixes = load_dir_suffixes(user_config)
        # Derive source contentid root from backup_dir_str
        # backup_dir_str format: {root}/{contentid}.{hex}.{baksuffix}/
        backup_path_obj = Path(backup_dir_str)
        contentid_dir = backup_path_obj.parent  # the contentid directory
        source_root = str(contentid_dir)

        filtered_files = []
        copied_ignores: set[str] = set()
        for f in files:
            if _should_ignore(f, source_root, dir_suffixes):
                all_skipped.append(f)
                continue
            filtered_files.append(f)
            _copy_kmmbakignore_chain(f, source_root, backup_dir_str, copied_ignores)

        if not filtered_files:
            processed += len(files)
            continue

        result = run_differential_backup(
            backup_dir_str, filtered_files,
            on_progress=on_progress,
            dry_run=dry_run,
        )
        all_backed_up.extend(result.get("backed_up", []))
        all_skipped.extend(result.get("skipped", []))
        all_errors.extend(result.get("errors", []))
        processed += len(files)

    if on_progress is not None:
        on_progress("backup", processed, total_files, "Backup complete")

    return {
        "ok": not all_errors,
        "backed_up": all_backed_up,
        "skipped": all_skipped,
        "errors": all_errors,
        "warnings": all_warnings,
        "dry_run": dry_run,
    }


def apply(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """执行 final_mapping 的磁盘替换。

    内部调用 ``build_backup_dirs`` 推导备份目录，并将属于每个目录的
    条目分组后委托 ``apply_final_mapping`` 执行。

    Args:
        final_mapping: ``final_mapping`` list from ``compute_mapping``.
        database: Game database dict.
        user_config: User configuration dict.
        dry_run: When ``True`` only return structured would-apply results.
        on_progress: Optional progress callback.

    Returns:
        Result dict with ``ok``, ``applied``, ``skipped``, ``errors``,
        ``warnings``, ``dry_run``.
    """
    backup_dirs, dir_warnings = build_backup_dirs(final_mapping, database, user_config)

    all_applied: list[str] = []
    all_skipped: list[str] = []
    all_errors: list[str] = []
    all_warnings: list[str] = list(dir_warnings)
    diagnostics: dict[str, Any] = {
        "total_backup_dirs": len(backup_dirs),
        "processed_dirs": 0,
        "no_matched_entry_dirs": [],
    }

    for backup_dir_str, dir_files in backup_dirs.items():
        path_set = {normalize_posix(str(p)) for p in dir_files}
        dir_entries = [
            e for e in final_mapping
            if normalize_posix(str(e.get("path", ""))) in path_set
        ]
        if not dir_entries:
            all_warnings.append(
                f"W_APPLY_DIR_NO_MATCHED_ENTRIES: {backup_dir_str}"
            )
            diagnostics["no_matched_entry_dirs"].append(backup_dir_str)
            continue

        result = apply_final_mapping(
            dir_entries, backup_dir_str,
            dry_run=dry_run,
            on_progress=on_progress,
        )
        diagnostics["processed_dirs"] += 1
        all_applied.extend(result.get("applied", []))
        all_skipped.extend(result.get("skipped", []))
        all_errors.extend(result.get("errors", []))

    if not dry_run and not all_applied and not all_errors and diagnostics["no_matched_entry_dirs"]:
        all_warnings.append(
            "W_APPLY_NO_EFFECT: "
            f"gate_failed_dirs=0, no_matched_entry_dirs={len(diagnostics['no_matched_entry_dirs'])}"
        )

    return {
        "ok": not all_errors,
        "applied": all_applied,
        "skipped": all_skipped,
        "errors": all_errors,
        "warnings": all_warnings,
        "diagnostics": diagnostics,
        "dry_run": dry_run,
    }


def restore(
    final_mapping: list[dict[str, Any]],
    database: dict[str, Any],
    user_config: dict[str, Any],
    *,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """根据 final_mapping 恢复文件。

    独立原语，与 ``backup`` 解耦。内部调用 ``build_backup_dirs``
    推导备份目录，对每个目录读 ``backupinfo.json`` 中的 tree，
    按 force 标志决定是否比对 HASH。

    Args:
        final_mapping: ``final_mapping`` list from ``compute_mapping``.
        database: Game database dict.
        user_config: User configuration dict.
        force: When ``True`` skip HASH comparison and overwrite unconditionally.
        on_progress: Optional progress callback.

    Returns:
        Result dict with ``ok``, ``restored``, ``skipped``, ``errors``,
        ``warnings``, ``force``.
    """
    backup_dirs, dir_warnings = build_backup_dirs(final_mapping, database, user_config)

    all_restored: list[str] = []
    all_skipped: list[str] = []
    all_errors: list[str] = []
    all_warnings: list[str] = list(dir_warnings)
    total_files = sum(len(files) for files in backup_dirs.values())
    processed = 0

    for backup_dir_str, dir_files in backup_dirs.items():
        if not dir_files:
            continue

        # Gate check
        gate_errors = check_backup_gate(backup_dir_str)
        if gate_errors:
            all_warnings.append(
                f"W_BACKUP_GATE_FAILED: {backup_dir_str}: {'; '.join(gate_errors)}"
            )
            processed += len(dir_files)
            continue

        # Load backup tree
        info = load_backup_info(backup_dir_str)
        tree = info.get("tree") if isinstance(info, dict) else None
        flat_hashes = _flatten_tree_file_hashes(tree) if isinstance(tree, dict) else {}

        for target in dir_files:
            processed += 1
            if on_progress:
                on_progress("restore", processed, total_files, target)

            norm = normalize_posix(target)
            rel = norm.lstrip("/")
            src = Path(target)
            bak_file = Path(backup_dir_str) / rel

            if not bak_file.exists():
                all_skipped.append(target)
                continue

            if not force:
                # Compare HASH — skip if identical
                if src.exists():
                    try:
                        src_hash = _sha256_file(src)
                        bak_hash = _sha256_file(bak_file)
                        if src_hash == bak_hash and src_hash != "0":
                            all_skipped.append(target)
                            continue
                    except Exception:
                        pass

            # Copy from backup to original location
            try:
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(bak_file), str(src))
                all_restored.append(target)
            except OSError as exc:
                all_errors.append(f"E_RESTORE_COPY_FAILED: {target}: {exc}")

    return {
        "ok": not all_errors,
        "restored": all_restored,
        "skipped": all_skipped,
        "errors": all_errors,
        "warnings": all_warnings,
        "force": force,
    }


def run(
    database: dict,
    *,
    aggregated_rule_set: dict | None = None,
    user_config: dict[str, Any] | None = None,
    action_orders: dict[str, int] | None = None,
    branch_decisions: dict[str, str] | None = None,
    managed_entries: dict | None = None,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Execute the full pipeline: compute → backup → apply.

    This is a convenience wrapper around ``compute()`` + ``backup()`` +
    ``apply()`` that provides continuous progress callbacks and short-circuits
    on failure.

    Args:
        database: Game database dict.
        aggregated_rule_set: Pre-aggregated rule set dict. When ``None``,
            returns an error.
        user_config: User configuration dict. When ``None``, defaults to
            ``{"baksuffix": "kmmbackup"}``.
        action_orders: Optional ``{mixed_id: int}`` overrides.
        branch_decisions: Optional explicit branch decisions.
        managed_entries: Optional dict to filter database entries before
            computing. Passed through to ``compute()``.
        dry_run: When ``True`` skip actual file modifications.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult`` with all intermediate results populated.
    """
    resolved_user_config = user_config or {"baksuffix": "kmmbackup"}

    # ── Step 1: Compute ───────────────────────────────────────────────────
    compute_result = compute(
        database,
        aggregated_rule_set=aggregated_rule_set,
        action_orders=action_orders,
        branch_decisions=branch_decisions,
        managed_entries=managed_entries,
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
            trees=compute_result.trees,
            final_mapping=compute_result.final_mapping,
            mapping_result=compute_result.mapping_result,
            backup_result=None,
            apply_result=None,
        )

    # ── Step 2: Backup ────────────────────────────────────────────────────
    backup_result = backup(
        compute_result.final_mapping,
        database,
        resolved_user_config,
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
            trees=compute_result.trees,
            final_mapping=compute_result.final_mapping,
            mapping_result=compute_result.mapping_result,
            backup_result=backup_result,
        )

    # ── Step 3: Apply ─────────────────────────────────────────────────────
    apply_result = apply(
        compute_result.final_mapping,
        database,
        resolved_user_config,
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
        trees=compute_result.trees,
        final_mapping=compute_result.final_mapping,
        mapping_result=compute_result.mapping_result,
        backup_result=backup_result,
        apply_result=apply_result,
    )


# ── Workspace-aware entry points ──────────────────────────────────────────


def _get_workspace_manager(user_config: dict[str, Any] | None = None) -> WorkspaceManager:
    """Resolve workspace root directory from user_config or default."""
    cfg = user_config or {}
    ws_dir = cfg.get("workspace_dir") or str(Path.home() / ".cache" / "kmm" / "workspace")
    return WorkspaceManager(expand_path(ws_dir))


def _resolve_database(database_name: str, user_config: dict[str, Any]) -> dict[str, Any]:
    """Load a database dict from its name in user_config."""
    databases = user_config.get("databases", {})
    if database_name not in databases:
        raise ValueError(f"database '{database_name}' not found in user_config.databases")
    db_path = expand_path(databases[database_name]["path"])
    return load_json_file(db_path)


def compute_ws(
    workspace_id: str,
    *,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Compute mapping in a workspace context.

    Reads ``aggregated_rule.json`` and ``decisions.json`` from the
    workspace, resolves the bound database, and computes the mapping.
    Results (mapping + SVG + fingerprints) are written back to the
    workspace directory.

    Args:
        workspace_id: Target workspace identifier.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.  ``backup_result`` and ``apply_result`` are
        always ``None`` from this function.
    """
    user_config = discover_user_config()
    wm = _get_workspace_manager(user_config)

    if not wm.exists(workspace_id):
        return PipelineResult(
            ok=False,
            errors=[f"workspace '{workspace_id}' not found"],
        )

    # ── Load workspace context ────────────────────────────────────────
    meta = wm.read_meta(workspace_id)
    database_name = meta["database_name"]

    if not wm.has_aggregated_rule(workspace_id):
        return PipelineResult(
            ok=False,
            errors=["no aggregated rule set in workspace — aggregate rules first"],
        )
    aggregated_rule_set = wm.read_aggregated_rule(workspace_id)

    decisions = (
        wm.read_decisions(workspace_id) if wm.has_decisions(workspace_id) else {}
    )

    # ── Resolve and load database ─────────────────────────────────────
    try:
        database = _resolve_database(database_name, user_config)
    except Exception as exc:
        return PipelineResult(ok=False, errors=[str(exc)])

    # ── Compute ───────────────────────────────────────────────────────
    result = compute(
        database=database,
        aggregated_rule_set=aggregated_rule_set,
        branch_decisions=decisions.get("branch_decisions"),
        managed_entries=decisions.get("managed_entries"),
        on_progress=on_progress,
    )

    if not result.ok:
        return result

    # ── Write results back to workspace ───────────────────────────────
    wm.write_mapping(workspace_id, result.mapping_result)

    # Compute and write data fingerprints for cache invalidation
    fingerprints = {
        "schema_namespace": "KMM_WorkspaceFingerprints",
        "schema_version": "knighthana@0.1.0",
        "kmmrule": _sha256_dict(aggregated_rule_set),
        "database": _sha256_dict(database),
        "computed_at": _utcnow(),
    }
    wm.write_fingerprints(workspace_id, fingerprints)

    # Generate and write SVG
    if result.trees:
        try:
            from .forest_visual import visualize_payload
            svg = visualize_payload({"trees": result.trees}, "svg")
            wm.write_svg(workspace_id, svg)
        except Exception:
            pass  # SVG generation is non-critical

    return result


def run_ws(
    workspace_id: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Execute the full pipeline in a workspace context.

    Builds on ``compute_ws()`` and adds backup + apply phases.
    Results are written back to the workspace directory.

    Args:
        workspace_id: Target workspace identifier.
        dry_run: When ``True`` skip actual file modifications.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult`` with all intermediate results populated.
    """
    # ── Compute (workspace-aware, writes mapping + SVG) ───────────────
    compute_result = compute_ws(workspace_id=workspace_id, on_progress=on_progress)

    if not compute_result.ok:
        return compute_result

    if dry_run:
        return compute_result

    # ── Resolve database ──────────────────────────────────────────────
    user_config = discover_user_config()
    wm = _get_workspace_manager(user_config)
    meta = wm.read_meta(workspace_id)
    database = _resolve_database(meta["database_name"], user_config)

    # ── Backup ────────────────────────────────────────────────────────
    backup_result = backup(
        compute_result.final_mapping,
        database,
        user_config,
        on_progress=on_progress,
    )

    if not backup_result.get("ok"):
        errors = list(compute_result.errors)
        be = backup_result.get("errors", [])
        errors.extend(be if isinstance(be, list) else [str(be)])
        return PipelineResult(
            ok=False,
            errors=errors,
            warnings=compute_result.warnings,
            trees=compute_result.trees,
            final_mapping=compute_result.final_mapping,
            mapping_result=compute_result.mapping_result,
            backup_result=backup_result,
        )

    # ── Apply ─────────────────────────────────────────────────────────
    apply_result = apply(
        compute_result.final_mapping,
        database,
        user_config,
        dry_run=dry_run,
        on_progress=on_progress,
    )

    all_errors = list(compute_result.errors)
    all_warnings = list(compute_result.warnings)
    if apply_result:
        ae = apply_result.get("errors", [])
        all_errors.extend(ae if isinstance(ae, list) else [str(ae)])
        aw = apply_result.get("warnings", [])
        all_warnings.extend(aw if isinstance(aw, list) else [str(aw)])

    return PipelineResult(
        ok=not any(all_errors),
        errors=all_errors,
        warnings=all_warnings,
        trees=compute_result.trees,
        final_mapping=compute_result.final_mapping,
        mapping_result=compute_result.mapping_result,
        backup_result=backup_result,
        apply_result=apply_result,
    )


def backup_ws(
    workspace_id: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Run differential backup in a workspace context.

    Reads mapping from the workspace, delegates to ``backup()`` engine,
    and stores the backup dirs mapping back to the workspace.

    Args:
        workspace_id: Target workspace identifier.
        dry_run: When ``True`` only report what would be backed up.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.
    """
    user_config = discover_user_config()
    wm = _get_workspace_manager(user_config)

    if not wm.exists(workspace_id):
        return PipelineResult(
            ok=False,
            errors=[f"workspace '{workspace_id}' not found"],
        )

    # ── Load workspace context ────────────────────────────────────────
    meta = wm.read_meta(workspace_id)
    database_name = meta["database_name"]

    if not wm.has_mapping(workspace_id):
        return PipelineResult(
            ok=False,
            errors=["no mapping in workspace — compute first"],
        )
    mapping_result = wm.read_mapping(workspace_id)

    # ── Resolve and load database ─────────────────────────────────────
    try:
        database = _resolve_database(database_name, user_config)
    except Exception as exc:
        return PipelineResult(ok=False, errors=[str(exc)])

    final_mapping = mapping_result.get("final_mapping", [])

    # ── Derive backup_dirs for storage ────────────────────────────────
    try:
        backup_dirs, dir_warnings = build_backup_dirs(final_mapping, database, user_config)
    except ValueError as exc:
        return PipelineResult(ok=False, errors=[str(exc)])

    # ── Delegate to engine ────────────────────────────────────────────
    backup_result = backup(
        final_mapping,
        database,
        user_config,
        dry_run=dry_run,
        on_progress=on_progress,
    )

    # ── Collect warnings ──────────────────────────────────────────────
    all_warnings = list(dir_warnings)
    if isinstance(backup_result.get("warnings"), list):
        all_warnings.extend(backup_result["warnings"])

    return PipelineResult(
        ok=backup_result.get("ok", False),
        errors=backup_result.get("errors", []),
        warnings=all_warnings,
        final_mapping=final_mapping,
        mapping_result=mapping_result,
        backup_result=backup_result,
    )


def resolve_apply_ws(
    workspace_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    """Resolve workspace context required by apply orchestration.

    Performs workspace-level validation and returns ready-to-use inputs
    for the apply orchestration command.

    Args:
        workspace_id: Target workspace identifier.

    Returns:
        Tuple of ``(mapping_result, final_mapping, database, user_config)``.

    Raises:
        ValueError: When workspace or required inputs are missing.
    """
    user_config = discover_user_config()
    wm = _get_workspace_manager(user_config)

    if not wm.exists(workspace_id):
        raise ValueError(f"workspace '{workspace_id}' not found")

    if not wm.has_mapping(workspace_id):
        raise ValueError("no mapping in workspace — compute first")
    mapping_result = wm.read_mapping(workspace_id)

    meta = wm.read_meta(workspace_id)
    database = _resolve_database(meta["database_name"], user_config)
    final_mapping = mapping_result.get("final_mapping", [])

    return mapping_result, final_mapping, database, user_config


def orchestrate_apply(
    workspace_id: str,
    *,
    dry_run: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Apply the final mapping to disk in a workspace context.

    Reads mapping from the workspace, delegates to ``apply()`` engine.

    Args:
        workspace_id: Target workspace identifier.
        dry_run: When ``True`` skip actual file modifications.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.
    """
    try:
        mapping_result, final_mapping, database, user_config = resolve_apply_ws(workspace_id)
    except Exception as exc:
        return PipelineResult(ok=False, errors=[str(exc)])

    preflight = _generate_apply_preflight(final_mapping, database, user_config)
    if not preflight.get("ok", False):
        return PipelineResult(
            ok=False,
            errors=preflight.get("errors", []),
            warnings=preflight.get("warnings", []),
            final_mapping=final_mapping,
            mapping_result=mapping_result,
            apply_result={
                "ok": False,
                "applied": [],
                "skipped": [],
                "errors": preflight.get("errors", []),
                "warnings": preflight.get("warnings", []),
                "diagnostics": {"preflight": preflight},
                "dry_run": dry_run,
            },
        )

    # ── Delegate to engine ────────────────────────────────────────────
    apply_result = apply(
        final_mapping,
        database,
        user_config,
        dry_run=dry_run,
        on_progress=on_progress,
    )

    return PipelineResult(
        ok=apply_result.get("ok", False),
        errors=apply_result.get("errors", []),
        warnings=apply_result.get("warnings", []),
        final_mapping=final_mapping,
        mapping_result=mapping_result,
        apply_result={**apply_result, "diagnostics": {**apply_result.get("diagnostics", {}), "preflight": preflight}},
    )


def restore_ws(
    workspace_id: str,
    *,
    force: bool = False,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """从备份恢复文件（工作区感知）。

    加载工作区上下文，委托 ``restore()`` 执行。

    Args:
        workspace_id: Target workspace identifier.
        force: When ``True`` skip HASH comparison and overwrite unconditionally.
        on_progress: Optional progress callback.

    Returns:
        A ``PipelineResult``.
    """
    user_config = discover_user_config()
    wm = _get_workspace_manager(user_config)

    if not wm.exists(workspace_id):
        return PipelineResult(ok=False, errors=[f"workspace '{workspace_id}' not found"])
    if not wm.has_mapping(workspace_id):
        return PipelineResult(ok=False, errors=["no mapping in workspace — compute first"])

    mapping_result = wm.read_mapping(workspace_id)
    meta = wm.read_meta(workspace_id)
    try:
        database = _resolve_database(meta["database_name"], user_config)
    except Exception as exc:
        return PipelineResult(ok=False, errors=[str(exc)])

    final_mapping = mapping_result.get("final_mapping", [])
    restore_result = restore(
        final_mapping, database, user_config,
        force=force, on_progress=on_progress,
    )

    return PipelineResult(
        ok=restore_result.get("ok", False),
        errors=restore_result.get("errors", []),
        warnings=restore_result.get("warnings", []),
        final_mapping=final_mapping,
        mapping_result=mapping_result,
        restore_result=restore_result,
    )


# ── Helpers ──────────────────────────────────────────────────────────────


def _sha256_dict(data: dict[str, Any]) -> str:
    """SHA256 hash of a dict (sorted keys, canonical JSON)."""
    payload = json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _utcnow() -> str:
    """ISO 8601 timestamp in UTC."""
    return datetime.now(timezone.utc).isoformat()
