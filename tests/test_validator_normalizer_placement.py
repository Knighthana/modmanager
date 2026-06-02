"""Black-box tests for validator / normalizer call-point placement (裁定 5).

Covers T-VN-01 through T-VN-11 from ``repo_test/validator_normalizer_spec.md``.

These tests verify:
  - ``validate_kmm_rule_files()`` is NOT called by ``aggregate()``
  - Instead it's called via bootstrap → verifier before aggregate
  - ``normalize_rule_actions()`` IS called inside ``aggregate()``
  - Path normalization effects (trailing slashes, "path" rejection, ".." rejection)

All tests are **black-box** — they go through the public API
(``aggregate()``, ``verify_kmm_rules()``, ``normalize_rule_actions()``)
without mocking internals.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from modmgr.orchestrator.verifier import verify_kmm_rules
from modmgr.path_normalizer import WARNING_KEY, normalize_rule_actions
from modmgr.rule_aggregator import aggregate


# ===================================================================
# Helpers
# ===================================================================


def _make_kmm_rule(temp_dir: str, filename: str, content: dict) -> str:
    """Write *content* as JSON and return the absolute path."""
    path = Path(temp_dir) / filename
    path.write_text(json.dumps(content, ensure_ascii=False), encoding="utf-8")
    return str(path)


def _valid_rule_dict(
    mixed_id: str = "270150:100",
    def_destin: str = "270150:0",
    def_action: str = "replace",
    actionlist: list[dict] | None = None,
) -> dict:
    """Return a minimal valid kmm_rule dict that passes both validation stages."""
    if actionlist is None:
        actionlist = [
            {
                "from": ["data/file.txt"],
                "from_type": "file",
                "into": ["game_data/"],
                "into_type": "dir",
            }
        ]
    return {
        "schema_namespace": "test",
        "schema_version": "1.0",
        "rule_meta_tag": {"rulenamespace": "test", "rulename": "test_mod"},
        "game": [{"appid": "270150", "modid": ["100"]}],
        "mod": [
            {
                "mixed_id": mixed_id,
                "nickname": "TestMod",
                "def_destin": def_destin,
                "def_action": def_action,
                "actionlist": actionlist,
            }
        ],
    }


# ===================================================================
# T-VN-01: validate_kmm_rule_files is NOT called by aggregate
# ===================================================================


class TestValidatorNotInAggregate:
    """T-VN-01: validate_kmm_rule_files() is NOT called by aggregate().

    Proof: pass a file whose C3 violation (invalid action value) is NOT caught
    by ``normalize_rule_actions`` or ``validate_aggregated_rule_set``.
    ``validate_kmm_rule_files`` would reject it (C3), but ``aggregate()``
    does not.
    """

    def test_aggregate_does_not_call_validator(self) -> None:
        """A file with action='bogus_action' passes aggregate() (no validator inside)."""
        bogus_action = {
            "from": ["data/file.txt"],
            "from_type": "file",
            "into": ["game_data/"],
            "into_type": "dir",
            "action": "bogus_action",  # C3 would reject, but aggregate won't
        }
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "rule.json", _valid_rule_dict(actionlist=[bogus_action]))
            result, errors, warnings = aggregate([path])

        # aggregate should NOT reject this — only validator would.
        assert result is not None, (
            "aggregate() should not reject action='bogus_action' because it "
            "does NOT call validate_kmm_rule_files()"
        )


# ===================================================================
# T-VN-02/03/04: Verifier runs before aggregate, filters files
# ===================================================================


class TestVerifierBeforeAggregate:
    """T-VN-02: validate_kmm_rule_files() called before aggregate via verifier.

    T-VN-03: Only validated files reach aggregate.
    T-VN-04: Rejected files do not appear in aggregator input.
    """

    def test_verifier_passed_paths_reach_aggregate(self) -> None:
        """Validated files passed by verifier reach aggregate successfully."""
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "valid.json", _valid_rule_dict())
            passed, rejected, warnings = verify_kmm_rules([path])

            assert len(passed) == 1
            assert len(rejected) == 0

            # T-VN-03: passed paths go to aggregate
            result, errors, _warnings = aggregate(passed)
            assert result is not None
            assert errors == []

    def test_verifier_rejected_files_do_not_reach_aggregate(self) -> None:
        """Files with C1 violation are rejected by verifier and NOT passed."""
        bad_action = {
            "from": ["data/file.txt"],
            "from_type": "invalid_type",  # C1 violation
            "into": ["game_data/"],
            "into_type": "dir",
        }
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "bad.json", _valid_rule_dict(actionlist=[bad_action]))
            passed, rejected, warnings = verify_kmm_rules([path])

            assert len(passed) == 0, "C1 violation should be rejected"
            assert len(rejected) == 1
            # Error comes from JSON Schema validation (Stage 1), not Stage 2
            err_str = " ".join(str(e) for e in rejected[0].get("errors", []))
            assert "invalid_type" in err_str, (
                f"expected error mentioning 'invalid_type', got: {err_str}"
            )

            # T-VN-04: rejected path does NOT appear in passed
            assert path not in passed

    def test_verifier_rejects_path_type(self) -> None:
        """'path' type is rejected by validator (not by normalizer in aggregate)."""
        path_action = {
            "from": ["data/file.txt"],
            "from_type": "path",  # Should be rejected by validator
            "into": ["game_data/"],
            "into_type": "dir",
        }
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "path_type.json", _valid_rule_dict(actionlist=[path_action]))
            passed, rejected, warnings = verify_kmm_rules([path])

            assert len(passed) == 0, "'path' type should be rejected by validator"
            assert len(rejected) == 1


# ===================================================================
# T-VN-05: normalize_rule_actions IS called inside aggregate
# ===================================================================


class TestNormalizerCalledInAggregate:
    """T-VN-05: normalize_rule_actions() is called inside aggregate().

    Proof: pass a file with from_type='path' — normalizer raises ValueError,
    which aggregate catches and returns as an error.
    """

    def test_aggregate_rejects_path_type_via_normalizer(self) -> None:
        """from_type='path' raises ValueError inside aggregate → error returned."""
        path_action = {
            "from": ["data/file.txt"],
            "from_type": "path",
            "into": ["game_data/"],
            "into_type": "dir",
        }
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "path_type.json", _valid_rule_dict(actionlist=[path_action]))
            result, errors, warnings = aggregate([path])

            assert result is None, "aggregate should reject from_type='path'"
            assert any("path" in e.lower() for e in errors), (
                f"expected error about 'path' type, got: {errors}"
            )

    def test_aggregate_rejects_dotdot(self) -> None:
        """'..' path traversal raises ValueError inside aggregate → error returned."""
        traversal_action = {
            "from": ["data/../file.txt"],
            "from_type": "file",
            "into": ["game_data/"],
            "into_type": "dir",
        }
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "traversal.json", _valid_rule_dict(actionlist=[traversal_action]))
            result, errors, warnings = aggregate([path])

            assert result is None, "aggregate should reject '..' traversal"
            assert any(".." in e for e in errors), (
                f"expected error about '..', got: {errors}"
            )

    def test_aggregate_adds_trailing_slash_dir_from(self) -> None:
        """from_type='dir' with missing trailing / → normalized by aggregate."""
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "rule.json", _valid_rule_dict(
                actionlist=[{
                    "from": ["data/textures"],
                    "from_type": "dir",
                    "into": ["dest/"],
                    "into_type": "dir",
                }]
            ))
            result, errors, warnings = aggregate([path])

            assert result is not None
            op = result["operation"][0]
            action = op["actionlist"][0]
            assert action["from"] == ["data/textures/"], (
                f"expected trailing slash, got {action['from']}"
            )

    def test_aggregate_adds_trailing_slash_dir_into(self) -> None:
        """into_type='dir' with missing trailing / → normalized by aggregate."""
        with tempfile.TemporaryDirectory() as td:
            path = _make_kmm_rule(td, "rule.json", _valid_rule_dict(
                actionlist=[{
                    "from": ["data/file.txt"],
                    "from_type": "file",
                    "into": ["dest/target"],
                    "into_type": "dir",
                }]
            ))
            result, errors, warnings = aggregate([path])

            assert result is not None
            op = result["operation"][0]
            action = op["actionlist"][0]
            assert action["into"] == ["dest/target/"], (
                f"expected trailing slash, got {action['into']}"
            )


# ===================================================================
# T-VN-06: 'path' type is rejected / normalized
# ===================================================================


class TestPathTypeRejection:
    """T-VN-06: 'path' type is rejected by normalizer."""

    def test_normalizer_rejects_path_from_type(self) -> None:
        """from_type='path' → ValueError."""
        rule = {
            "mod": [{"mixed_id": "270150:100", "actionlist": [{"from_type": "path"}]}]
        }
        import pytest
        with pytest.raises(ValueError, match="path"):
            normalize_rule_actions(rule)

    def test_normalizer_rejects_path_into_type(self) -> None:
        """into_type='path' → ValueError."""
        rule = {
            "mod": [{"mixed_id": "270150:100", "actionlist": [{"into_type": "path"}]}]
        }
        import pytest
        with pytest.raises(ValueError, match="path"):
            normalize_rule_actions(rule)


# ===================================================================
# T-VN-07: Trailing slash is complemented
# ===================================================================


class TestTrailingSlashComplement:
    """T-VN-07: trailing / is added by normalizer for dir-type paths."""

    def test_dir_from_gets_slash(self) -> None:
        """from_type='dir', from='data/textures' → 'data/textures/'"""
        rule = {
            "mod": [{
                "mixed_id": "270150:100",
                "actionlist": [{
                    "from": ["data/textures"],
                    "from_type": "dir",
                }],
            }]
        }
        result = normalize_rule_actions(rule)
        action = result["mod"][0]["actionlist"][0]
        assert action["from"] == ["data/textures/"]

    def test_dir_into_gets_slash(self) -> None:
        """into_type='dir', into='dest/target' → 'dest/target/'"""
        rule = {
            "mod": [{
                "mixed_id": "270150:100",
                "actionlist": [{
                    "into": ["dest/target"],
                    "into_type": "dir",
                }],
            }]
        }
        result = normalize_rule_actions(rule)
        action = result["mod"][0]["actionlist"][0]
        assert action["into"] == ["dest/target/"]

    def test_glob_preserved_no_slash(self) -> None:
        """Glob patterns in 'from' with from_type='dir' keep trailing / intact."""
        rule = {
            "mod": [{
                "mixed_id": "270150:100",
                "actionlist": [{
                    "from": ["maps/*/"],
                    "from_type": "dir",
                }],
            }]
        }
        result = normalize_rule_actions(rule)
        action = result["mod"][0]["actionlist"][0]
        assert action["from"] == ["maps/*/"]

    def test_dot_preserved_no_slash(self) -> None:
        """'.' in 'into' with into_type='dir' keeps '.' unchanged."""
        rule = {
            "mod": [{
                "mixed_id": "270150:100",
                "actionlist": [{
                    "into": ["."],
                    "into_type": "dir",
                }],
            }]
        }
        result = normalize_rule_actions(rule)
        action = result["mod"][0]["actionlist"][0]
        assert action["into"] == ["."]


# ===================================================================
# T-VN-08: '..' path traversal is rejected
# ===================================================================


class TestPathTraversalRejection:
    """T-VN-08: '..' traversal is rejected by normalizer."""

    def test_dotdot_from_rejected(self) -> None:
        """from entry with '..' → ValueError."""
        rule = {
            "mod": [{
                "mixed_id": "270150:100",
                "actionlist": [{"from": ["data/../file.txt"]}],
            }]
        }
        import pytest
        with pytest.raises(ValueError, match="E_PATH_TRAVERSAL"):
            normalize_rule_actions(rule)

    def test_dotdot_into_rejected(self) -> None:
        """into entry with '..' → ValueError."""
        rule = {
            "mod": [{
                "mixed_id": "270150:100",
                "actionlist": [{"into": ["../outside"]}],
            }]
        }
        import pytest
        with pytest.raises(ValueError, match="E_PATH_TRAVERSAL"):
            normalize_rule_actions(rule)


# ===================================================================
# T-VN-09/10/11: Documentation consistency (structural checks)
# ===================================================================


class TestDocumentationConsistency:
    """T-VN-09/10/11 — verify design documents reflect the call placement.

    These tests read the relevant design documents and check for key phrases.
    """

    REPO_MEMO_DIR = Path(__file__).resolve().parent.parent / "repo_memo"

    def test_design_rule_validation_mentions_bootstrap_verifier(self) -> None:
        """T-VN-09: DESIGN_RULE_VALIDATION.md mentions bootstrap → verifier."""
        path = self.REPO_MEMO_DIR / "DESIGN_RULE_VALIDATION.md"
        content = path.read_text(encoding="utf-8")
        assert "bootstrap" in content and "verifier" in content, (
            "DESIGN_RULE_VALIDATION.md should mention bootstrap → verifier path"
        )

    def test_design_rule_aggregator_mentions_normalize(self) -> None:
        """T-VN-10: DESIGN_RULE_AGGREGATOR.md §6.3 includes normalize_rule_actions."""
        path = self.REPO_MEMO_DIR / "DESIGN_RULE_AGGREGATOR.md"
        content = path.read_text(encoding="utf-8")
        assert "normalize_rule_actions" in content, (
            "DESIGN_RULE_AGGREGATOR.md §6.3 should mention normalize_rule_actions"
        )

    def test_design_bootstrap_mentions_verifier(self) -> None:
        """T-VN-11: DESIGN_BOOTSTRAP.md includes verifier kmm_rule validation."""
        path = self.REPO_MEMO_DIR / "DESIGN_BOOTSTRAP.md"
        content = path.read_text(encoding="utf-8")
        assert "verifier" in content and "kmm_rule" in content, (
            "DESIGN_BOOTSTRAP.md should mention verifier kmm_rule validation"
        )
