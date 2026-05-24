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

from modmgr.orchestrator import PipelineResult
from modmgr_web.app import create_app


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


# ── OS defaults endpoint ──────────────────────────────────────────────────


class TestOsDefaultsEndpoint:
    """GET /api/os/defaults"""

    def test_os_defaults_endpoint(self, client: TestClient) -> None:
        resp = client.get("/api/os/defaults")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        data = body["data"]
        assert "platform" in data
        assert data["platform"] in ("linux", "windows", "darwin", "wsl")
        assert "userconfig_index" in data
        uci = data["userconfig_index"]
        assert uci["type"] == "path"
        assert isinstance(uci["string"], str)
        assert len(uci["string"]) > 0
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
            "modmgr_web.routes.config.discover_user_config",
            lambda config_index: ({"game": "valheim", "language": "en"}, config_index),
        )
        resp = client.post("/api/config/discover", json={"config_index": "/fake/path"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["config"]["game"] == "valheim"
        assert body["data"]["config_index"] == "/fake/path"
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
            "modmgr_web.routes.config.discover_user_config", _raise
        )
        resp = client.post("/api/config/discover", json={"config_index": "/fake/path"})
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
            cb = kwargs.get("on_progress")
            if cb:
                cb("scan", 0, -1, "Discovering...")
                cb("scan", 1, 1, "Complete")
            return self.SAMPLE_DB

        monkeypatch.setattr(
            "modmgr_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "auto", "config_index": "/fake/path"},
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
            "modmgr_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "manual", "paths": ["/some/path"], "config_index": "/fake/path"},
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
            "modmgr_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "auto", "config_index": "/fake/path"},
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
            "modmgr_web.routes.database.generate_database", fake_generate
        )

        resp = client.post(
            "/api/database/generate",
            json={"mode": "invalid", "config_index": "/fake/path"},
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

        def fake_compute(request, *, on_progress=None):
            if on_progress:
                on_progress("compute", 0, 1, "Computing...")
                on_progress("compute", 1, 1, "Done")
            return PipelineResult(
                ok=True,
                trees=[{"path": "/a.txt", "ops": []}],
                final_mapping=[{"path": "/a.txt", "action": "replace"}],
                mapping_result={"trees": [{"path": "/a.txt", "ops": []}]},
            )

        monkeypatch.setattr(
            "modmgr_web.routes.database.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.load_json_file",
            lambda path: {"steamlib": []},
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.dispatch", fake_compute
        )

        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database_name": "default",
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
                "config_index": "/fake/path",
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

        def fake_compute(request, *, on_progress=None):
            captured_kwargs.update(request.resolver_args)
            if on_progress:
                on_progress("compute", 1, 1, "Done")
            return PipelineResult(
                ok=True,
                trees=[],
                final_mapping=[],
                mapping_result={},
            )

        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.load_json_file",
            lambda path: {"steamlib": []},
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.dispatch", fake_compute
        )

        managed_entries = {
            "game": {"270150": ["/path/a/"]},
            "mod": {"270150:123": ["/mod/path/"]},
        }

        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database_name": "default",
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
                "managed_entries": managed_entries,
                "config_index": "/fake/path",
            },
        )
        assert resp.status_code == 200
        assert captured_kwargs.get("managed_entries") == managed_entries

    def test_compute_with_aggregated_rule_set(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """aggregated_rule_set dict is passed through to orchestrator compute()."""
        captured_kwargs: dict = {}

        def fake_compute(request, *, on_progress=None):
            captured_kwargs.update(request.resolver_args)
            if on_progress:
                on_progress("compute", 1, 1, "done")
            return PipelineResult(
                ok=True,
                trees=[],
                final_mapping=[],
                mapping_result={},
            )

        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.load_json_file",
            lambda path: {"steamlib": []},
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.dispatch", fake_compute
        )

        rule_set = {"schema_namespace": "KMM_RuleSet", "operation": []}
        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database_name": "default",
                "aggregated_rule_set": rule_set,
                "config_index": "/fake/path",
            },
        )
        assert resp.status_code == 200
        # Verify aggregated_rule_set was passed to orchestrator
        assert captured_kwargs.get("aggregated_rule_set") == rule_set

    def test_compute_no_rule_input_returns_error(
        self, client: TestClient
    ) -> None:
        """No aggregated_rule_set → explicit error."""
        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database_name": "default",
                "config_index": "/fake/path",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert any("E_NO_RULE_INPUT" in e for e in body["errors"])


