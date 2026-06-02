"""verifier.py — kmm_rule file validation before aggregation.

Part of the bootstrap → verifier path.  Wraps
``rule_validator.validate_kmm_rule_files()`` so it can be called from
bootstrap or directly from pipeline code before ``rule_aggregator.aggregate()``.

Usage::

    passed, rejected, warnings = verify_kmm_rules(["/path/to/rule.kmmrule.json"])
"""

from __future__ import annotations

from ..rule_validator import validate_kmm_rule_files

__all__ = ["verify_kmm_rules"]


def verify_kmm_rules(
    rule_paths: list[str],
) -> tuple[list[str], list[dict], list[dict]]:
    """Two-stage funnel validation for kmm_rule files.

    Delegates to :func:`rule_validator.validate_kmm_rule_files`.

    Args:
        rule_paths:
            Absolute paths to ``*.kmmrule.json`` files.

    Returns:
        ``(passed_paths, rejected, warnings)`` — see
        :func:`rule_validator.validate_kmm_rule_files` for details.
    """
    return validate_kmm_rule_files(rule_paths)
