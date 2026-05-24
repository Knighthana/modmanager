"""Preprocessor that normalizes kmm_rule file content before aggregation.

This module implements the semantic refinement / path normalization layer
of the rule file pre-check funnel (see ``DESIGN_RULE_VALIDATION.md``).
It runs before the aggregator (``rule_aggregator.py``) and handles:

* Rejection of ``"path"`` type (must be ``"file"`` or ``"dir"``)
* Trailing-slash enforcement for ``"dir"``-type paths
* Directory traversal (``".."``) rejection
"""

from __future__ import annotations

from typing import Any

__all__ = ["normalize_rule_actions"]

WARNING_KEY = "_normalize_warnings"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_rule_actions(rule_data: dict) -> dict:
    """Normalize all actionlist entries in a kmm_rule dict.

    Performs:
    1. **'path' type rejection** — if *from_type* or *into_type* is ``"path"``,
       raise :class:`ValueError` with a descriptive message.
    2. **Dir path trailing slash** — when *from_type* is ``"dir"``, ensure each
       ``from`` entry ends with ``/``; when *into_type* is ``"dir"``, ensure
       each ``into`` entry ends with ``/``.  Missing slashes are appended and
       recorded as warnings.
    3. **Path safety** — reject entries containing ``".."`` (directory
       traversal) with :class:`ValueError`.
    4. Returns the normalized dict with warnings attached under
       ``_normalize_warnings``.

    Parameters
    ----------
    rule_data:
        A raw kmm_rule dict (must contain a ``"mod"`` list).

    Returns
    -------
    dict
        The *same* dict (modified in-place).  Callers should retrieve warnings
        via ``rule_data.pop("_normalize_warnings", [])``.

    Raises
    ------
    ValueError
        If a ``from_type`` / ``into_type`` is ``"path"`` or if any path entry
        contains ``".."``.
    """
    warnings: list[str] = []
    mod_entries = rule_data.get("mod", [])

    if not isinstance(mod_entries, list):
        rule_data[WARNING_KEY] = warnings
        return rule_data

    for mod_idx, mod_entry in enumerate(mod_entries):
        if not isinstance(mod_entry, dict):
            continue

        actionlist = mod_entry.get("actionlist", [])
        if not isinstance(actionlist, list):
            continue

        for action_idx, action_item in enumerate(actionlist):
            if not isinstance(action_item, dict):
                continue

            from_type = action_item.get("from_type")
            into_type = action_item.get("into_type")

            # ---- 1. 'path' type rejection ---------------------------------
            if from_type == "path":
                raise ValueError(
                    "E_INVALID_TYPE: 'path' is not a valid from_type. "
                    "Use 'file' or 'dir'."
                )
            if into_type == "path":
                raise ValueError(
                    "E_INVALID_TYPE: 'path' is not a valid into_type. "
                    "Use 'file' or 'dir'."
                )

            # ---- 3. Path safety (directory traversal) ---------------------
            # Check *all* entries regardless of type setting.
            from_list = action_item.get("from")
            if isinstance(from_list, list):
                for entry in from_list:
                    if isinstance(entry, str) and ".." in entry.split("/"):
                        raise ValueError(
                            f"E_PATH_TRAVERSAL: from entry '{entry}' "
                            f"contains '..'"
                        )

            into_list = action_item.get("into")
            if isinstance(into_list, list):
                for entry in into_list:
                    if isinstance(entry, str) and ".." in entry.split("/"):
                        raise ValueError(
                            f"E_PATH_TRAVERSAL: into entry '{entry}' "
                            f"contains '..'"
                        )

            # ---- 2. Dir path trailing slash -------------------------------
            if from_type == "dir":
                fixed_from: list[str] = []
                raw_from = action_item.get("from", [])
                if isinstance(raw_from, list):
                    for entry in raw_from:
                        if isinstance(entry, str) and not entry.endswith("/"):
                            warnings.append(
                                f"W_PATH_TRAILING_SLASH_ADDED: {entry}"
                            )
                            fixed_from.append(entry + "/")
                        else:
                            fixed_from.append(entry)
                action_item["from"] = fixed_from

            if into_type == "dir":
                fixed_into: list[str] = []
                raw_into = action_item.get("into", [])
                if isinstance(raw_into, list):
                    for entry in raw_into:
                        if isinstance(entry, str) and not entry.endswith("/"):
                            warnings.append(
                                f"W_PATH_TRAILING_SLASH_ADDED: {entry}"
                            )
                            fixed_into.append(entry + "/")
                        else:
                            fixed_into.append(entry)
                action_item["into"] = fixed_into

    rule_data[WARNING_KEY] = warnings
    return rule_data