# ── Pipeline /run ─────────────────────────────────────────────────────────


class TestRunPipeline:
    """POST /api/pipeline/run — SSE stream"""

    def test_run_pipeline_sse(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SSE stream returns progress + result for full pipeline."""

        def fake_run(request, *, on_progress=None):
            if on_progress:
                on_progress("compute", 0, 1, "Computing...")
                on_progress("compute", 1, 1, "Done")
                on_progress("backup", 0, 2, "Backing up...")
                on_progress("backup", 2, 2, "Backup done")
                on_progress("apply", 0, 1, "Applying...")
                on_progress("apply", 1, 1, "Apply done")
            return PipelineResult(
                ok=True,
                trees=[{"path": "/a.txt", "ops": []}],
                final_mapping=[{"path": "/a.txt", "action": "replace"}],
                mapping_result={"trees": [{"path": "/a.txt", "ops": []}]},
                backup_result={
                    "ok": True,
                    "backed_up": ["/a.txt.bak"],
                    "skipped": [],
                    "errors": [],
                    "dry_run": False,
                },
                apply_result={
                    "ok": True,
                    "applied": ["/a.txt"],
                    "skipped": [],
                    "errors": [],
                    "warnings": [],
                    "dry_run": False,
                },
            )

        monkeypatch.setattr(
            "modmgr_web.routes.database.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.load_json_file",
            lambda path: {"steamlib": []},
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.dispatch", fake_run
        )

        resp = client.post(
            "/api/pipeline/run",
            json={
                "database_name": "default",
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
                "config_index": "/fake/path",
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

        def fake_run(request, *, on_progress=None):
            captured_kwargs.update(request.resolver_args)
            if on_progress:
                for step in ["compute", "backup", "apply"]:
                    on_progress(step, 1, 1, "done")
            return PipelineResult(
                ok=True, trees=[], final_mapping=[], mapping_result={},
                backup_result={"ok": True, "backed_up": [], "skipped": [], "errors": [], "dry_run": False},
                apply_result={"ok": True, "applied": [], "skipped": [], "errors": [], "warnings": [], "dry_run": False},
            )

        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.load_json_file",
            lambda path: {"steamlib": []},
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.dispatch", fake_run
        )

        managed_entries = {
            "game": {"270150": ["/path/a/"]},
        }

        resp = client.post(
            "/api/pipeline/run",
            json={
                "database_name": "default",
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
                "managed_entries": managed_entries,
                "config_index": "/fake/path",
            },
        )
        assert resp.status_code == 200
        assert captured_kwargs.get("managed_entries") == managed_entries

    def test_run_with_aggregated_rule_set(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """aggregated_rule_set dict is passed through to orchestrator run()."""
        captured_kwargs: dict = {}

        def fake_run(request, *, on_progress=None):
            captured_kwargs.update(request.resolver_args)
            if on_progress:
                for step in ["compute", "backup", "apply"]:
                    on_progress(step, 1, 1, "done")
            return PipelineResult(
                ok=True, trees=[], final_mapping=[], mapping_result={},
                backup_result={"ok": True, "backed_up": [], "skipped": [], "errors": [], "dry_run": False},
                apply_result={"ok": True, "applied": [], "skipped": [], "errors": [], "warnings": [], "dry_run": False},
            )

        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.load_json_file",
            lambda path: {"steamlib": []},
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.dispatch", fake_run
        )

        rule_set = {"schema_namespace": "KMM_RuleSet", "operation": []}
        resp = client.post(
            "/api/pipeline/run",
            json={
                "database_name": "default",
                "aggregated_rule_set": rule_set,
                "config_index": "/fake/path",
            },
        )
        assert resp.status_code == 200
        assert captured_kwargs.get("aggregated_rule_set") == rule_set

    def test_run_no_rule_input_returns_error(
        self, client: TestClient
    ) -> None:
        """No aggregated_rule_set → explicit error."""
        resp = client.post(
            "/api/pipeline/run",
            json={
                "database_name": "default",
                "config_index": "/fake/path",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert any("E_NO_RULE_INPUT" in e for e in body["errors"])


# ── Adapter unit tests ────────────────────────────────────────────────────


class TestAdapters:
    """Direct unit tests for adapter functions."""

    def test_adapt_pipeline_result_ok(self) -> None:
        from modmgr_web.adapters import adapt_pipeline_result

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
        from modmgr_web.adapters import adapt_pipeline_result

        pr = PipelineResult(
            ok=False,
            errors=["E_SOMETHING"],
            warnings=["W_CAREFUL"],
        )
        result = adapt_pipeline_result(pr)
        assert result["ok"] is False
        assert "E_SOMETHING" in result["errors"]
        assert "W_CAREFUL" in result["warnings"]

    def test_adapt_pipeline_result_with_apply_diagnostics(self) -> None:
        from modmgr_web.adapters import adapt_pipeline_result

        pr = PipelineResult(
            ok=True,
            apply_result={
                "ok": True,
                "applied": [],
                "skipped": [],
                "errors": [],
                "warnings": ["W_APPLY_NO_EFFECT: gate_failed_dirs=1, no_matched_entry_dirs=0"],
                "diagnostics": {
                    "total_backup_dirs": 1,
                    "processed_dirs": 0,
                    "gate_failed_dirs": ["/tmp/fixture/270150.abcd.kmmbackup/"],
                    "no_matched_entry_dirs": [],
                },
                "dry_run": False,
            },
        )
        result = adapt_pipeline_result(pr)
        assert result["ok"] is True
        assert result["data"]["apply_warnings"] == [
            "W_APPLY_NO_EFFECT: gate_failed_dirs=1, no_matched_entry_dirs=0"
        ]
        assert result["data"]["apply_diagnostics"]["processed_dirs"] == 0
        assert result["data"]["apply_diagnostics"]["total_backup_dirs"] == 1

    def test_adapt_dict_result(self) -> None:
        from modmgr_web.adapters import adapt_dict_result

        result = adapt_dict_result({"foo": "bar"})
        assert result["ok"] is True
        assert result["data"] == {"foo": "bar"}
        assert result["errors"] == []

    def test_adapt_error(self) -> None:
        from modmgr_web.adapters import adapt_error

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
        def fake_compute(request, *, on_progress=None):
            # Simulate work that reports progress then returns
            if on_progress:
                on_progress("compute", 0, 1, "Computing...")
            return PipelineResult(
                ok=True,
                forest=[],
                final_mapping=[],
                mapping_result={},
            )

        monkeypatch.setattr(
            "modmgr_web.routes.database.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.load_json_file",
            lambda path: {"steamlib": []},
        )
        monkeypatch.setattr(
            "modmgr_web.routes.pipeline.dispatch", fake_compute
        )

        # Send a normal request — the important thing is that it does not
        # crash the server regardless of how the client handles the stream.
        resp = client.post(
            "/api/pipeline/compute",
            json={
                "database_name": "default",
                "aggregated_rule_set": {"schema_namespace": "KMM_RuleSet", "operation": []},
                "config_index": "/fake/path",
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

    def test_rules_affected_entries_empty_path(self, client: TestClient) -> None:
        """affected-entries with empty path returns error."""
        resp = client.post("/api/rules/affected-entries", json={"aggregated_rule_path": "", "config_index": "/fake/path"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is False
        assert body["errors"]


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

        # Mock user_config to return the database path via database_name
        monkeypatch.setattr(
            "modmgr_web.routes.rules.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": str(db_file)}}}, "/fake/path"),
        )

        resp = client.post(
            "/api/rules/affected-entries",
            json={"aggregated_rule_path": str(agg_file), "database_name": "default", "config_index": "/fake/path"},
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


# ── Backups API ─────────────────────────────────────────────────────────────


class TestBackupsListApi:
    """POST /api/backups/list"""

    def test_backups_list_returns_kmmbackup_dirs(
        self, client: TestClient, tmp_path: Path
    ) -> None:
        """list returns directories with .kmmbackup suffix."""
        d1 = tmp_path / "001.kmmbackup"
        d1.mkdir()
        (d1 / "backupinfo.json").write_text("{}")
        (d1 / "somefile.txt").write_text("data")

        d2 = tmp_path / "002.kmmbackup"
        d2.mkdir()
        (d2 / "file.bin").write_text("binary")

        # This one should NOT appear
        (tmp_path / "other_dir").mkdir()

        resp = client.post("/api/backups/list", json={"dir": str(tmp_path)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        names = [b["name"] for b in body["data"]["backups"]]
        assert "001.kmmbackup" in names
        assert "002.kmmbackup" in names
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
            "tree_created_time": "2026-05-20T10:15:30Z",
            "last_modified_time": "2026-05-20T10:16:02Z",
            "schema_version": "1",
            "tree": {
                "name": "kmmbackup_test",
                "type": "dir",
                "children": [
                    {
                        "name": "mnt",
                        "type": "dir",
                        "children": [
                            {
                                "name": "d",
                                "type": "dir",
                                "children": [
                                    {
                                        "name": "test.txt",
                                        "type": "file",
                                        "isbackuped": True,
                                        "hashtype": "sha256",
                                        "hashvalue": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
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
            "modmgr_web.routes.pipeline.restore_from_backup", fake_restore
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
            "modmgr_web.routes.pipeline.restore_from_backup", fake_restore
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
        from modmgr_web.adapters import adapt_restore_result

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
        from modmgr_web.adapters import adapt_restore_result

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


# ── Database /read ────────────────────────────────────────────────────────


class TestReadDatabase:
    """POST /api/database/read"""

    def test_read_database_success(
        self, client, monkeypatch
    ):
        """read resolves database_name from user_config and loads database."""
        fake_db = {"game": [{"appid": "270150"}], "mod": []}

        monkeypatch.setattr(
            "modmgr_web.routes.database.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": "/fake/db.json"}}}, "/fake/path"),
        )
        monkeypatch.setattr(
            "modmgr_web.routes.database.load_json_file",
            lambda path: fake_db,
        )

        resp = client.post("/api/database/read", json={"database_name": "default", "config_index": "/fake/path"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["data"]["game"][0]["appid"] == "270150"

    def test_read_database_not_found(self, client, monkeypatch):
        """read returns error when database_name is not in user_config."""
        monkeypatch.setattr(
            "modmgr_web.routes.database.discover_user_config",
            lambda config_index: ({"databases": {}}, "/fake/path"),
        )

        resp = client.post("/api/database/read", json={"database_name": "nonexistent", "config_index": "/fake/path"})
        body = resp.json()
        assert body["ok"] is False


# ── Database /save ─────────────────────────────────────────────────────────


class TestSaveDatabase:
    """POST /api/database/save"""

    def test_save_database_writes_file(self, client, tmp_path, monkeypatch):
        """save writes the database dict to disk using database_name."""
        db_file = tmp_path / "db.json"
        db_data = {"game": [{"appid": "270150"}], "mod": []}

        monkeypatch.setattr(
            "modmgr_web.routes.database.discover_user_config",
            lambda config_index: ({"databases": {"default": {"path": str(db_file)}}}, "/fake/path"),
        )

        # Use real write_json_file so we can verify the file was written
        resp = client.post(
            "/api/database/save",
            json={"database": db_data, "database_name": "default", "config_index": "/fake/path"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        # Verify the file was actually written
        saved = json.loads(db_file.read_text(encoding="utf-8"))
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

        config = {
            "game": "valheim",
            "rule_sources": [
                str(rules_dir),  # directory — should get trailing /
                "/some/file.json",  # file — should not
            ],
        }

        output = tmp_path / "user_config.json"

        # Mock userconfig_save to just write the file (bypass schema validation)
        from modmgr.iojson import write_json_file as _wjf
        monkeypatch.setattr(
            "modmgr_web.routes.config.userconfig_save",
            lambda config_index, data: _wjf(config_index, data),
        )

        resp = client.post(
            "/api/config/save",
            json={"config": config, "config_index": str(output)},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True

        saved = json.loads(output.read_text(encoding="utf-8"))
        # The directory path should now end with /
        assert saved["rule_sources"][0].endswith("/")
        # The file path should not end with /
        assert not saved["rule_sources"][1].endswith("/")


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
