"""Tests for orchestrator/ignore_rules — ignore rule collection and matching."""

import os
import tempfile
from pathlib import Path

import pytest

from modmgr.orchestrator.ignore_rules import (
    IgnoreRuleSet,
    collect_rules,
    should_ignore,
)


class TestCollectRules:
    """collect_rules() — three-layer rule collection."""

    def test_hardcoded_suffix_always_present(self):
        """Hardcoded .kmmbackup suffix is always in the rule set."""
        rules = collect_rules({}, [])
        assert ".kmmbackup" in rules.hardcoded_suffixes

    def test_user_ignore_patterns(self):
        """user_config.kmmignore patterns are collected."""
        rules = collect_rules({"kmmignore": [".log", ".tmp"]}, [])
        assert ".log" in rules.user_patterns
        assert ".tmp" in rules.user_patterns

    def test_kmmignore_file_parsed(self):
        """.kmmignore file with gitignore syntax is parsed."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".kmmignore").write_text("*.cache\n")
            (root / "subdir").mkdir()
            (root / "subdir" / ".kmmignore").write_text("*.tmp\n")

            rules = collect_rules({}, [str(root)])
            assert len(rules.gitignore_rules) == 2

    def test_empty_config_produces_valid_rules(self):
        """Empty user_config produces a valid IgnoreRuleSet."""
        rules = collect_rules({}, [])
        assert isinstance(rules, IgnoreRuleSet)
        assert rules.hardcoded_suffixes == [".kmmbackup"]


class TestShouldIgnore:
    """should_ignore() — three-layer matching."""

    def test_hardcoded_suffix_matched(self):
        """Paths ending with .kmmbackup are ignored."""
        rules = IgnoreRuleSet()
        assert should_ignore("/path/to/123.kmmbackup/file.txt", rules)
        assert should_ignore("/path/.kmmbackup", rules)

    def test_user_pattern_matched(self):
        """Paths ending with user patterns are ignored."""
        rules = IgnoreRuleSet(user_patterns=[".log"])
        assert should_ignore("/path/to/error.log", rules)
        assert not should_ignore("/path/to/file.txt", rules)

    def test_gitignore_rule_matched(self):
        """.kmmignore rules are matched via gitignore-parser."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".kmmignore").write_text("*.cache\n")
            (root / "subdir").mkdir()

            rules = collect_rules({}, [str(root)])
            assert should_ignore(str(root / "foo.cache"), rules)
            assert should_ignore(str(root / "subdir" / "bar.cache"), rules)
            assert not should_ignore(str(root / "keep.txt"), rules)

    def test_normal_file_not_ignored(self):
        """Normal files are not matched by any layer."""
        rules = IgnoreRuleSet()
        assert not should_ignore("/path/to/file.txt", rules)

    def test_gitignore_cascade_parent_and_child(self):
        """Parent and child .kmmignore rules both apply (gitignore cascading)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Parent rule: ignore *.log
            (root / ".kmmignore").write_text("*.log\n")
            # Child rule: ignore *.tmp (adds to parent, not replaces)
            sub = root / "sub"
            sub.mkdir()
            (sub / ".kmmignore").write_text("*.tmp\n")

            rules = collect_rules({}, [str(root)])
            # Parent rule applies to files in subdirectory
            assert should_ignore(str(sub / "error.log"), rules)
            # Child rule applies
            assert should_ignore(str(sub / "data.tmp"), rules)
            # Unmatched file
            assert not should_ignore(str(sub / "keep.txt"), rules)
