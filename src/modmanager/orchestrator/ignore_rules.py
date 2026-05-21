"""ignore_rules.py — Planner-owned ignore rule collection and matching.

Encapsulates gitignore_parser and the three-layer ignore rule system:

1. Hardcoded: ``.kmmbackup`` suffix directories
2. User config: ``user_config.ignore`` patterns
3. File rules: ``.kmmignore`` files (gitignore syntax) in source tree

Consumed by Planner to filter final_mapping entries, and by backup_ops
to exclude files from the backupinfo tree scan.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from gitignore_parser import parse_gitignore

# ── Constants ──────────────────────────────────────────────────────────

_HARDCODED_SKIP_SUFFIX = ".kmmbackup"
_IGNORE_FILENAME = ".kmmignore"


# ── Data structures ─────────────────────────────────────────────────────


@dataclass
class IgnoreRuleSet:
    """Collected ignore rules from all three layers."""

    hardcoded_suffixes: list[str] = field(default_factory=lambda: [_HARDCODED_SKIP_SUFFIX])
    user_patterns: list[str] = field(default_factory=list)
    gitignore_rules: dict[str, Any] = field(default_factory=dict)
    # ^ Maps root directory path → parsed gitignore rule object


# ── Public API ──────────────────────────────────────────────────────────


def collect_rules(
    user_config: dict[str, Any],
    source_roots: list[str],
    *,
    relevant_paths: list[str] | None = None,
) -> IgnoreRuleSet:
    """Collect ignore rules from all three layers.

    Args:
        user_config: The resolved user_config dict.
        source_roots: List of root directories that define the scope.
        relevant_paths: Optional list of file paths actually being processed.
            When provided, only directories that are ancestors of these paths
            are scanned for ``.kmmignore`` files, avoiding full-tree walks.

    Returns:
        IgnoreRuleSet ready for matching.
    """
    rules = IgnoreRuleSet()

    # ── Layer 1: hardcoded ─────────────────────────────────────────

    # ── Layer 2: user_config.ignore ─────────────────────────────────
    rules.user_patterns = list(user_config.get("ignore", []))

    # ── Layer 3: .kmmignore files ───────────────────────────────────
    dirs_to_check: set[str] = set()
    if relevant_paths:
        # Only scan directories that are ancestors of relevant files
        for p in relevant_paths:
            d = os.path.dirname(p)
            while d and any(d.startswith(r.rstrip("/")) for r in source_roots):
                dirs_to_check.add(d)
                parent = os.path.dirname(d)
                if parent == d:
                    break
                d = parent
    else:
        # Fallback: walk full source roots (used in tests / standalone)
        for root in source_roots:
            for dirpath, _dirnames, filenames in os.walk(root):
                if _IGNORE_FILENAME in filenames:
                    dirs_to_check.add(dirpath)

    for d in sorted(dirs_to_check):
        ignore_file = os.path.join(d, _IGNORE_FILENAME)
        if os.path.isfile(ignore_file):
            try:
                parsed = parse_gitignore(ignore_file)
                rules.gitignore_rules[d + "/"] = parsed
            except Exception:
                pass

    return rules


def should_ignore(path: str, rules: IgnoreRuleSet) -> bool:
    """Check whether *path* should be excluded based on collected rules.

    Applies all three layers. Returns True on first match.
    """
    # Layer 1: hardcoded suffix
    if _any_path_component_ends_with(path, rules.hardcoded_suffixes):
        return True

    # Layer 2: user patterns (simple suffix matching)
    for pattern in rules.user_patterns:
        if path.endswith(pattern):
            return True

    # Layer 3: gitignore rules — check all matching rule sets from
    # deepest (most specific) to shallowest (least specific).
    # Child .kmmignore rules add to parent rules per standard gitignore
    # semantics; the first match wins.
    matching_rules = sorted(
        [(root_dir, rule) for root_dir, rule in rules.gitignore_rules.items()
         if path.startswith(root_dir)],
        key=lambda x: len(x[0]),
        reverse=True,  # deepest first
    )
    for _root_dir, rule in matching_rules:
        try:
            if rule(path):
                return True
        except Exception:
            pass

    return False


# ── Internal helpers ────────────────────────────────────────────────────


def _any_path_component_ends_with(path: str, suffixes: list[str]) -> bool:
    """True if any component of *path* ends with one of *suffixes*."""
    parts = path.replace("\\", "/").split("/")
    return any(
        part.endswith(suffix) for part in parts for suffix in suffixes
    )
