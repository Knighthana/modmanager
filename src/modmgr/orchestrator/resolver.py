"""Resolver layer — pure parsing: TaskRequest → SourceDescriptor.

Resolvers perform NO I/O. They extract field values from ``TaskRequest``
and produce a ``SourceDescriptor`` that the DataPort uses to read data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@runtime_checkable
class Resolver(Protocol):
    """Strategy protocol: resolve a TaskRequest into SourceDescriptor."""

    def resolve(self, request: Any) -> Any:
        ...


class WorkspaceResolver:
    """Resolve from a workspace_id — pure parsing, no I/O."""

    def resolve(self, request: Any) -> Any:
        workspace_id: str = request.resolver_args["workspace_id"]
        config_index: str = request.resolver_args.get("config_index", "")
        # Avoid circular import at module level
        from .data_port import SourceDescriptor

        return SourceDescriptor(
            source_type="workspace",
            workspace_id=workspace_id,
            config_index=config_index,
        )


class FilePathResolver:
    """Resolve from explicit file paths — pure parsing, no I/O."""

    def resolve(self, request: Any) -> Any:
        args = request.resolver_args
        from .data_port import SourceDescriptor

        return SourceDescriptor(
            source_type="file_paths",
            database_path=args["database_path"],
            config_index=args.get("config_index", ""),
        )


class RawDictResolver:
    """Resolve from inline dicts — pure passthrough, no I/O."""

    def resolve(self, request: Any) -> Any:
        args = request.resolver_args
        from .data_port import SourceDescriptor

        return SourceDescriptor(
            source_type="raw_dict",
            database_dict=args.get("database", {}),
            aggregated_rule_set=args.get("aggregated_rule_set"),
        )
