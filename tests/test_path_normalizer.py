"""Tests for modmgr.path_normalizer.normalize_rule_actions.

See ``repo_memo/DESIGN_RULE_VALIDATION.md`` for the semantic refinement spec.
"""

from __future__ import annotations

import pytest

from modmgr.path_normalizer import WARNING_KEY, normalize_rule_actions


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_action(
    from_list: list[str] | None = None,
    from_type: str | None = "file",
    into_list: list[str] | None = None,
    into_type: str | None = "file",
) -> dict:
    """Build a single action dict with optional fields."""
    action: dict = {}
    if from_type is not None:
        action["from_type"] = from_type
    if from_list is not None:
        action["from"] = list(from_list)
    if into_type is not None:
        action["into_type"] = into_type
    if into_list is not None:
        action["into"] = list(into_list)
    return action


def _make_rule(mod_entries: list[dict] | None = None) -> dict:
    """Build a minimal valid kmm_rule dict."""
    return {
        "mod": mod_entries or [
            {
                "mixed_id": "270150:100",
                "actionlist": [],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNormalizeRuleActions:
    """Path normalizer — trailing slash, type check, and traversal safety."""

    # -- trailing slash: from_type='dir' -----------------------------------

    def test_dir_path_gets_trailing_slash(self) -> None:
        """from_type='dir' with missing trailing / → appended + warning."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/textures"],
                        from_type="dir",
                        into_list=["dest/"],
                        into_type="dir",
                    )
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])

        action = result["mod"][0]["actionlist"][0]
        assert action["from"] == ["data/textures/"]
        assert warnings == ["W_PATH_TRAILING_SLASH_ADDED: data/textures"]

    def test_into_dir_path_gets_trailing_slash(self) -> None:
        """into_type='dir' with missing trailing / → appended + warning."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/textures/"],
                        from_type="dir",
                        into_list=["dest/models"],
                        into_type="dir",
                    )
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])

        action = result["mod"][0]["actionlist"][0]
        assert action["into"] == ["dest/models/"]
        assert warnings == ["W_PATH_TRAILING_SLASH_ADDED: dest/models"]

    def test_file_type_no_trailing_slash(self) -> None:
        """from_type='file' paths are not modified."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/file.txt"],
                        from_type="file",
                        into_list=["dest/file.txt"],
                        into_type="file",
                    )
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])

        action = result["mod"][0]["actionlist"][0]
        assert action["from"] == ["data/file.txt"]  # unchanged
        assert action["into"] == ["dest/file.txt"]  # unchanged
        assert warnings == []

    # -- 'path' type rejection ---------------------------------------------

    def test_path_type_rejected(self) -> None:
        """from_type='path' → ValueError."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/whatever"],
                        from_type="path",
                    )
                ],
            }
        ])
        with pytest.raises(ValueError) as exc:
            normalize_rule_actions(rule)
        assert "E_INVALID_TYPE" in str(exc.value)
        assert "from_type" in str(exc.value)
        assert "path" in str(exc.value)

    def test_into_path_type_rejected(self) -> None:
        """into_type='path' → ValueError."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        into_list=["data/whatever"],
                        into_type="path",
                    )
                ],
            }
        ])
        with pytest.raises(ValueError) as exc:
            normalize_rule_actions(rule)
        assert "E_INVALID_TYPE" in str(exc.value)
        assert "into_type" in str(exc.value)
        assert "path" in str(exc.value)

    # -- path traversal rejection ------------------------------------------

    def test_path_traversal_rejected(self) -> None:
        """from path with '..' → ValueError."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/../evil.txt"],
                        from_type="file",
                    )
                ],
            }
        ])
        with pytest.raises(ValueError) as exc:
            normalize_rule_actions(rule)
        assert "E_PATH_TRAVERSAL" in str(exc.value)
        assert ".." in str(exc.value)

    def test_into_path_traversal_rejected(self) -> None:
        """into path with '..' → ValueError."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        into_list=["dest/../../etc"],
                        into_type="file",
                    )
                ],
            }
        ])
        with pytest.raises(ValueError) as exc:
            normalize_rule_actions(rule)
        assert "E_PATH_TRAVERSAL" in str(exc.value)
        assert ".." in str(exc.value)

    def test_path_traversal_in_dir_type(self) -> None:
        """from_type='dir' with '..' is still rejected."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["safe/../textures"],
                        from_type="dir",
                    )
                ],
            }
        ])
        with pytest.raises(ValueError) as exc:
            normalize_rule_actions(rule)
        assert "E_PATH_TRAVERSAL" in str(exc.value)

    # -- valid rule passes -------------------------------------------------

    def test_valid_rule_passes_unchanged(self) -> None:
        """Already correct rule passes without warnings."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/textures/"],
                        from_type="dir",
                        into_list=["dest/textures/"],
                        into_type="dir",
                    )
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])

        action = result["mod"][0]["actionlist"][0]
        assert action["from"] == ["data/textures/"]
        assert action["into"] == ["dest/textures/"]
        assert warnings == []

    def test_empty_actionlist_noop(self) -> None:
        """Mod with empty actionlist produces no warnings and no crash."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])
        assert warnings == []

    # -- multiple warnings -------------------------------------------------

    def test_multiple_warnings_collected(self) -> None:
        """Multiple fixable issues all get warnings."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/textures", "data/meshes"],
                        from_type="dir",
                        into_list=["dest/target"],
                        into_type="dir",
                    )
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])

        action = result["mod"][0]["actionlist"][0]
        assert action["from"] == ["data/textures/", "data/meshes/"]
        assert action["into"] == ["dest/target/"]
        # Three entries needed trailing slash → three warnings
        assert len(warnings) == 3
        assert "W_PATH_TRAILING_SLASH_ADDED: data/textures" in warnings
        assert "W_PATH_TRAILING_SLASH_ADDED: data/meshes" in warnings
        assert "W_PATH_TRAILING_SLASH_ADDED: dest/target" in warnings

    def test_multiple_actions_warnings(self) -> None:
        """Multiple actions each produce their own warnings."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["a"],
                        from_type="dir",
                        into_list=["b"],
                        into_type="dir",
                    ),
                    _make_action(
                        from_list=["c"],
                        from_type="dir",
                        into_list=["d"],
                        into_type="dir",
                    ),
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])
        assert len(warnings) == 4
        assert "W_PATH_TRAILING_SLASH_ADDED: a" in warnings
        assert "W_PATH_TRAILING_SLASH_ADDED: b" in warnings
        assert "W_PATH_TRAILING_SLASH_ADDED: c" in warnings
        assert "W_PATH_TRAILING_SLASH_ADDED: d" in warnings

    # -- already correct trailing slash ------------------------------------

    def test_dir_path_already_has_slash(self) -> None:
        """from_type='dir' with trailing / already present → no warning."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        from_list=["data/textures/"],
                        from_type="dir",
                    )
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])
        assert warnings == []

    def test_into_dir_path_already_has_slash(self) -> None:
        """into_type='dir' with trailing / already present → no warning."""
        rule = _make_rule([
            {
                "mixed_id": "270150:100",
                "actionlist": [
                    _make_action(
                        into_list=["dest/textures/"],
                        into_type="dir",
                    )
                ],
            }
        ])
        result = normalize_rule_actions(rule)
        warnings = result.pop(WARNING_KEY, [])
        assert warnings == []
