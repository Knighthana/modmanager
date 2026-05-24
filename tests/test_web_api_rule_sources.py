"""Tests for POST /api/rules/list-sources and POST /api/rules/scan-by-source.

These endpoints implement the ``rule_sources`` → name-based lookup pattern
described in ``SPEC_RULE_SOURCES.md``.

Endpoints do not exist yet; tests will FAIL until implementation is complete.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from modmgr_web.app import create_app


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """Build a fresh TestClient for each test."""
    app = create_app()
    return TestClient(app)


def _valid_rule_content() -> str:
    """Return minimal valid ``.kmmrule.json`` content."""
    return json.dumps({
        "schema_namespace": "KMM_Rule",
        "schema_version": "knighthana@0.1.0",
        "rule_meta_tag": {
            "rulenamespace": "test",
            "rulename": "test",
            "author": [],
            "description": "",
        },
        "game": [{"appid": "270150", "modid": ["100"]}],
        "mod": [],
    })


# ── POST /api/rules/list-sources ──────────────────────────────────────────


class TestListSources:
    """POST /api/rules/list-sources — list available rule source names."""

    def test_list_sources_returns_all_keys(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T1: Mock rule_sources with two entries → both names returned."""
        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: (
                {
                    "rule_sources": {
                        "default": {"paths": ["/some/path/"]},
                        "custom": {"paths": ["/other/path/"]},
                    }
                },
                config_index,
            ),
        )
        resp = client.post("/api/rules/list-sources", json={"config_index": "/fake/config.json"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert sorted(body["data"]["source_names"]) == ["custom", "default"]
        assert body["errors"] == []

    def test_list_sources_empty_rule_sources(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T2: Empty ``rule_sources`` → empty ``source_names`` list."""
        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: ({"rule_sources": {}}, config_index),
        )
        resp = client.post("/api/rules/list-sources", json={"config_index": "/fake/config.json"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["source_names"] == []
        assert body["errors"] == []


# ── POST /api/rules/scan-by-source ────────────────────────────────────────


class TestScanBySource:
    """POST /api/rules/scan-by-source — scan a named rule source for files."""

    def test_scan_known_source_with_directories(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T3: Known source name pointing to a directory → files returned with name/path/size."""
        rule_file = tmp_path / "test_rule.kmmrule.json"
        rule_file.write_text(_valid_rule_content())
        another = tmp_path / "another.kmmrule.json"
        another.write_text(_valid_rule_content())
        # Non-rule files should be ignored
        (tmp_path / "readme.txt").write_text("hello")

        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: (
                {
                    "rule_sources": {
                        "default": {
                            "paths": [str(tmp_path) + "/"]  # trailing / marks directory
                        }
                    }
                },
                config_index,
            ),
        )

        resp = client.post(
            "/api/rules/scan-by-source",
            json={"source_name": "default", "config_index": "/fake/config.json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        files = body["data"]["files"]
        assert len(files) == 2
        names = [f["name"] for f in files]
        assert "test_rule.kmmrule.json" in names
        assert "another.kmmrule.json" in names
        for f in files:
            assert "path" in f
            assert "size" in f
            assert f["size"] > 0
        assert body["data"]["source_name"] == "default"
        assert body["errors"] == []

    def test_scan_unknown_source_name(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T4: Unknown ``source_name`` → ``ok: false`` + ``E_SOURCE_NOT_FOUND``."""
        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: (
                {
                    "rule_sources": {
                        "default": {"paths": ["/some/path/"]},
                    }
                },
                config_index,
            ),
        )
        resp = client.post(
            "/api/rules/scan-by-source",
            json={"source_name": "nonexistent", "config_index": "/fake/config.json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        # The error key must contain E_SOURCE_NOT_FOUND (exact code per SPEC)
        assert any("E_SOURCE_NOT_FOUND" in e for e in body["errors"])

    def test_scan_mixed_dir_and_file_paths(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T5: Mixed paths (directory + standalone file) → both types appear."""
        # Create a sub-directory with a rule file inside
        sub_dir = tmp_path / "rules_dir"
        sub_dir.mkdir()
        rule_in_dir = sub_dir / "from_dir.kmmrule.json"
        rule_in_dir.write_text(_valid_rule_content())

        # Create a standalone rule file outside the directory
        standalone = tmp_path / "standalone.kmmrule.json"
        standalone.write_text(_valid_rule_content())

        # Irrelevant file that should NOT appear
        (tmp_path / "config.txt").write_text("irrelevant")

        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: (
                {
                    "rule_sources": {
                        "mixed": {
                            "paths": [
                                str(sub_dir) + "/",  # directory path (trailing /)
                                str(standalone),      # file path (no trailing /)
                            ]
                        }
                    }
                },
                config_index,
            ),
        )

        resp = client.post(
            "/api/rules/scan-by-source",
            json={"source_name": "mixed", "config_index": "/fake/config.json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        files = body["data"]["files"]
        names = [f["name"] for f in files]
        assert "from_dir.kmmrule.json" in names, "file from directory should appear"
        assert "standalone.kmmrule.json" in names, "standalone file should appear"
        assert "config.txt" not in names, "non-rule file should be excluded"
        assert len(files) == 2

    def test_scan_path_with_non_existent_directory(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """T6: One path non-existent → ``W_PATH_NOT_FOUND`` warning + valid paths still work."""
        rule_file = tmp_path / "valid.kmmrule.json"
        rule_file.write_text(_valid_rule_content())

        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: (
                {
                    "rule_sources": {
                        "default": {
                            "paths": [
                                str(tmp_path) + "/",  # valid directory
                                "/nonexistent_dir_xyz12345/",  # non-existent
                            ]
                        }
                    }
                },
                config_index,
            ),
        )

        resp = client.post(
            "/api/rules/scan-by-source",
            json={"source_name": "default", "config_index": "/fake/config.json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        # Valid files must still appear
        assert len(body["data"]["files"]) >= 1
        assert any(f["name"] == "valid.kmmrule.json" for f in body["data"]["files"])
        # Warning about the non-existent path must be emitted
        assert any("W_PATH_NOT_FOUND" in w for w in body["warnings"])

    def test_scan_all_paths_non_existent(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """T7: All paths non-existent → ``files: []`` + warnings."""
        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: (
                {
                    "rule_sources": {
                        "default": {
                            "paths": [
                                "/nonexistent_dir_abc_12345/",
                                "/nonexistent_file.kmmrule.json",
                            ]
                        }
                    }
                },
                config_index,
            ),
        )

        resp = client.post(
            "/api/rules/scan-by-source",
            json={"source_name": "default", "config_index": "/fake/config.json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["files"] == []
        assert len(body["warnings"]) >= 1
        assert all("W_PATH_NOT_FOUND" in w for w in body["warnings"])


# ── Existing aggregate endpoint unaffected ────────────────────────────────


class TestAggregateEndpoint:
    """POST /api/workspace/{id}/rules/aggregate — verify it remains unaffected."""

    def test_aggregate_endpoint_unaffected(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """T8: Existing aggregate endpoint still works after new endpoints are added.

        Mock the workspace manager and rule_aggregate to avoid side effects,
        then verify the endpoint returns the expected shape.
        """
        # Mock workspace manager so we don't need a real workspace
        mock_wm = MagicMock()
        mock_wm.exists.return_value = True
        mock_wm.write_aggregated_rule.return_value = None

        monkeypatch.setattr(
            "modmgr_web.routes.workspace._get_workspace_manager",
            lambda config_index: mock_wm,
        )

        # Mock rule_aggregate to return a valid result without real file I/O
        monkeypatch.setattr(
            "modmgr_web.routes.workspace.rule_aggregate",
            lambda paths: (
                {"schema_namespace": "KMM_RuleSet", "operation": []},
                [],  # errors
                [],  # warnings
            ),
        )

        # Provide a workspace_dir so _get_workspace_manager doesn't crash
        # (it won't be called because we mock _get_workspace_manager, but
        #  having it doesn't hurt)
        monkeypatch.setattr(
            "modmgr_web.routes.workspace.discover_user_config",
            lambda config_index: (
                {"workspace_dir": str(tmp_path)},
                config_index,
            ),
        )

        resp = client.post(
            "/api/workspace/test-ws-1/rules/aggregate",
            json={"paths": [str(tmp_path / "some_rules")], "config_index": "/fake/config.json"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        # Verify the aggregated rule set structure is returned
        assert "aggregated_hash" in body["data"]
        assert body["data"]["schema_namespace"] == "KMM_RuleSet"
        assert body["data"]["operation"] == []
        assert body["errors"] == []
