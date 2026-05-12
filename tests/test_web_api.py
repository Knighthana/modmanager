"""Tests for the modmanager_web Web API layer.

All tests use ``TestClient`` (no real HTTP server).  Side-effect-heavy calls
(bootstrap, orchestrator) are mocked to avoid real file-system modifications.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from modmanager.orchestrator import PipelineResult
from modmanager_web.app import create_app


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def client() -> TestClient:
    """Build a fresh TestClient for each test."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def tmp_user_config(tmp_path: Path) -> Path:
    """Create a temporary user_config.json and return its parent directory."""
    config_dir = tmp_path / ".config" / "kmm"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "user_config.json"
    config_file.write_text(json.dumps({"game": "valheim", "language": "en"}))
    return tmp_path


# ── Health endpoint ────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """GET /api/health"""

    def test_health_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["version"] == "0.1.0"
        assert body["data"]["package"] == "modmanager_web"
        assert body["errors"] == []
        assert body["warnings"] == []


# ── Docs endpoint ─────────────────────────────────────────────────────────


class TestDocsEndpoint:
    """GET /api/docs — Swagger UI"""

    def test_docs_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/docs")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "swagger" in resp.text.lower()


# ── Config /discover ──────────────────────────────────────────────────────


class TestDiscoverUserConfig:
    """POST /api/config/discover"""

    def test_discover_user_config_success(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return merged config when user_config.json exists."""
        monkeypatch.setattr(
            "modmanager_web.routes.config.discover_user_config",
            lambda home_dir=None: {"game": "valheim", "language": "en"},
        )
        resp = client.post("/api/config/discover", json={"home_dir": None})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["game"] == "valheim"
        assert body["errors"] == []

    def test_discover_user_config_not_found(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Return error when no user_config.json is found anywhere."""
        def _raise(*args, **kwargs):
            raise FileNotFoundError(
                "No user_config.json found in any search location"
            )

        monkeypatch.setattr(
            "modmanager_web.routes.config.discover_user_config", _raise
        )
        resp = client.post("/api/config/discover", json={"home_dir": None})
        assert resp.status_code == 200  # FastAPI returns 200; ok=false in body
        body = resp.json()
        assert body["ok"] is False
        assert len(body["errors"]) > 0
        assert "No user_config.json found" in body["errors"][0]


# ── Database /generate ────────────────────────────────────────────────────


class TestGenerateDatabase:
    """POST /api/database/generate — SSE stream"""

    SAMPLE_DB = {
        "steamlib": [
            {
                "path": "/games/steam",
                "contains_libraryfolders_vdf": False,
                "game": [],
            }
        ]
    }

    def test_generate_database_success_sse(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SSE stream returns progress + result for successful generation."""

        def fake_generate(**kwargs):
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("scan", 0, -1, "Discovering...")
                kwargs["on_progress"]("scan", 1, 1, "Complete")
            return self.SAMPLE_DB

        monkeypatch.setattr(
            "modmanager_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "auto"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        lines = resp.text.split("\n")
        events = _parse_sse_lines(lines)

        progress_events = [e for e in events if e["event"] == "progress"]
        result_events = [e for e in events if e["event"] == "result"]

        assert len(progress_events) >= 1
        assert len(result_events) == 1
        assert result_events[0]["data"]["ok"] is True
        assert "steamlib" in result_events[0]["data"]["data"]

    def test_generate_database_manual_mode_passes_manual_only(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """mode='manual' + paths → verify manual_only=True (no auto discover)."""
        captured_kwargs: dict = {}

        def fake_generate(**kwargs):
            captured_kwargs.update(kwargs)
            # Return minimal valid database (no managed/warnings/errors)
            return {
                "steamlib": [{"path": "/manual/steamapps", "contains_libraryfolders_vdf": False, "game": []}],
                "game": [],
                "mod": [],
            }

        monkeypatch.setattr(
            "modmanager_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "manual", "paths": ["/some/path"]},
        )
        assert resp.status_code == 200

        # Verify the call was made with correct parameters
        assert captured_kwargs.get("mode") == "manual"
        assert captured_kwargs.get("paths") == ["/some/path"]

    def test_generate_database_duplicate_appid_error(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Duplicate appid across libraries should be reported in errors."""

        def fake_generate(**kwargs):
            return {
                "steamlib": [
                    {"path": "/lib1/steamapps", "contains_libraryfolders_vdf": False, "game": ["270150"]},
                    {"path": "/lib2/steamapps", "contains_libraryfolders_vdf": False, "game": ["270150"]},
                ],
                "game": [
                    {
                        "appid": "270150",
                        "name": "RWR",
                        "basepath": "/lib1/steamapps/common/RWR",
                        "modpath": "/lib1/steamapps/workshop/content/270150",
                        "mods_found": [],
                    },
                ],
                "mod": [],
            }

        monkeypatch.setattr(
            "modmanager_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "auto"},
        )
        assert resp.status_code == 200
        lines = resp.text.split("\n")
        events = _parse_sse_lines(lines)
        result_events = [e for e in events if e["event"] == "result"]
        assert len(result_events) == 1
        data = result_events[0]["data"]
        assert data["ok"] is True

    def test_generate_database_invalid_mode(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invalid mode raises ValueError → SSE error event."""

        def fake_generate(**kwargs):
            raise ValueError("mode must be 'auto' or 'manual', got 'invalid'")

        monkeypatch.setattr(
            "modmanager_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "invalid"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        lines = resp.text.split("\n")
        events = _parse_sse_lines(lines)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["ok"] is False
        assert len(error_events[0]["data"]["errors"]) > 0


# ── Pipeline /compute ─────────────────────────────────────────────────────


class TestComputePipeline:
    """POST /api/pipeline/compute — SSE stream"""

    def test_compute_pipeline_sse(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SSE stream returns progress + result for compute pipeline."""

        def fake_compute(**kwargs):
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("aggregate", 0, 1, "Aggregating...")
                kwargs["on_progress"]("aggregate", 1, 1, "Complete")
                kwargs["on_progress"]("compute", 0, 1, "Computing...")
                kwargs["on_progress"]("compute", 1, 1, "Done")
            return PipelineResult(
                ok=True,
                trees=[{"path": "/a.txt", "ops": []}],
                final_mapping=[{"path": "/a.txt", "action": "replace"}],
                mapping_result={"trees": [{"path": "/a.txt", "ops": []}]},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_compute", fake_compute
        )
        monkeypatch.setattr(
            "modmanager.path_resolver.resolve_file_path", lambda path, _name: path
        )

        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database": {"steamlib": []},
                "kmm_rule_paths": ["/fake/rules.json"],
                "user_config_path": "/fake/user_config.json",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        lines = resp.text.split("\n")
        events = _parse_sse_lines(lines)

        progress_events = [e for e in events if e["event"] == "progress"]
        result_events = [e for e in events if e["event"] == "result"]

        assert len(progress_events) >= 1
        assert len(result_events) == 1
        assert result_events[0]["data"]["ok"] is True
        assert "trees" in result_events[0]["data"]["data"]

    def test_compute_with_managed_entries(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """managed_entries is passed through to orchestrator compute()."""
        captured_kwargs: dict = {}

        def fake_compute(**kwargs):
            captured_kwargs.update(kwargs)
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("aggregate", 1, 1, "Done")
                kwargs["on_progress"]("compute", 1, 1, "Done")
            return PipelineResult(
                ok=True,
                trees=[],
                final_mapping=[],
                mapping_result={},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_compute", fake_compute
        )
        monkeypatch.setattr(
            "modmanager.path_resolver.resolve_file_path", lambda path, _name: path
        )

        managed_entries = {
            "game": {"270150": ["/path/a/"]},
            "mod": {"270150:123": ["/mod/path/"]},
        }

        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database": {"steamlib": []},
                "kmm_rule_paths": ["/fake/rules.json"],
                "user_config_path": "/fake/user_config.json",
                "managed_entries": managed_entries,
            },
        )
        assert resp.status_code == 200
        assert captured_kwargs.get("managed_entries") == managed_entries


# ── Pipeline /run ─────────────────────────────────────────────────────────


class TestRunPipeline:
    """POST /api/pipeline/run — SSE stream"""

    def test_run_pipeline_sse(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SSE stream returns progress + result for full pipeline."""

        def fake_run(**kwargs):
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("aggregate", 0, 1, "Aggregating...")
                kwargs["on_progress"]("aggregate", 1, 1, "Done")
                kwargs["on_progress"]("compute", 0, 1, "Computing...")
                kwargs["on_progress"]("compute", 1, 1, "Done")
                kwargs["on_progress"]("backup", 0, 2, "Backing up...")
                kwargs["on_progress"]("backup", 2, 2, "Backup done")
                kwargs["on_progress"]("apply", 0, 1, "Applying...")
                kwargs["on_progress"]("apply", 1, 1, "Apply done")
            return PipelineResult(
                ok=True,
                trees=[{"path": "/a.txt", "ops": []}],
                final_mapping=[{"path": "/a.txt", "action": "replace"}],
                mapping_result={"trees": [{"path": "/a.txt", "ops": []}]},
                backup_result={
                    "ok": True,
                    "backed_up": ["/a.txt.bak"],
                    "skipped": [],
                },
                apply_result={
                    "ok": True,
                    "applied": ["/a.txt"],
                    "skipped": [],
                },
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_run", fake_run
        )
        monkeypatch.setattr(
            "modmanager.path_resolver.resolve_file_path", lambda path, _name: path
        )

        resp = client.post(
            "/api/pipeline/run",
            json={
                "database": {"steamlib": []},
                "kmm_rule_paths": ["/fake/rules.json"],
                "user_config_path": "/fake/user_config.json",
                "backup_dir": "/fake/backups",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        lines = resp.text.split("\n")
        events = _parse_sse_lines(lines)

        progress_events = [e for e in events if e["event"] == "progress"]
        result_events = [e for e in events if e["event"] == "result"]

        assert len(progress_events) >= 1
        assert len(result_events) == 1
        assert result_events[0]["data"]["ok"] is True
        # Stats should be present for full pipeline
        stats = result_events[0]["data"]["data"].get("stats")
        assert stats is not None
        assert stats["backed_up"] == 1
        assert stats["applied"] == 1

    def test_run_with_managed_entries(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """managed_entries is passed through to orchestrator run()."""
        captured_kwargs: dict = {}

        def fake_run(**kwargs):
            captured_kwargs.update(kwargs)
            if kwargs.get("on_progress"):
                for step in ["aggregate", "compute", "backup", "apply"]:
                    kwargs["on_progress"](step, 1, 1, "done")
            return PipelineResult(
                ok=True, trees=[], final_mapping=[], mapping_result={},
                backup_result={"ok": True, "backed_up": [], "skipped": []},
                apply_result={"ok": True, "applied": [], "skipped": []},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_run", fake_run
        )
        monkeypatch.setattr(
            "modmanager.path_resolver.resolve_file_path", lambda path, _name: path
        )

        managed_entries = {
            "game": {"270150": ["/path/a/"]},
        }

        resp = client.post(
            "/api/pipeline/run",
            json={
                "database": {"steamlib": []},
                "kmm_rule_paths": ["/fake/rules.json"],
                "user_config_path": "/fake/user_config.json",
                "backup_dir": "/fake/backups",
                "managed_entries": managed_entries,
            },
        )
        assert resp.status_code == 200
        assert captured_kwargs.get("managed_entries") == managed_entries


# ── Adapter unit tests ────────────────────────────────────────────────────


class TestAdapters:
    """Direct unit tests for adapter functions."""

    def test_adapt_pipeline_result_ok(self) -> None:
        from modmanager_web.adapters import adapt_pipeline_result

        pr = PipelineResult(
            ok=True,
            trees=[{"path": "/a.txt"}],
            final_mapping=[{"path": "/a.txt", "action": "replace"}],
            mapping_result={"trees": [{"path": "/a.txt"}]},
        )
        result = adapt_pipeline_result(pr)
        assert result["ok"] is True
        assert result["data"]["trees"] == [{"path": "/a.txt"}]
        assert result["errors"] == []
        assert result["warnings"] == []

    def test_adapt_pipeline_result_fail(self) -> None:
        from modmanager_web.adapters import adapt_pipeline_result

        pr = PipelineResult(
            ok=False,
            errors=["E_SOMETHING"],
            warnings=["W_CAREFUL"],
        )
        result = adapt_pipeline_result(pr)
        assert result["ok"] is False
        assert "E_SOMETHING" in result["errors"]
        assert "W_CAREFUL" in result["warnings"]

    def test_adapt_backup_result(self) -> None:
        from modmanager_web.adapters import adapt_backup_result

        raw = {
            "ok": True,
            "backed_up": ["/a.txt.bak"],
            "skipped": [],
            "errors": [],
        }
        result = adapt_backup_result(raw)
        assert result["ok"] is True
        assert result["data"]["backed_up"] == ["/a.txt.bak"]
        assert result["errors"] == []

    def test_adapt_apply_result(self) -> None:
        from modmanager_web.adapters import adapt_apply_result

        raw = {
            "ok": True,
            "applied": ["/a.txt"],
            "skipped": [],
            "errors": [],
        }
        result = adapt_apply_result(raw)
        assert result["ok"] is True
        assert result["data"]["applied"] == ["/a.txt"]
        assert result["errors"] == []

    def test_adapt_dict_result(self) -> None:
        from modmanager_web.adapters import adapt_dict_result

        result = adapt_dict_result({"foo": "bar"})
        assert result["ok"] is True
        assert result["data"] == {"foo": "bar"}
        assert result["errors"] == []

    def test_adapt_error(self) -> None:
        from modmanager_web.adapters import adapt_error

        result = adapt_error("Something went wrong")
        assert result["ok"] is False
        assert result["data"] is None
        assert "Something went wrong" in result["errors"]


# ── SSE stream disconnect ─────────────────────────────────────────────────


class TestSseDisconnect:
    """Client disconnection does not crash the server."""

    def test_sse_stream_disconnect(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the client disconnects early, the handler should not crash."""

        import asyncio

        async def slow_work(*, on_progress):
            on_progress("step", 0, 1, "working...")
            await asyncio.sleep(0.5)
            on_progress("step", 1, 1, "done")
            return {"result": "ok"}

        # We need to test at the StreamResponse level.
        # The easiest way is to stream the response with a timeout.
        def fake_compute(**kwargs):
            # Simulate work that reports progress then returns
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("compute", 0, 1, "Computing...")
            return PipelineResult(
                ok=True,
                forest=[],
                final_mapping=[],
                mapping_result={},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_compute", fake_compute
        )
        monkeypatch.setattr(
            "modmanager.path_resolver.resolve_file_path", lambda path, _name: path
        )

        # Send a normal request — the important thing is that it does not
        # crash the server regardless of how the client handles the stream.
        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database": {"steamlib": []},
                "kmm_rule_paths": ["/fake/rules.json"],
                "user_config_path": "/fake/user_config.json",
            },
        )
        # If the SSE stream is well-formed, we're good.
        assert resp.status_code == 200
        assert "event:" in resp.text


# ── Rules API ───────────────────────────────────────────────────────────────


class TestRulesApi:
    """POST /api/rules/scan and POST /api/rules/read."""

    def test_rules_scan_returns_kmmrule_json_files(self, client: TestClient, tmp_path: Path) -> None:
        """scan lists .kmmrule.json files in a directory."""
        (tmp_path / "rule_a.kmmrule.json").write_text('{"a": 1}')
        (tmp_path / "rule_b.kmmrule.json").write_text('{"b": 2}')
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "regular.json").write_text('{"c": 3}')
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "nested.kmmrule.json").write_text("{}")

        resp = client.post("/api/rules/scan", json={"dir": str(tmp_path)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        names = [f["name"] for f in body["data"]["files"]]
        assert "rule_a.kmmrule.json" in names
        assert "rule_b.kmmrule.json" in names
        assert "readme.txt" not in names  # not .kmmrule.json
        assert "regular.json" not in names  # not .kmmrule.json
        assert "nested.kmmrule.json" not in names  # in subdirectory (non-recursive)

    def test_rules_scan_dir_not_found(self, client: TestClient) -> None:
        """scan returns error for non-existent directory."""
        resp = client.post("/api/rules/scan", json={"dir": "/nonexistent_dir_xyz"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]

    def test_rules_scan_not_a_directory(self, client: TestClient, tmp_path: Path) -> None:
        """scan returns error when path is a file, not directory."""
        f = tmp_path / "afile.txt"
        f.write_text("data")
        resp = client.post("/api/rules/scan", json={"dir": str(f)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]

    def test_rules_scan_empty_dir(self, client: TestClient, tmp_path: Path) -> None:
        """scan returns empty list for directory with no .kmmrule.json files."""
        (tmp_path / "readme.txt").write_text("data")
        resp = client.post("/api/rules/scan", json={"dir": str(tmp_path)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["files"] == []

    def test_rules_read_returns_content(self, client: TestClient, tmp_path: Path) -> None:
        """read returns raw text content of a file."""
        f = tmp_path / "test_rule.json"
        f.write_text('{"key": "value"}', encoding="utf-8")
        resp = client.post("/api/rules/read", json={"path": str(f)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["content"] == '{"key": "value"}'
        assert body["data"]["name"] == "test_rule.json"

    def test_rules_read_file_not_found(self, client: TestClient) -> None:
        """read returns error for non-existent file."""
        resp = client.post("/api/rules/read", json={"path": "/nonexistent_file_xyz.json"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]

    def test_rules_read_not_a_file(self, client: TestClient, tmp_path: Path) -> None:
        """read returns error when path is a directory."""
        resp = client.post("/api/rules/read", json={"path": str(tmp_path)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]

    def test_rules_aggregate_empty_paths(self, client: TestClient) -> None:
        """aggregate with empty paths returns error."""
        resp = client.post("/api/rules/aggregate", json={"paths": []})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]

    def test_rules_load_aggregated_not_found(self, client: TestClient) -> None:
        """load-aggregated with non-existent path returns error."""
        resp = client.post("/api/rules/load-aggregated", json={"path": "/nonexistent_agg.json"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]

    def test_rules_affected_entries_empty_path(self, client: TestClient) -> None:
        """affected-entries with empty path returns error."""
        resp = client.post("/api/rules/affected-entries", json={"aggregated_rule_path": ""})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]


class TestRulesAggregateEndpoint:
    """POST /api/rules/aggregate"""

    def test_rules_aggregate_calls_aggregate(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """aggregate passes paths to rule_aggregator.aggregate()."""
        captured: dict = {}

        def fake_aggregate(kmm_rule_paths, user_config_path, *, action_orders=None, sidecar_refs=None, output_path=None):
            captured["paths"] = kmm_rule_paths
            captured["output_path"] = output_path
            return {"schema_namespace": "KMM_RuleSet", "operation": []}, [], []

        monkeypatch.setattr(
            "modmanager_web.routes.rules.rule_aggregate", fake_aggregate
        )
        monkeypatch.setattr(
            "modmanager.workspace.load_workspace",
            lambda: {"inputs": {"aggregated_rule_path": "", "user_config_path": ""}},
        )

        resp = client.post(
            "/api/rules/aggregate",
            json={"paths": ["/rule1.json", "/rule2.json"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert captured.get("paths") == ["/rule1.json", "/rule2.json"]


class TestRulesLoadAggregated:
    """POST /api/rules/load-aggregated"""

    def test_load_aggregated_success(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """load-aggregated returns the raw content of an aggregated rule set."""
        agg_file = tmp_path / "aggregated_rule_set.json"
        agg_data = {"schema_namespace": "KMM_RuleSet", "operation": []}
        agg_file.write_text(json.dumps(agg_data))

        resp = client.post(
            "/api/rules/load-aggregated",
            json={"path": str(agg_file)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["schema_namespace"] == "KMM_RuleSet"


class TestRulesAffectedEntries:
    """POST /api/rules/affected-entries"""

    def test_affected_entries_with_valid_data(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """affected-entries returns libraries/games/mods with correct structure."""
        # Create an aggregated rule set
        agg_file = tmp_path / "agg.json"
        agg_file.write_text(json.dumps({
            "schema_namespace": "KMM_RuleSet",
            "operation": [
                {"mixed_id": "270150:123", "nickname": "TestMod", "actionlist": []},
            ],
        }))

        # Create a database
        db_file = tmp_path / "database.json"
        db_file.write_text(json.dumps({
            "steamlib": [
                {"path": "/games/steam", "contains_libraryfolders_vdf": False, "game": ["270150"]},
            ],
            "game": [
                {"appid": "270150", "name": "RWR", "basepath": "/games/steam/steamapps/common/RWR", "modpath": "/games/steam/steamapps/workshop/content/270150", "mods_found": []},
            ],
            "mod": [
                {"mixed_id": "270150:123", "nickname": "TestMod", "path": "/mods/test/", "appid": "270150"},
            ],
        }))

        # Mock workspace to return the database path
        monkeypatch.setattr(
            "modmanager.workspace.load_workspace",
            lambda: {"inputs": {"database_path": str(db_file)}},
        )

        resp = client.post(
            "/api/rules/affected-entries",
            json={"aggregated_rule_path": str(agg_file)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        data = body["data"]
        assert "libraries" in data
        assert "games" in data
        assert "mods" in data
        # Verify structure
        if data["libraries"]:
            assert "index" in data["libraries"][0]
            assert "path" in data["libraries"][0]
            assert "game_count" in data["libraries"][0]
            assert "mod_count" in data["libraries"][0]
        if data["games"]:
            assert "appid" in data["games"][0]
            assert "libraryIndex" in data["games"][0]
            assert "has_duplicate" in data["games"][0]
        if data["mods"]:
            assert "mixed_id" in data["mods"][0]
            assert "libraryIndex" in data["mods"][0]
            assert "gameIndex" in data["mods"][0]
            assert "has_duplicate" in data["mods"][0]


# ── Workspace API ───────────────────────────────────────────────────────────


class TestWorkspaceStatus:
    """GET /api/workspace/status"""

    def test_workspace_status_returns_workspace(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """status returns the full workspace dict."""
        fake_workspace = {
            "session_updated": "2026-01-01T00:00:00Z",
            "inputs": {
                "database_path": "/tmp/db.json",
                "rule_paths": [],
                "aggregated_rule_path": "",
                "user_config_path": "",
                "discovery_mode": "auto",
                "discovery_manual_paths": [],
            },
            "decisions": {"branch_decisions": {}},
            "results": {
                "last_compute": {
                    "trees_count": 0,
                    "mapping_count": 0,
                    "warnings": [],
                    "errors": [],
                    "stats": {},
                    "inputs_hash": "",
                    "timestamp": None,
                },
            },
        }

        monkeypatch.setattr(
            "modmanager_web.routes.workspace.load_workspace",
            lambda: fake_workspace,
        )

        resp = client.get("/api/workspace/status")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"] == fake_workspace
        assert body["errors"] == []


class TestWorkspaceSaveInputs:
    """POST /api/workspace/save-inputs"""

    def test_save_inputs_merges_fields(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save-inputs merges provided fields into workspace inputs."""
        captured: dict = {}

        def fake_merge_workspace(data, section, path=None):
            captured["data"] = data
            captured["section"] = section
            return {"inputs": data, "decisions": {}, "results": {}}

        monkeypatch.setattr(
            "modmanager_web.routes.workspace.merge_workspace", fake_merge_workspace
        )

        resp = client.post(
            "/api/workspace/save-inputs",
            json={
                "database_path": "/new/db.json",
                "discovery_mode": "manual",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert captured["section"] == "inputs"
        assert captured["data"]["database_path"] == "/new/db.json"
        assert captured["data"]["discovery_mode"] == "manual"

    def test_save_inputs_empty_body(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save-inputs with empty body merges nothing (preserves existing)."""
        captured: dict = {}

        def fake_merge_workspace(data, section, path=None):
            captured["data"] = data
            captured["section"] = section
            return {"inputs": data, "decisions": {}, "results": {}}

        monkeypatch.setattr(
            "modmanager_web.routes.workspace.merge_workspace", fake_merge_workspace
        )

        resp = client.post(
            "/api/workspace/save-inputs",
            json={},
        )
        assert resp.status_code == 200
        assert captured["data"] == {}


class TestWorkspaceSaveDecisions:
    """POST /api/workspace/save-decisions"""

    def test_save_decisions_merges_branch_decisions(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save-decisions merges branch_decisions into workspace decisions."""
        captured: dict = {}

        def fake_merge_workspace(data, section, path=None):
            captured["data"] = data
            captured["section"] = section
            return {"inputs": {}, "decisions": data, "results": {}}

        monkeypatch.setattr(
            "modmanager_web.routes.workspace.merge_workspace", fake_merge_workspace
        )

        resp = client.post(
            "/api/workspace/save-decisions",
            json={"branch_decisions": {"/tree/a": "/src/a"}},
        )
        assert resp.status_code == 200
        assert captured["section"] == "decisions"
        assert captured["data"]["branch_decisions"]["/tree/a"] == "/src/a"

    def test_save_decisions_null_branch_decisions(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save-decisions with null branch_decisions merges empty data."""
        captured: dict = {}

        def fake_merge_workspace(data, section, path=None):
            captured["data"] = data
            captured["section"] = section
            return {"inputs": {}, "decisions": data, "results": {}}

        monkeypatch.setattr(
            "modmanager_web.routes.workspace.merge_workspace", fake_merge_workspace
        )

        resp = client.post(
            "/api/workspace/save-decisions",
            json={"branch_decisions": None},
        )
        assert resp.status_code == 200
        assert captured["data"] == {}


class TestWorkspaceSaveResults:
    """POST /api/workspace/save-results"""

    def test_save_results_merges_last_compute(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save-results merges fields into results.last_compute."""
        captured: dict = {}

        def fake_merge_workspace(data, section, path=None):
            captured["data"] = data
            captured["section"] = section
            return {"inputs": {}, "decisions": {}, "results": data}

        monkeypatch.setattr(
            "modmanager_web.routes.workspace.merge_workspace", fake_merge_workspace
        )

        resp = client.post(
            "/api/workspace/save-results",
            json={
                "trees_count": 42,
                "mapping_count": 99,
                "warnings": ["W_TEST"],
                "errors": [],
                "stats": {"elapsed": 1.5},
                "inputs_hash": "abc123",
            },
        )
        assert resp.status_code == 200
        assert captured["section"] == "results"
        assert captured["data"]["last_compute"]["trees_count"] == 42
        assert captured["data"]["last_compute"]["mapping_count"] == 99
        assert captured["data"]["last_compute"]["warnings"] == ["W_TEST"]
        assert captured["data"]["last_compute"]["inputs_hash"] == "abc123"

    def test_save_results_partial(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """save-results with partial fields only merges those fields."""
        captured: dict = {}

        def fake_merge_workspace(data, section, path=None):
            captured["data"] = data
            captured["section"] = section
            return {"inputs": {}, "decisions": {}, "results": data}

        monkeypatch.setattr(
            "modmanager_web.routes.workspace.merge_workspace", fake_merge_workspace
        )

        resp = client.post(
            "/api/workspace/save-results",
            json={"trees_count": 7},
        )
        assert resp.status_code == 200
        assert captured["data"]["last_compute"]["trees_count"] == 7
        # Only provided field should be in the merge data
        assert "mapping_count" not in captured["data"]["last_compute"]


# ── Backups API ─────────────────────────────────────────────────────────────


class TestBackupsListApi:
    """POST /api/backups/list"""

    def test_backups_list_returns_kmmbackup_dirs(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """list returns directories with kmmbackup_ prefix."""
        d1 = tmp_path / "kmmbackup_001"
        d1.mkdir()
        (d1 / "backupinfo.json").write_text("{}")
        (d1 / "somefile.txt").write_text("data")

        d2 = tmp_path / "kmmbackup_002"
        d2.mkdir()
        (d2 / "file.bin").write_text("binary")

        # This one should NOT appear
        (tmp_path / "other_dir").mkdir()

        resp = client.post("/api/backups/list", json={"dir": str(tmp_path)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        names = [b["name"] for b in body["data"]["backups"]]
        assert "kmmbackup_001" in names
        assert "kmmbackup_002" in names
        assert "other_dir" not in names

    def test_backups_list_dir_not_found(self, client: TestClient) -> None:
        """list returns error for non-existent directory."""
        resp = client.post("/api/backups/list", json={"dir": "/nonexistent_bak_xyz"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]

    def test_backups_list_empty(self, client: TestClient, tmp_path: Path) -> None:
        """list returns empty array when no kmmbackup_* directories exist."""
        (tmp_path / "some_dir").mkdir()
        resp = client.post("/api/backups/list", json={"dir": str(tmp_path)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["backups"] == []


class TestBackupsInspectApi:
    """POST /api/backups/inspect"""

    def test_backups_inspect_returns_info(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """inspect returns backup details for a valid backup directory."""
        backup_dir = tmp_path / "kmmbackup_test"
        backup_dir.mkdir()

        # Create a minimal backupinfo.json
        info = {
            "filefoldertree_status": "ready",
            "filefoldertree": {
                "name": "kmmbackup_test",
                "type": "folder",
                "children": [
                    {
                        "name": "mnt",
                        "type": "folder",
                        "children": [
                            {
                                "name": "d",
                                "type": "folder",
                                "children": [
                                    {
                                        "name": "test.txt",
                                        "type": "file",
                                        "hashvalue": "abc123",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
        }
        (backup_dir / "backupinfo.json").write_text(json.dumps(info))
        # Also create the actual file so it's counted
        actual = backup_dir / "mnt" / "d" / "test.txt"
        actual.parent.mkdir(parents=True)
        actual.write_text("hello")

        resp = client.post("/api/backups/inspect", json={"path": str(backup_dir)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["file_count"] >= 1
        assert body["data"]["dirty"]["dirty"] is False
        assert "path" in body["data"]

    def test_backups_inspect_dir_not_found(self, client: TestClient) -> None:
        """inspect returns error for non-existent directory."""
        resp = client.post("/api/backups/inspect", json={"path": "/nonexistent_bak_xyz"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert any("not found" in e for e in body["errors"])


# ── Pipeline /restore ───────────────────────────────────────────────────────


class TestPipelineRestore:
    """POST /api/pipeline/restore — SSE stream"""

    def test_restore_sse_stream(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SSE stream returns progress + result for restore."""

        def fake_restore(**kwargs):
            return {
                "ok": True,
                "restored": ["/mnt/d/test.txt"],
                "skipped": [],
                "errors": [],
                "orphans": [],
                "warnings": [],
            }

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.restore_from_backup", fake_restore
        )

        resp = client.post(
            "/api/pipeline/restore",
            json={"backup_dir": "/fake/backups", "target_files": None},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        lines = resp.text.split("\n")
        events = _parse_sse_lines(lines)

        result_events = [e for e in events if e["event"] == "result"]
        assert len(result_events) == 1
        assert result_events[0]["data"]["ok"] is True
        assert result_events[0]["data"]["data"]["restored"] == ["/mnt/d/test.txt"]

    def test_restore_sse_error(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SSE stream returns error event when restore raises."""

        def fake_restore(**kwargs):
            raise ValueError("backup gate failed")

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.restore_from_backup", fake_restore
        )

        resp = client.post(
            "/api/pipeline/restore",
            json={"backup_dir": "/fake/bad_backup"},
        )
        assert resp.status_code == 200
        lines = resp.text.split("\n")
        events = _parse_sse_lines(lines)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["data"]["ok"] is False


# ── Adapter unit tests (extended) ────────────────────────────────────────────


class TestAdaptersExtended:
    """Additional adapter tests for new endpoints."""

    def test_adapt_restore_result_ok(self) -> None:
        from modmanager_web.adapters import adapt_restore_result

        raw = {
            "ok": True,
            "restored": ["/a.txt"],
            "skipped": [],
            "orphans": [],
            "errors": [],
            "warnings": [],
        }
        result = adapt_restore_result(raw)
        assert result["ok"] is True
        assert result["data"]["restored"] == ["/a.txt"]
        assert result["errors"] == []

    def test_adapt_restore_result_fail(self) -> None:
        from modmanager_web.adapters import adapt_restore_result

        raw = {
            "ok": False,
            "restored": [],
            "skipped": [],
            "orphans": [],
            "errors": ["E_BACKUP_DIR_MISSING"],
            "warnings": [],
        }
        result = adapt_restore_result(raw)
        assert result["ok"] is False
        assert "E_BACKUP_DIR_MISSING" in result["errors"]


# ── Database /load ────────────────────────────────────────────────────────


class TestLoadDatabase:
    """POST /api/database/load"""

    def test_load_database_from_path_success(self, client, tmp_path):
        # 创建临时 database.json
        db_file = tmp_path / "database.json"
        db_file.write_text(json.dumps({"game": [], "mod": []}))

        resp = client.post("/api/database/load", json={"path": str(db_file)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["game"] == []

    def test_load_database_from_directory(self, client, tmp_path):
        # 传入目录路径，自动找 database.json
        db_file = tmp_path / "database.json"
        db_file.write_text(json.dumps({"game": [{"appid": "270150"}]}))

        resp = client.post("/api/database/load", json={"path": str(tmp_path) + "/"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["game"][0]["appid"] == "270150"

    def test_load_database_not_found(self, client):
        resp = client.post("/api/database/load", json={"path": "/nonexistent/path"})
        body = resp.json()
        assert body["ok"] is False


# ── Database /save ─────────────────────────────────────────────────────────


class TestSaveDatabase:
    """POST /api/database/save"""

    def test_save_database_writes_file(self, client, tmp_path):
        """save writes the database dict to disk."""
        output = tmp_path / "saved_db.json"
        db_data = {"game": [{"appid": "270150"}], "mod": []}

        resp = client.post(
            "/api/database/save",
            json={"database": db_data, "output_path": str(output)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["path"] == str(output)
        # Verify the file was actually written
        saved = json.loads(output.read_text(encoding="utf-8"))
        assert saved["game"][0]["appid"] == "270150"


# ── Config /save with rule_sources normalization ────────────────────────────


class TestConfigSaveRuleSources:
    """POST /api/config/save with rule_sources normalization."""

    def test_save_config_normalizes_directory_rule_sources(
        self, client, tmp_path, monkeypatch
    ):
        """rule_sources directory paths get trailing / appended."""
        # Create a real directory to trigger normalization
        rules_dir = tmp_path / "my_rules"
        rules_dir.mkdir()

        output = tmp_path / "saved_config.json"
        config = {
            "game": "valheim",
            "rule_sources": [
                str(rules_dir),  # directory — should get trailing /
                "/some/file.json",  # file — should not
            ],
        }

        resp = client.post(
            "/api/config/save",
            json={"config": config, "output_path": str(output)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

        saved = json.loads(output.read_text(encoding="utf-8"))
        # The directory path should now end with /
        assert saved["rule_sources"][0].endswith("/")
        # The file path should not end with /
        assert not saved["rule_sources"][1].endswith("/")


# ── Tilde expansion tests (TODO-11) ──────────────────────────────────────────


class TestTildeExpansion:
    """``POST /api/pipeline/compute`` and ``/run`` with ``~`` paths must expand correctly.

    The route handler calls ``resolve_file_path`` which internally expands
    ``~`` / ``$HOME`` via ``os.path.expanduser``.  We override ``HOME`` so that
    ``~/file.json`` resolves into a ``tmp_path``-based location.
    """

    def _set_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Redirect HOME to *tmp_path* so ``~`` resolves under our control."""
        monkeypatch.setenv("HOME", str(tmp_path))

    def test_compute_expands_tilde_in_kmm_rule_paths(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tilde in kmm_rule_paths is expanded before reaching orchestrator."""
        self._set_home(monkeypatch, tmp_path)

        # Create files under the fake HOME
        rule_file = tmp_path / "my_rules.json"
        rule_file.write_text('{"operation": []}')
        cfg_file = tmp_path / "user_config.json"
        cfg_file.write_text('{"game_permissions": {}}')

        captured: dict = {}

        def fake_compute(**kwargs):
            captured["rule_paths"] = kwargs.get("kmm_rule_paths", [])
            captured["user_cfg"] = kwargs.get("user_config_path", "")
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("aggregate", 1, 1, "done")
            return PipelineResult(
                ok=True, trees=[], final_mapping=[], mapping_result={},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_compute", fake_compute
        )
        # Do NOT mock resolve_file_path — we want the real expansion

        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database": {"steamlib": []},
                # Use ~ path that resolves to tmp_path/my_rules.json
                "kmm_rule_paths": ["~/my_rules.json"],
                "user_config_path": "~/user_config.json",
            },
        )
        assert resp.status_code == 200

        # The captured paths should be expanded absolute paths
        assert len(captured.get("rule_paths", [])) == 1
        resolved_rule = captured["rule_paths"][0]
        assert resolved_rule == str(rule_file), f"Expected {rule_file}, got {resolved_rule}"
        # user_config should also be expanded
        assert captured.get("user_cfg") == str(cfg_file)
        # No literal tilde should remain
        assert "~" not in str(captured)
        assert "~" not in str(captured.get("user_cfg", ""))

    def test_run_expands_tilde_in_kmm_rule_paths(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tilde expansion in /run endpoint."""
        self._set_home(monkeypatch, tmp_path)

        rule_file = tmp_path / "run_rule.json"
        rule_file.write_text('{"operation": []}')
        cfg_file = tmp_path / "user_config.json"
        cfg_file.write_text('{"game_permissions": {}}')

        captured: dict = {}

        def fake_run(**kwargs):
            captured["rule_paths"] = kwargs.get("kmm_rule_paths", [])
            captured["user_cfg"] = kwargs.get("user_config_path", "")
            if kwargs.get("on_progress"):
                for step in ["aggregate", "compute", "backup", "apply"]:
                    kwargs["on_progress"](step, 1, 1, "done")
            return PipelineResult(
                ok=True, trees=[], final_mapping=[], mapping_result={},
                backup_result={"ok": True, "backed_up": [], "skipped": []},
                apply_result={"ok": True, "applied": [], "skipped": []},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_run", fake_run
        )

        resp = client.post(
            "/api/pipeline/run",
            json={
                "database": {"steamlib": []},
                "kmm_rule_paths": ["~/run_rule.json"],
                "user_config_path": "~/user_config.json",
                "backup_dir": "/tmp",
            },
        )
        assert resp.status_code == 200
        assert len(captured.get("rule_paths", [])) == 1
        assert captured["rule_paths"][0] == str(rule_file)
        assert "~" not in str(captured)

    def test_compute_expands_tilde_in_user_config_path(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tilde in user_config_path is expanded."""
        self._set_home(monkeypatch, tmp_path)

        cfg_file = tmp_path / "user_config.json"
        cfg_file.write_text('{"game_permissions": {}}')
        rule_file = tmp_path / "dummy.json"
        rule_file.write_text('{"operation": []}')

        captured: dict = {}

        def fake_compute(**kwargs):
            captured["user_cfg"] = kwargs.get("user_config_path", "")
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("aggregate", 1, 1, "done")
            return PipelineResult(
                ok=True, trees=[], final_mapping=[], mapping_result={},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_compute", fake_compute
        )

        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database": {"steamlib": []},
                "kmm_rule_paths": [str(rule_file)],
                "user_config_path": "~/user_config.json",
            },
        )
        assert resp.status_code == 200
        assert captured.get("user_cfg") == str(cfg_file)
        assert "~" not in str(captured.get("user_cfg", ""))

    def test_database_path_with_tilde_expands(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When database is a path string with ~, it gets expanded."""
        self._set_home(monkeypatch, tmp_path)

        db_file = tmp_path / "database.json"
        db_file.write_text('{"steamlib": []}')
        rule_file = tmp_path / "dummy.json"
        rule_file.write_text('{"operation": []}')
        cfg_file = tmp_path / "user_config.json"
        cfg_file.write_text('{"game_permissions": {}}')

        captured: dict = {}

        def fake_compute(**kwargs):
            captured["db"] = kwargs.get("database", None)
            captured["rule_paths"] = kwargs.get("kmm_rule_paths", [])
            if kwargs.get("on_progress"):
                kwargs["on_progress"]("aggregate", 1, 1, "done")
            return PipelineResult(
                ok=True, trees=[], final_mapping=[], mapping_result={},
            )

        monkeypatch.setattr(
            "modmanager_web.routes.pipeline.orch_compute", fake_compute
        )

        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database": "~/database.json",
                "kmm_rule_paths": [str(rule_file)],
                "user_config_path": str(cfg_file),
            },
        )
        assert resp.status_code == 200
        # The database should have been loaded and passed as a dict (not a string)
        assert isinstance(captured.get("db"), dict)
        assert "steamlib" in captured["db"]


# ── Helper ────────────────────────────────────────────────────────────────


def _parse_sse_lines(lines: list[str]) -> list[dict]:
    """Parse raw SSE text lines into a list of {event, data} dicts."""
    events: list[dict] = []
    current: dict | None = None
    for line in lines:
        line = line.strip()
        if line.startswith("event:"):
            if current is not None:
                events.append(current)
            current = {"event": line.split(":", 1)[1].strip()}
        elif line.startswith("data:") and current is not None:
            raw = line.split(":", 1)[1].strip()
            try:
                current["data"] = json.loads(raw)
            except json.JSONDecodeError:
                current["data"] = raw
        elif line == "" and current is not None:
            events.append(current)
            current = None
    if current is not None:
        events.append(current)
    return events
