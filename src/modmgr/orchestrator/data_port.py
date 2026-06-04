"""DataPort — the sole I/O adapter for the orchestrator.

DataPort is the only module in the orchestrator that performs file I/O.
Resolvers are pure parsing (strings → SourceDescriptor), and the engine/
planner are pure data transformation. DataPort bridges the gap:

  - ``fetch(desc, intent)``: read data per SourceDescriptor → clean dicts
  - ``push(dest, intent, result)``: write results per DestDescriptor
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..bootstrap import discover_user_config
from ..core.workspacemanager import WorkspaceManager
from ..iojson import load_json_file
from ..path_resolver import expand_path
from ._common import (
    PipelineResult,
    _get_workspace_manager,
    _resolve_database,
    _sha256_dict,
    _utcnow,
)
from .entry import Intent


# ── Descriptors ────────────────────────────────────────────────────────


@dataclass
class SourceDescriptor:
    """Describes the source of data for ``fetch()``.

    Produced by Resolver.resolve() — no I/O at that stage.
    """
    source_type: Literal["workspace", "file_paths", "raw_dict"]
    workspace_id: str | None = None
    config_index: str = ""
    database_path: str | None = None
    database_dict: dict | None = None
    aggregated_rule_set: dict | None = None
    final_mapping: list | None = None
    user_config_dict: dict | None = None


@dataclass
class DestDescriptor:
    """Describes the destination for ``push()``.

    Constructed from ``TaskRequest.output_type`` + ``output_args``.
    SEPARATE from SourceDescriptor — never mix source and dest fields.
    """
    output_type: Literal["workspace", "none"]
    workspace_id: str | None = None
    config_index: str = ""


# ── Fetch ──────────────────────────────────────────────────────────────


def fetch(desc: SourceDescriptor, intent: Intent) -> dict[str, Any]:
    """Read data per source descriptor. Returns clean dicts varying by intent.

    Args:
        desc: SourceDescriptor from a Resolver.
        intent: Pipeline intent (determines which keys are populated).

    Returns:
        dict with keys like:
          - ``database``, ``user_config``, ``final_mapping`` (all intents)
          - ``aggregated_rule_set``, ``decisions`` (COMPUTE_MAPPING workspace)
    """
    if desc.source_type == "workspace":
        return _fetch_workspace(desc, intent)
    elif desc.source_type == "file_paths":
        return _fetch_file_paths(desc)
    elif desc.source_type == "raw_dict":
        return _fetch_raw_dict(desc)
    else:
        raise ValueError(f"unknown source_type: {desc.source_type}")


def _validate_database_name(name: str) -> None:
    """Validate database_name doesn't contain path traversal characters."""
    if not name:
        raise ValueError(
            "E_DATABASE_NAME_EMPTY: database_name must not be empty"
        )
    if ".." in name:
        raise ValueError(
            f"E_PATH_TRAVERSAL: database_name contains '..': {name}"
        )


def _fetch_workspace(desc: SourceDescriptor, intent: Intent) -> dict[str, Any]:
    """Fetch data from a workspace."""
    assert desc.workspace_id is not None

    # 1. Read user_config
    user_config, _ = discover_user_config(config_index=desc.config_index)

    # 2. Create WorkspaceManager, read meta → database_name
    wm = _get_workspace_manager(user_config)
    if not wm.exists(desc.workspace_id):
        raise ValueError(f"workspace '{desc.workspace_id}' does not exist")

    meta = wm.read_meta(desc.workspace_id)
    database_name = meta["database_name"]
    _validate_database_name(database_name)

    # 3. Resolve database_name to path, read database file
    database = _resolve_database(database_name, user_config)

    # 4. Read mapping → final_mapping
    mapping = wm.read_mapping(desc.workspace_id)
    final_mapping = mapping.get("final_mapping", [])

    result: dict[str, Any] = {
        "database": database,
        "user_config": user_config,
        "final_mapping": final_mapping,
    }

    # 5. If COMPUTE_MAPPING: also read aggregated_rule + decisions
    if intent == Intent.COMPUTE_MAPPING:
        if wm.has_aggregated_rule(desc.workspace_id):
            result["aggregated_rule_set"] = wm.read_aggregated_rule(
                desc.workspace_id
            )
        decisions = (
            wm.read_decisions(desc.workspace_id)
            if wm.has_decisions(desc.workspace_id)
            else {}
        )
        result["decisions"] = decisions

    return result


def _fetch_file_paths(desc: SourceDescriptor) -> dict[str, Any]:
    """Fetch data from explicit file paths."""
    assert desc.database_path is not None
    database = load_json_file(expand_path(desc.database_path))
    user_config, _ = discover_user_config(config_index=desc.config_index)
    return {
        "database": database,
        "user_config": user_config,
        "final_mapping": [],
    }


def _fetch_raw_dict(desc: SourceDescriptor) -> dict[str, Any]:
    """Fetch data from inline dicts."""
    result: dict[str, Any] = {
        "database": desc.database_dict or {},
        "user_config": desc.user_config_dict or {},
        "final_mapping": desc.final_mapping or [],
    }
    if desc.aggregated_rule_set is not None:
        result["aggregated_rule_set"] = desc.aggregated_rule_set
    return result


# ── Push ───────────────────────────────────────────────────────────────


def push(dest: DestDescriptor, intent: Intent, result: PipelineResult) -> None:
    """Write results per destination descriptor.

    Only ``output_type="workspace"`` with ``intent == COMPUTE_MAPPING``
    writes data (mapping, fingerprints, SVG). All other combinations are
    no-ops.
    """
    if dest.output_type != "workspace" or intent != Intent.COMPUTE_MAPPING:
        return

    assert dest.workspace_id is not None
    user_config, _ = discover_user_config(config_index=dest.config_index)
    wm = _get_workspace_manager(user_config)

    # ── Write mapping ─────────────────────────────────────────────────
    wm.write_mapping(dest.workspace_id, result.mapping_result)

    # ── Compute and write fingerprints ────────────────────────────────
    fp_source = result.mapping_result.get("_fingerprint_inputs", {})
    fingerprints = {
        "schema_namespace": "KMM_WorkspaceFingerprints",
        "schema_version": "knighthana@0.1.0",
        "kmmrule": _sha256_dict(fp_source.get("aggregated_rule_set", {})),
        "database": _sha256_dict(fp_source.get("database", {})),
        "computed_at": _utcnow(),
    }
    wm.write_fingerprints(dest.workspace_id, fingerprints)

    # ── Generate and write SVG if trees present ───────────────────────
    if result.trees:
        try:
            from ..forest_visual import visualize_payload

            svg = visualize_payload({"trees": result.trees}, "svg")
            wm.write_svg(dest.workspace_id, svg)
        except Exception:
            pass  # SVG generation is non-critical
