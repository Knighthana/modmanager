"""Resolver layer — resolves heterogeneous data sources into CleanContext.

Resolver implementations are strategies that understand different
resource forms (workspace, file paths, raw dicts) and produce a
uniform CleanContext consumed by Planner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from ..bootstrap import discover_user_config
from ..core.workspacemanager import WorkspaceManager
from ..iojson import load_json_file
from ..path_resolver import expand_path


@dataclass
class CleanContext:
    """Uniform resource bundle consumed by Planner.

    Contains only resources (data read from disk / received from caller).
    Does NOT contain derived state (backupinfo, backup_dirs, ignore rules)
    — those are Planner's responsibility.
    """
    final_mapping: list[dict[str, Any]] = field(default_factory=list)
    database: dict[str, Any] = field(default_factory=dict)
    user_config: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Resolver(Protocol):
    """Strategy protocol: resolve a TaskRequest into CleanContext."""

    def resolve(self, request: Any) -> CleanContext:
        ...


class WorkspaceResolver:
    """Resolve from a workspace_id stored in resolver_args."""

    def resolve(self, request: Any) -> CleanContext:
        workspace_id: str = request.resolver_args["workspace_id"]
        user_config, _ = discover_user_config()
        ws_dir = user_config.get("workspace_dir")
        if not ws_dir:
            raise ValueError("workspace_dir is missing from user_config")
        wm = WorkspaceManager(expand_path(ws_dir))

        if not wm.exists(workspace_id):
            raise ValueError(f"workspace {workspace_id} does not exist")

        meta = wm.read_meta(workspace_id)
        mapping = wm.read_mapping(workspace_id)
        database = _resolve_database(meta["database_name"], user_config)

        return CleanContext(
            final_mapping=mapping.get("final_mapping", []),
            database=database,
            user_config=user_config,
        )


class FilePathResolver:
    """Resolve from explicit file paths in resolver_args."""

    def resolve(self, request: Any) -> CleanContext:
        args = request.resolver_args
        mapping = load_json_file(expand_path(args["mapping_path"]))
        database = load_json_file(expand_path(args["database_path"]))
        user_config, _ = discover_user_config()

        return CleanContext(
            final_mapping=mapping.get("final_mapping", []),
            database=database,
            user_config=user_config,
        )


class RawDictResolver:
    """Resolve from inline dicts in resolver_args."""

    def resolve(self, request: Any) -> CleanContext:
        args = request.resolver_args
        user_config = args.get("user_config")
        if user_config is None:
            user_config, _ = discover_user_config()
        return CleanContext(
            final_mapping=args.get("final_mapping", []),
            database=args.get("database", {}),
            user_config=user_config,
        )


def _resolve_database(database_name: str, user_config: dict[str, Any]) -> dict[str, Any]:
    """Load a database file by name from user_config.databases."""
    db_entry = user_config.get("databases", {}).get(database_name)
    if not db_entry:
        raise ValueError(f"database '{database_name}' not found in user_config.databases")
    return load_json_file(expand_path(db_entry["path"]))
