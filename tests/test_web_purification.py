"""Tests for web layer purification (裁 定 8 + 9 + 15).

Covers T-WP-01 ~ T-WP-09, T-WP-13 ~ T-WP-14.

See ``repo_test/web_purification.md`` for full assertion table.
"""

from __future__ import annotations

import importlib
from typing import Any
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
def config_header() -> dict[str, str]:
    """Provide a minimal valid X-UserConfig-Index header."""
    return {"X-UserConfig-Index": '{"string": "/tmp/fake_config.json", "type": "path"}'}


# ── T-WP-05: pipeline.py does not exist ────────────────────────────────────


class TestWP05PipelineFileDeleted:
    """T-WP-05: ``src/modmgr_web/routes/pipeline.py`` does not exist."""

    def test_pipeline_module_not_importable(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("modmgr_web.routes.pipeline")


# ── T-WP-06, T-WP-07: app.py does not register/import pipeline ────────────


class TestWP06WP07AppNoPipeline:
    """T-WP-06 / T-WP-07: app.py does not register / import pipeline routes."""

    def test_no_pipeline_import_in_create_app(self) -> None:
        """Verify that ``create_app`` does not reference 'pipeline'."""
        import inspect
        from modmgr_web import app as app_module

        source = inspect.getsource(app_module.create_app)
        assert "pipeline" not in source, (
            "create_app() should not reference 'pipeline' at all"
        )

    def test_no_api_pipeline_route_registered(self, client: TestClient) -> None:
        """Verify no route with prefix '/api/pipeline' is registered."""
        routes = [r.path for r in client.app.routes]
        pipeline_routes = [r for r in routes if r.startswith("/api/pipeline")]
        assert pipeline_routes == [], (
            f"Found unexpected /api/pipeline routes: {pipeline_routes}"
        )


# ── T-WP-08: visualize endpoint exists in workspace.py ────────────────────


class TestWP08VisualizeEndpoint:
    """T-WP-08: ``POST /{workspace_id}/pipeline/visualize`` endpoint exists."""

    def test_visualize_route_pattern_registered(self, client: TestClient) -> None:
        """Check the route pattern is registered (even if call fails without workspace)."""
        routes = [r.path for r in client.app.routes]
        visualize_routes = [r for r in routes if "visualize" in r]
        assert len(visualize_routes) >= 1, (
            "No route containing '/visualize' found"
        )
        # Verify it's under the workspace prefix
        matching = [r for r in visualize_routes if "/api/workspace/" in r]
        assert len(matching) >= 1, (
            f"visualize route not under /api/workspace: {visualize_routes}"
        )

    def test_visualize_endpoint_call_without_workspace(
        self, client: TestClient, config_header: dict[str, str]
    ) -> None:
        """Calling with a non-existent workspace returns an error (not 404)."""
        resp = client.post(
            "/api/workspace/nonexistent/pipeline/visualize",
            json={"format": "svg"},
            headers=config_header,
        )
        # Should get a valid JSON response (error about workspace not found
        # or config file not found — but not a 422 validation error)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body["ok"] is False


# ── T-WP-09: original generic endpoints not accessible ────────────────────


class TestWP09GenericEndpointsGone:
    """T-WP-09: Original generic endpoints are no longer accessible."""

    @pytest.mark.parametrize("path", [
        "/api/pipeline/compute",
        "/api/pipeline/run",
        "/api/pipeline/restore",
        "/api/pipeline/visualize",
    ])
    def test_generic_pipeline_endpoints_return_404_or_405(
        self, client: TestClient, path: str
    ) -> None:
        """Should NOT return 200 — either 404 (not found) or 405 (method mismatch)."""
        resp = client.post(path, json={})
        assert resp.status_code in (404, 405), (
            f"Expected 404/405 for {path}, got {resp.status_code} — "
            "a pipeline endpoint still seems to be active"
        )


# ── T-WP-01: Web layer resolver_type ──────────────────────────────────────


class TestWP01ResolverTypeWorkspace:
    """T-WP-01: Web layer all TaskRequest constructions set resolver_type='workspace'."""

    def test_workspace_pipeline_endpoints_use_workspace_resolver(self) -> None:
        """Scan workspace.py for TaskRequest(...) and verify resolver_type='workspace'."""
        import ast
        import inspect
        from modmgr_web.routes import workspace as ws_module

        source = inspect.getsource(ws_module)
        tree = ast.parse(source)

        class TaskRequestVisitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self.task_request_calls: list[dict] = []

            def visit_Call(self, node: ast.Call) -> None:
                if (isinstance(node.func, ast.Name) and node.func.id == "TaskRequest") or \
                   (isinstance(node.func, ast.Attribute) and node.func.attr == "TaskRequest"):
                    kwargs = {}
                    for kw in node.keywords:
                        if kw.arg is not None:
                            kwargs[kw.arg] = ast.dump(kw.value)
                    self.task_request_calls.append(kwargs)
                self.generic_visit(node)

        visitor = TaskRequestVisitor()
        visitor.visit(tree)

        assert len(visitor.task_request_calls) > 0, (
            "No TaskRequest(...) calls found in workspace.py"
        )

        for i, kwargs in enumerate(visitor.task_request_calls):
            resolver_type_repr = kwargs.get("resolver_type", "<missing>")
            # Python 3.12+ represents string constants as Constant(value='...')
            # while older versions use just '...'.  Check the value either way.
            assert "'workspace'" in resolver_type_repr, (
                f"TaskRequest #{i} has resolver_type={resolver_type_repr}, expected 'workspace'"
            )

    def test_no_raw_dict_resolver_in_web_layer(self) -> None:
        """Verify no Web route file uses resolver_type='raw_dict'."""
        import ast
        import inspect
        from modmgr_web.routes import workspace as ws_module

        source = inspect.getsource(ws_module)
        assert "raw_dict" not in source, (
            "workspace.py should not contain 'raw_dict'"
        )


# ── T-WP-13: PipelineResult no backup_dir ─────────────────────────────────


class TestWP13PipelineResultNoBackupDir:
    """T-WP-13: PipelineResult does not contain backup_dir field."""

    def test_backup_dir_not_in_dataclass_fields(self) -> None:
        fields = {f.name for f in PipelineResult.__dataclass_fields__.values()}
        assert "backup_dir" not in fields, (
            f"PipelineResult still has backup_dir field. Fields: {fields}"
        )

    def test_pipeline_result_can_be_constructed_without_backup_dir(self) -> None:
        """Construction without backup_dir should work."""
        result = PipelineResult(ok=True)
        assert result.ok is True
        assert not hasattr(result, "backup_dir")


# ── T-WP-14: adapters.py does not output backup_dir ───────────────────────


class TestWP14AdapterNoBackupDir:
    """T-WP-14: adapt_pipeline_result() does not output data.backup_dir."""

    def test_adapt_pipeline_result_no_backup_dir(self) -> None:
        result = PipelineResult(ok=True)
        from modmgr_web.adapters import adapt_pipeline_result

        adapted = adapt_pipeline_result(result)
        assert "backup_dir" not in adapted.get("data", {}), (
            "adapt_pipeline_result still contains backup_dir in data"
        )
        assert "backup_dir" not in adapted, (
            "adapt_pipeline_result still contains backup_dir at top level"
        )

    def test_adapt_pipeline_result_with_results_still_no_backup_dir(self) -> None:
        """Even with backup_result present, no backup_dir field."""
        result = PipelineResult(
            ok=True,
            backup_result={
                "ok": True,
                "backed_up": [],
                "skipped": [],
                "errors": [],
                "dry_run": False,
            },
        )
        from modmgr_web.adapters import adapt_pipeline_result

        adapted = adapt_pipeline_result(result)
        assert "backup_dir" not in adapted.get("data", {}), (
            "backup_dir should not appear even when backup_result is present"
        )


# ── Sanity: visualize endpoint works with mock workspace ──────────────────


class TestVisualizeEndpointFunctional:
    """End-to-end smoke test for the visualize endpoint."""

    @patch("modmgr_web.routes.workspace._get_workspace_manager")
    def test_visualize_endpoint_reachable(
        self, mock_get_wm: Any, client: TestClient, config_header: dict[str, str]
    ) -> None:
        """Mock workspace manager — verify endpoint processes the request.

        The actual ``visualize_payload`` function validates tree node
        structures; here we only verify the endpoint is wired correctly.
        """
        mock_wm = mock_get_wm.return_value
        mock_wm.exists.return_value = True
        mock_wm.has_mapping.return_value = True
        mock_wm.read_mapping.return_value = {
            "trees": [
                {
                    "root_path": "/test",
                    "changerequest": [],
                    "destin_mixed_id": "",
                    "warning": "",
                    "candidates": [],
                    "resolved_state": "keep",
                    "refs": [],
                    "extra": {},
                    "raw_node_ref": {},
                }
            ]
        }

        resp = client.post(
            "/api/workspace/test-ws/pipeline/visualize",
            json={"format": "svg", "show_m1_details": True},
            headers=config_header,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        # The endpoint should return a well-formed response
        assert "ok" in body
        assert "data" in body
        # The actual rendering may produce SVG or an error depending on
        # available tools (graphviz); either is acceptable as long as the
        # endpoint is wired correctly.
        if body["ok"]:
            assert "rendered" in body["data"]
            assert body["data"]["format"] == "svg"
