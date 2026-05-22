"""Entry layer — TaskRequest definition.

The Entry layer defines the canonical request object that all callers
(Web API routes, CLI) must produce before the orchestrator can act.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class Intent(Enum):
    COMPUTE_MAPPING = "compute_mapping"
    BACKUP = "backup"
    APPLY = "apply"
    RESTORE = "restore"
    RUN = "run"


Identity = Literal["web", "cli"]

ResolverType = Literal["workspace", "file_paths", "raw_dict"]


@dataclass
class TaskRequest:
    """Canonical request object produced by Entry and consumed by Orchestrator.

    All callers (Web API, CLI) construct this object identically;
    the orchestrator dispatches based on ``intent``.
    """
    identity: Identity
    intent: Intent
    resolver_type: ResolverType
    resolver_args: dict[str, Any] = field(default_factory=dict)
    flags: dict[str, Any] = field(default_factory=dict)
