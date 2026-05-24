"""Two-stage validation funnel for kmm_rule files.

Stage 1: JSON Schema validation against kmm_rule.schema.json.
Stage 2: Semantic checks (C1-C10 from DESIGN_RULE_VALIDATION.md).

Usage::

    passed, rejected, warnings = validate_kmm_rule_files(["/path/to/rule.kmmrule.json"])
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from .iojson import load_json_file

__all__ = ["validate_kmm_rule_files"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error / warning codes
# ---------------------------------------------------------------------------
E_INVALID_FROM_TYPE = "E_INVALID_FROM_TYPE"
E_INVALID_INTO_TYPE = "E_INVALID_INTO_TYPE"
E_INVALID_ACTION = "E_INVALID_ACTION"
E_PATH_TRAVERSAL = "E_PATH_TRAVERSAL"
E_MISSING_FROM = "E_MISSING_FROM"
E_MISSING_INTO = "E_MISSING_INTO"
W_MIXED_ID_FORMAT = "W_MIXED_ID_FORMAT"
W_DESTIN_FORMAT = "W_DESTIN_FORMAT"
W_SUB_FORMAT = "W_SUB_FORMAT"

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------
_MIXED_ID_RE = re.compile(r"^\d+:.+$")
_DESTIN_RE = re.compile(r"^\d+:(0|.+)$")
_SUB_RE = re.compile(r"^\d+:.+$")  # same as mixed_id

# ---------------------------------------------------------------------------
# Valid value sets
# ---------------------------------------------------------------------------
_VALID_FROM_TYPES: frozenset[str] = frozenset({"file", "dir"})
_VALID_INTO_TYPES: frozenset[str] = frozenset({"file", "dir"})
_VALID_ACTIONS: frozenset[str] = frozenset(
    {"hold", "replace", "copy", "delete", "create"}
)

# ---------------------------------------------------------------------------
# Schema path
# ---------------------------------------------------------------------------
_KMM_RULE_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "repo_spec"
    / "kmm_rule.schema.json"
)


# ===================================================================
# Public API
# ===================================================================


def validate_kmm_rule_files(
    rule_paths: list[str],
) -> tuple[list[str], list[dict], list[dict]]:
    """Two-stage funnel validation for kmm_rule files.

    Stage 1 — JSON Schema validation (structural).
    Stage 2 — Semantic checks C1–C10 (field values, path safety, format).

    Returns:
        ``(passed_paths, rejected, warnings)``

        *passed_paths* — file paths that pass both stages (usable).
        *rejected*     — ``[{path, errors: [str]}]`` fatal issues.
        *warnings*     — ``[{path, warnings: [str]}]`` non-fatal issues
                         (file is usable but should be reviewed).
    """
    # -- Soft dependency: jsonschema ------------------------------------------
    jsonschema = _import_jsonschema()

    # -- Load schema once -----------------------------------------------------
    schema: dict[str, Any] | None = None
    if jsonschema is not None:
        try:
            schema = json.loads(_KMM_RULE_SCHEMA_PATH.read_text(encoding="utf-8"))
        except Exception:
            logger.warning(
                "Failed to load schema at %s; skipping Stage 1", _KMM_RULE_SCHEMA_PATH
            )

    passed_paths: list[str] = []
    rejected: list[dict] = []
    warnings_list: list[dict] = []

    for path in rule_paths:
        # -- Load file --------------------------------------------------------
        try:
            data = load_json_file(path)
        except FileNotFoundError:
            rejected.append({"path": path, "errors": ["File not found"]})
            continue
        except json.JSONDecodeError as exc:
            rejected.append(
                {"path": path, "errors": [f"JSON decode error: {exc}"]}
            )
            continue
        except Exception as exc:
            rejected.append(
                {"path": path, "errors": [f"Failed to load file: {exc}"]}
            )
            continue

        # -- Stage 1: Schema validation ---------------------------------------
        if jsonschema is not None and schema is not None:
            try:
                jsonschema.validate(instance=data, schema=schema)
            except jsonschema.ValidationError as exc:
                rejected.append({"path": path, "errors": [str(exc)]})
                continue
            except Exception as exc:
                rejected.append(
                    {"path": path, "errors": [f"Schema validation error: {exc}"]}
                )
                continue

        # -- Stage 2: Semantic checks -----------------------------------------
        file_errors: list[str] = []
        file_warnings: list[str] = []

        mod_entries = data.get("mod", [])
        if not isinstance(mod_entries, list):
            rejected.append({"path": path, "errors": ["'mod' must be a list"]})
            continue

        for mod_entry in mod_entries:
            if not isinstance(mod_entry, dict):
                continue

            _check_mod_entry(mod_entry, file_errors, file_warnings)

        if file_errors:
            rejected.append({"path": path, "errors": file_errors})
        else:
            passed_paths.append(path)
            if file_warnings:
                warnings_list.append({"path": path, "warnings": file_warnings})

    return passed_paths, rejected, warnings_list


# ===================================================================
# Helpers
# ===================================================================


def _import_jsonschema() -> Any:
    """Try to import *jsonschema*; return *None* if unavailable."""
    try:
        import jsonschema  # noqa: F811

        return jsonschema
    except ImportError:
        logger.warning("jsonschema not installed; skipping Stage 1 schema validation")
        return None


def _check_mod_entry(
    entry: dict[str, Any],
    file_errors: list[str],
    file_warnings: list[str],
) -> None:
    """Run C1–C10 checks on a single mod entry (including its actionlist)."""
    # --- C8: mixed_id format ---
    mixed_id = entry.get("mixed_id")
    if isinstance(mixed_id, str) and not _MIXED_ID_RE.match(mixed_id):
        file_warnings.append(f"{W_MIXED_ID_FORMAT}: {mixed_id}")

    # --- C9: def_destin format ---
    def_destin = entry.get("def_destin")
    if isinstance(def_destin, str) and not _DESTIN_RE.match(def_destin):
        file_warnings.append(f"{W_DESTIN_FORMAT}: {def_destin}")

    # --- C10: sub[] entries format ---
    sub_entries = entry.get("sub")
    if isinstance(sub_entries, list):
        for sub_entry in sub_entries:
            if isinstance(sub_entry, str) and not _SUB_RE.match(sub_entry):
                file_warnings.append(f"{W_SUB_FORMAT}: {sub_entry}")

    # --- Check actionlist ---
    actionlist = entry.get("actionlist")
    if not isinstance(actionlist, list):
        return

    for action_entry in actionlist:
        if not isinstance(action_entry, dict):
            continue
        _check_action_entry(action_entry, file_errors, file_warnings)


def _check_action_entry(
    entry: dict[str, Any],
    file_errors: list[str],
    file_warnings: list[str],
) -> None:
    """Run C1–C7 checks on a single RawAction entry."""
    action = entry.get("action")

    # --- C3: action value ---
    if isinstance(action, str) and action not in _VALID_ACTIONS:
        file_errors.append(f"{E_INVALID_ACTION}: {action}")

    # --- C1: from_type value ---
    from_type = entry.get("from_type")
    if isinstance(from_type, str) and from_type not in _VALID_FROM_TYPES:
        file_errors.append(f"{E_INVALID_FROM_TYPE}: {from_type}")

    # --- C2: into_type value ---
    into_type = entry.get("into_type")
    if isinstance(into_type, str) and into_type not in _VALID_INTO_TYPES:
        file_errors.append(f"{E_INVALID_INTO_TYPE}: {into_type}")

    # --- C4: from path traversal ---
    from_paths = entry.get("from")
    if isinstance(from_paths, list):
        for fp in from_paths:
            if isinstance(fp, str) and ".." in fp:
                file_errors.append(
                    f"{E_PATH_TRAVERSAL}: from path '{fp}'"
                )
                break  # one error per entry is enough

    # --- C5: into path traversal ---
    into_paths = entry.get("into")
    if isinstance(into_paths, list):
        for ip in into_paths:
            if isinstance(ip, str) and ".." in ip:
                file_errors.append(
                    f"{E_PATH_TRAVERSAL}: into path '{ip}'"
                )
                break

    # --- C6: from non-empty for non-delete, non-hold actions ---
    if isinstance(action, str) and action not in ("delete", "hold"):
        _from = entry.get("from")
        if _from is None or (isinstance(_from, list) and len(_from) == 0):
            file_errors.append(E_MISSING_FROM)

    # --- C7: into non-empty for non-hold actions ---
    if isinstance(action, str) and action != "hold":
        _into = entry.get("into")
        if _into is None or (isinstance(_into, list) and len(_into) == 0):
            file_errors.append(E_MISSING_INTO)
