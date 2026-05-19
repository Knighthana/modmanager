"""workspacemanager — Workspace lifecycle manager.

An orchestrator subordinate responsible for workspace directory CRUD,
metadata management, and reading/writing workspace artifacts (rules,
decisions, mapping, SVG, fingerprints).

Design doc: ``repo_memo/DESIGN_WORKSPACE_MODEL.md``
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..iojson import load_json_file, write_json_file

__all__ = ["WorkspaceManager"]


class WorkspaceManager:
    """Manage workspace directories and their contents.

    A workspace is a pre-created container identified by a unique
    ``workspace_id`` (SHA256 hex truncated to 24 chars).  All user
    decisions, aggregated rules, compute results, and fingerprints
    live inside ``{workspace_dir}/{workspace_id}/``.

    Directory layout (MVP)::

        {workspace_dir}/{workspace_id}/
            meta.json
            aggregated_rule.json
            decisions.json
            mapping.json
            forest.svg
            fingerprints.json
    """

    # ── file names (class-level for consistency) ─────────────────────
    _META = "meta.json"
    _AGGREGATED_RULE = "aggregated_rule.json"
    _DECISIONS = "decisions.json"
    _MAPPING = "mapping.json"
    _SVG = "forest.svg"
    _FINGERPRINTS = "fingerprints.json"

    def __init__(self, workspace_dir: str | Path) -> None:
        """*workspace_dir* – absolute path to the workspace root directory."""
        self._root = Path(workspace_dir)

    # ── public API ───────────────────────────────────────────────────

    # -- lifecycle -----------------------------------------------------

    def create(self, name: str, database_name: str) -> str:
        """Create a new workspace directory with ``meta.json``.

        Returns:
            The generated ``workspace_id``.
        """
        workspace_id = self._generate_id(name)
        ws_dir = self._dir(workspace_id)
        ws_dir.mkdir(parents=True, exist_ok=False)

        now = _utcnow()
        meta = {
            "workspace_id": workspace_id,
            "name": name,
            "database_name": database_name,
            "created_at": now,
            "updated_at": now,
            "app_version": _app_version(),
        }
        write_json_file(ws_dir / self._META, meta)
        return workspace_id

    def delete(self, workspace_id: str) -> None:
        """Recursively delete a workspace directory.

        Does nothing silently if the directory does not exist.
        """
        import shutil

        ws_dir = self._dir(workspace_id)
        if ws_dir.exists():
            shutil.rmtree(ws_dir)

    def list_all(self) -> list[dict[str, Any]]:
        """Return meta dicts for every workspace, newest first."""
        result: list[dict[str, Any]] = []
        if not self._root.exists():
            return result
        for child in sorted(self._root.iterdir(), key=_mtime, reverse=True):
            if not child.is_dir():
                continue
            meta_path = child / self._META
            if not meta_path.is_file():
                continue
            try:
                result.append(load_json_file(meta_path))
            except Exception:
                continue
        return result

    def read_meta(self, workspace_id: str) -> dict[str, Any]:
        """Read ``meta.json`` for a workspace."""
        return load_json_file(self._dir(workspace_id) / self._META)

    def exists(self, workspace_id: str) -> bool:
        """Check whether a workspace directory exists on disk."""
        return self._dir(workspace_id).is_dir()

    # -- touch ---------------------------------------------------------

    def _touch(self, workspace_id: str) -> None:
        """Update ``updated_at`` in meta.json."""
        ws_dir = self._dir(workspace_id)
        meta_path = ws_dir / self._META
        meta = load_json_file(meta_path) if meta_path.is_file() else {}
        meta["updated_at"] = _utcnow()
        write_json_file(meta_path, meta)

    # -- aggregated rule -----------------------------------------------

    def write_aggregated_rule(self, workspace_id: str, rule_set: dict[str, Any]) -> None:
        write_json_file(self._dir(workspace_id) / self._AGGREGATED_RULE, rule_set)
        self._touch(workspace_id)

    def read_aggregated_rule(self, workspace_id: str) -> dict[str, Any]:
        return load_json_file(self._dir(workspace_id) / self._AGGREGATED_RULE)

    def has_aggregated_rule(self, workspace_id: str) -> bool:
        return (self._dir(workspace_id) / self._AGGREGATED_RULE).is_file()

    # -- decisions -----------------------------------------------------

    def write_decisions(self, workspace_id: str, decisions: dict[str, Any]) -> None:
        write_json_file(self._dir(workspace_id) / self._DECISIONS, decisions)
        self._touch(workspace_id)

    def read_decisions(self, workspace_id: str) -> dict[str, Any]:
        return load_json_file(self._dir(workspace_id) / self._DECISIONS)

    def has_decisions(self, workspace_id: str) -> bool:
        return (self._dir(workspace_id) / self._DECISIONS).is_file()

    # -- mapping -------------------------------------------------------

    def write_mapping(self, workspace_id: str, mapping: dict[str, Any]) -> None:
        write_json_file(self._dir(workspace_id) / self._MAPPING, mapping)
        self._touch(workspace_id)

    def read_mapping(self, workspace_id: str) -> dict[str, Any]:
        return load_json_file(self._dir(workspace_id) / self._MAPPING)

    def has_mapping(self, workspace_id: str) -> bool:
        return (self._dir(workspace_id) / self._MAPPING).is_file()

    # -- SVG -----------------------------------------------------------

    def write_svg(self, workspace_id: str, svg_content: str) -> None:
        p = self._dir(workspace_id) / self._SVG
        p.write_text(svg_content, encoding="utf-8")
        self._touch(workspace_id)

    def read_svg(self, workspace_id: str) -> str:
        p = self._dir(workspace_id) / self._SVG
        return p.read_text(encoding="utf-8")

    def has_svg(self, workspace_id: str) -> bool:
        return (self._dir(workspace_id) / self._SVG).is_file()

    # -- fingerprints --------------------------------------------------

    def write_fingerprints(self, workspace_id: str, fingerprints: dict[str, Any]) -> None:
        write_json_file(self._dir(workspace_id) / self._FINGERPRINTS, fingerprints)
        self._touch(workspace_id)

    def read_fingerprints(self, workspace_id: str) -> dict[str, Any]:
        return load_json_file(self._dir(workspace_id) / self._FINGERPRINTS)

    # ── internal helpers ─────────────────────────────────────────────

    def _dir(self, workspace_id: str) -> Path:
        return self._root / workspace_id

    @staticmethod
    def _generate_id(name: str) -> str:
        """Generate a stable workspace_id from *name* + timestamp."""
        seed = f"{name}:{time.time_ns()}".encode("utf-8")
        return hashlib.sha256(seed).hexdigest()[:24]


# ── module-level helpers ───────────────────────────────────────────


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mtime(entry: Path) -> float:
    try:
        return entry.stat().st_mtime
    except OSError:
        return 0.0


def _app_version() -> str:
    """Return the application version string, or '0.0.0' if unavailable."""
    try:
        from .. import __version__  # type: ignore[attr-defined]
        return __version__
    except Exception:
        return "0.0.0"
