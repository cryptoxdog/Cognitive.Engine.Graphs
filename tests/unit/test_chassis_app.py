# ============================================================================
# tests/unit/test_chassis_app.py
# ============================================================================
"""
Unit tests for chassis/app.py — FastAPI factory and endpoints.
Tests the engine-agnostic chassis with LifecycleHook abstraction.
Target Coverage: 85%+
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from chassis.app import (
    ExecuteRequest,
    ExecuteResponse,
    LifecycleHook,
    ChassisSettings,
    create_app,
    _NoOpLifecycle,
)


# ============================================================================
# MOCK LIFECYCLE HOOK
# ============================================================================


class MockLifecycleHook(LifecycleHook):
    """Test implementation of LifecycleHook."""

    def __init__(self, execute_result: dict | None = None, execute_error: Exception | None = None):
        self._execute_result = execute_result or {
            "status": "success",
            "action": "test",
            "tenant": "test",
            "data": {},
            "meta": {},
        }
        self._execute_error = execute_error
        self.startup_called = False
        self.shutdown_called = False

    async def startup(self) -> None:
        self.startup_called = True

    async def shutdown(self) -> None:
        self.shutdown_called = True

    async def execute(
        self,
        action: str,
        payload: dict,
        tenant: str,
        trace_id: str,
    ) -> dict:
        if self._execute_error:
            raise self._execute_error
        result = self._execute_result.copy()
        result["action"] = action
        result["tenant"] = tenant
        result["meta"]["trace_id"] = trace_id
        return result


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
class TestLifecycleHook:
    """Test LifecycleHook abstraction."""

    def test_noop_lifecycle_returns_failed(self) -> None:
        """_NoOpLifecycle returns failed status."""
        import asyncio
        hook = _NoOpLifecycle()
        result = asyncio.get_event_loop().run_until_complete(
            hook.execute("test", {}, "tenant", "trace")
        )
        assert result["status"] == "failed"
        assert "No engine lifecycle hook" in result["data"]["error"]


@pytest.mark.unit
class TestCreateApp:
    """Test create_app factory."""

    def test_create_app_returns_fastapi_instance(self) -> None:
        """create_app() returns a FastAPI application."""
        hook = MockLifecycleHook()
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)

    def test_create_app_with_cors_origins(self) -> None:
        """create_app adds CORS middleware when cors_origins is set."""
        hook = MockLifecycleHook()
        settings = ChassisSettings(cors_origins=["http://localhost:3000"])
        app = create_app(lifecycle_hook=hook, settings=settings)
        middleware_classes = [m.cls.__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes

    def test_create_app_uses_custom_title(self) -> None:
        """create_app uses custom API title from settings."""
        hook = MockLifecycleHook()
        settings = ChassisSettings(api_title="Custom Engine")
        app = create_app(lifecycle_hook=hook, settings=settings)
        assert app.title == "Custom Engine"


@pytest.mark.unit
class TestExecuteEndpoint:
    """Test POST /v1/execute endpoint."""

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """POST /v1/execute routes to lifecycle hook and returns ExecuteResponse."""
        mock_result = {
            "status": "success", "action": "health", "tenant": "t1",
            "data": {"status": "healthy"}, "meta": {"trace_id": "tr_1"},
        }
        hook = MockLifecycleHook(execute_result=mock_result)
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

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
        hook = MockLifecycleHook()
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/execute", json={"bad": "data"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_handler_error_returns_500(self) -> None:
        """POST /v1/execute returns 500 on unhandled handler exception."""
        hook = MockLifecycleHook(execute_error=RuntimeError("boom"))
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/execute", json={
                "action": "match", "tenant": "t1", "payload": {},
            })
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_execute_failed_status_validation_returns_422(self) -> None:
        """POST /v1/execute returns 422 when hook returns validation failure."""
        mock_result = {
            "status": "failed",
            "action": "match",
            "tenant": "t1",
            "data": {"error": "Validation error in payload"},
            "meta": {},
        }
        hook = MockLifecycleHook(execute_result=mock_result)
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/execute", json={
                "action": "match", "tenant": "t1", "payload": {},
            })
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_execute_failed_status_returns_500(self) -> None:
        """POST /v1/execute returns 500 when hook returns non-validation failure."""
        mock_result = {
            "status": "failed",
            "action": "match",
            "tenant": "t1",
            "data": {"error": "Database connection failed"},
            "meta": {},
        }
        hook = MockLifecycleHook(execute_result=mock_result)
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/v1/execute", json={
                "action": "match", "tenant": "t1", "payload": {},
            })
        assert resp.status_code == 500


@pytest.mark.unit
class TestHealthEndpoint:
    """Test GET /v1/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200_when_healthy(self) -> None:
        """GET /v1/health returns 200 when engine is healthy."""
        mock_result = {
            "status": "success",
            "action": "health",
            "tenant": "default",
            "data": {"status": "healthy"},
            "meta": {},
        }
        hook = MockLifecycleHook(execute_result=mock_result)
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/v1/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_503_when_degraded(self) -> None:
        """GET /v1/health returns 503 when engine is degraded."""
        mock_result = {
            "status": "success",
            "action": "health",
            "tenant": "default",
            "data": {"status": "degraded"},
            "meta": {},
        }
        hook = MockLifecycleHook(execute_result=mock_result)
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/v1/health")
        assert resp.status_code == 503

    @pytest.mark.asyncio
    async def test_health_returns_503_on_exception(self) -> None:
        """GET /v1/health returns 503 on unhandled exception."""
        hook = MockLifecycleHook(execute_error=RuntimeError("crash"))
        settings = ChassisSettings(cors_origins=[])
        app = create_app(lifecycle_hook=hook, settings=settings)

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/v1/health")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "unhealthy"


@pytest.mark.unit
class TestChassisSettings:
    """Test ChassisSettings configuration."""

    def test_default_values(self) -> None:
        """ChassisSettings has sensible defaults."""
        settings = ChassisSettings()
        assert settings.api_title == "L9 Engine"
        assert settings.cors_origins == []
        assert settings.l9_lifecycle_hook == ""

    def test_custom_values(self) -> None:
        """ChassisSettings accepts custom values."""
        settings = ChassisSettings(
            api_title="Graph Engine",
            cors_origins=["http://localhost:3000"],
            l9_lifecycle_hook="engine.boot:GraphLifecycle",
        )
        assert settings.api_title == "Graph Engine"
        assert settings.cors_origins == ["http://localhost:3000"]
        assert settings.l9_lifecycle_hook == "engine.boot:GraphLifecycle"
