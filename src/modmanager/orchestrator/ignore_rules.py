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
from pathlib import Path
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
) -> IgnoreRuleSet:
    """Collect ignore rules from all three layers.

    Args:
        user_config: The resolved user_config dict.
        source_roots: List of root directories to scan for ``.kmmignore`` files.
                      Each root is walked recursively.

    Returns:
        IgnoreRuleSet ready for matching.
    """
    rules = IgnoreRuleSet()

    # ── Layer 1: hardcoded ─────────────────────────────────────────
    # Already in default; nothing to add.

    # ── Layer 2: user_config.ignore ─────────────────────────────────
    rules.user_patterns = list(user_config.get("ignore", []))

    # ── Layer 3: .kmmignore files ───────────────────────────────────
    for root in source_roots:
        _collect_gitignore_files(Path(root), rules)

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

    # Layer 3: gitignore rules
    # Find the most specific matching gitignore rule set
    gitignore_matched = None
    best_prefix_len = 0
    for root_dir, rule in rules.gitignore_rules.items():
        if path.startswith(root_dir) and len(root_dir) > best_prefix_len:
            gitignore_matched = rule
            best_prefix_len = len(root_dir)

    if gitignore_matched is not None:
        # gitignore_parser's rule objects are callable
        try:
            if gitignore_matched(path):
                return True
        except Exception:
            pass

    return False


# ── Internal helpers ────────────────────────────────────────────────────


def _collect_gitignore_files(root: Path, rules: IgnoreRuleSet) -> None:
    """Walk *root* and parse every ``.kmmignore`` file found.

    Each directory's .kmmignore provides rules applicable to files
    at or below that directory.  We store them keyed by the directory
    path so ``should_ignore`` can select the most specific one.
    """
    if not root.is_dir():
        return

    for dirpath, _dirnames, filenames in os.walk(str(root)):
        if _IGNORE_FILENAME in filenames:
            full_path = os.path.join(dirpath, _IGNORE_FILENAME)
            try:
                parsed = parse_gitignore(full_path)
                rules.gitignore_rules[dirpath + "/"] = parsed
            except Exception:
                pass


def _any_path_component_ends_with(path: str, suffixes: list[str]) -> bool:
    """True if any component of *path* ends with one of *suffixes*."""
    parts = path.replace("\\", "/").split("/")
    return any(
        part.endswith(suffix) for part in parts for suffix in suffixes
    )
