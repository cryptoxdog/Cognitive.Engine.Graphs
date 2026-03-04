# ============================================================================
# tests/unit/test_api_app.py
# ============================================================================
"""
Unit tests for engine/api/app.py — FastAPI factory and endpoints.
Target Coverage: 85%+
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from engine.api.app import ExecuteRequest, ExecuteResponse, create_app


# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestPydanticModels:
    """Test ExecuteRequest/ExecuteResponse Pydantic models."""

    def test_execute_request_valid(self) -> None:
        """ExecuteRequest validates valid input."""
        req = ExecuteRequest(action="match", tenant="t1", payload={"key": "val"})
        assert req.action == "match"
        assert req.trace_id is None

    def test_execute_request_with_trace_id(self) -> None:
        """ExecuteRequest accepts optional trace_id."""
        req = ExecuteRequest(action="sync", tenant="t1", trace_id="tr_123")
        assert req.trace_id == "tr_123"

    def test_execute_request_default_payload(self) -> None:
        """ExecuteRequest defaults payload to empty dict."""
        req = ExecuteRequest(action="health", tenant="t1")
        assert req.payload == {}

    def test_execute_response_valid(self) -> None:
        """ExecuteResponse validates valid input."""
        resp = ExecuteResponse(
            status="success", action="match", tenant="t1",
            data={"candidates": []}, meta={"trace_id": "t"},
        )
        assert resp.status == "success"


@pytest.mark.unit
class TestCreateApp:
    """Test create_app factory."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """create_app() returns a FastAPI application."""
        with patch("engine.api.app.settings") as mock_settings:
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from fastapi import FastAPI
            assert isinstance(app, FastAPI)
            assert app.title == "L9 Graph Cognitive Engine"

    def test_create_app_with_cors_origins(self) -> None:
        """create_app adds CORS middleware when cors_origins is set."""
        with patch("engine.api.app.settings") as mock_settings:
            mock_settings.cors_origins = ["http://localhost:3000"]
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            middleware_classes = [m.cls.__name__ for m in app.user_middleware]
            assert "CORSMiddleware" in middleware_classes


@pytest.mark.unit
class TestExecuteEndpoint:
    """Test POST /v1/execute endpoint."""

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """POST /v1/execute routes to chassis and returns ExecuteResponse."""
        mock_result = {
            "status": "success", "action": "health", "tenant": "t1",
            "data": {"status": "healthy"}, "meta": {"trace_id": "tr_1"},
        }
        with patch("engine.api.app.settings") as mock_settings, \
             patch("engine.api.app.execute_action", new_callable=AsyncMock, return_value=mock_result):
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from httpx import ASGITransport, AsyncClient
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/v1/execute", json={
                    "action": "health", "tenant": "t1", "payload": {},
                })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_invalid_payload_returns_422(self) -> None:
        """POST /v1/execute with missing required fields returns 422."""
        with patch("engine.api.app.settings") as mock_settings:
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from httpx import ASGITransport, AsyncClient
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/v1/execute", json={"bad": "data"})
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_handler_error_returns_500(self) -> None:
        """POST /v1/execute returns 500 on unhandled handler exception."""
        with patch("engine.api.app.settings") as mock_settings, \
             patch("engine.api.app.execute_action", new_callable=AsyncMock,
                   side_effect=RuntimeError("boom")):
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from httpx import ASGITransport, AsyncClient
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/v1/execute", json={
                    "action": "match", "tenant": "t1", "payload": {},
                })
            assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_execute_failed_status_validation_returns_422(self) -> None:
        """POST /v1/execute returns 422 when chassis returns validation failure."""
        mock_result = {
            "status": "failed",
            "data": {"error": "Validation error in payload"},
        }
        with patch("engine.api.app.settings") as mock_settings, \
             patch("engine.api.app.execute_action", new_callable=AsyncMock, return_value=mock_result):
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from httpx import ASGITransport, AsyncClient
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/v1/execute", json={
                    "action": "match", "tenant": "t1", "payload": {},
                })
            assert resp.status_code == 422


@pytest.mark.unit
class TestHealthEndpoint:
    """Test GET /v1/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200_when_healthy(self) -> None:
        """GET /v1/health returns 200 when engine is healthy."""
        mock_result = {"data": {"status": "healthy"}, "meta": {}}
        with patch("engine.api.app.settings") as mock_settings, \
             patch("engine.api.app.execute_action", new_callable=AsyncMock, return_value=mock_result):
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from httpx import ASGITransport, AsyncClient
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/v1/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_503_when_degraded(self) -> None:
        """GET /v1/health returns 503 when engine is degraded."""
        mock_result = {"data": {"status": "degraded"}, "meta": {}}
        with patch("engine.api.app.settings") as mock_settings, \
             patch("engine.api.app.execute_action", new_callable=AsyncMock, return_value=mock_result):
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from httpx import ASGITransport, AsyncClient
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/v1/health")
            assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_health_returns_503_on_exception(self) -> None:
        """GET /v1/health returns 503 on unhandled exception."""
        with patch("engine.api.app.settings") as mock_settings, \
             patch("engine.api.app.execute_action", new_callable=AsyncMock,
                   side_effect=RuntimeError("crash")):
            mock_settings.cors_origins = []
            mock_settings.neo4j_uri = "bolt://localhost:7687"
            mock_settings.neo4j_username = "neo4j"
            mock_settings.neo4j_password = "password"
            mock_settings.domains_root = "/tmp/domains"
            app = create_app()
            from httpx import ASGITransport, AsyncClient
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.get("/v1/health")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unhealthy"
