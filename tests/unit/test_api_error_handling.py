# tests/unit/test_api_error_handling.py
"""
Tests for API error handling and HTTP status codes.

Verifies that handler failures return appropriate HTTP status codes
instead of always returning 200 (AUD9-2-HIGH-1, AUD9-7-MED-1).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from chassis.app import LifecycleHook, ChassisSettings, create_app


class MockLifecycleHook(LifecycleHook):
    """Test implementation of LifecycleHook for error handling tests."""

    def __init__(self):
        self._execute_mock = AsyncMock()

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def execute(
        self,
        action: str,
        payload: dict,
        tenant: str,
        trace_id: str,
    ) -> dict:
        return await self._execute_mock(action, payload, tenant, trace_id)


@pytest.fixture
def mock_hook():
    """Create mock lifecycle hook."""
    return MockLifecycleHook()


@pytest.fixture
def test_client(mock_hook):
    """Create test client with mock lifecycle hook."""
    settings = ChassisSettings(cors_origins=[])
    app = create_app(lifecycle_hook=mock_hook, settings=settings)
    yield TestClient(app)


class TestErrorHandling:
    """Tests for proper HTTP status code handling."""

    def test_unknown_action_returns_400(self, test_client: TestClient, mock_hook: MockLifecycleHook) -> None:
        """Unknown action should return HTTP 400 when hook raises ValueError."""
        mock_hook._execute_mock.side_effect = ValueError("Unknown action: nonexistent_action")

        response = test_client.post(
            "/v1/execute",
            json={
                "action": "nonexistent_action",
                "tenant": "test",
                "payload": {},
            },
        )
        assert response.status_code == 400
        assert "Unknown action" in response.json()["detail"]

    def test_handler_failure_returns_500(self, test_client: TestClient, mock_hook: MockLifecycleHook) -> None:
        """Handler execution failure should return HTTP 500, not 200."""
        mock_hook._execute_mock.return_value = {
            "status": "failed",
            "action": "match",
            "tenant": "test",
            "data": {"error": "Database connection failed"},
            "meta": {"trace_id": "test123"},
        }

        response = test_client.post(
            "/v1/execute",
            json={
                "action": "match",
                "tenant": "test",
                "payload": {"query": {}},
            },
        )

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]

    def test_validation_error_returns_422(self, test_client: TestClient, mock_hook: MockLifecycleHook) -> None:
        """Validation errors should return HTTP 422."""
        mock_hook._execute_mock.return_value = {
            "status": "failed",
            "action": "match",
            "tenant": "test",
            "data": {"error": "Invalid query: missing required field"},
            "meta": {"trace_id": "test123"},
        }

        response = test_client.post(
            "/v1/execute",
            json={
                "action": "match",
                "tenant": "test",
                "payload": {},
            },
        )

        assert response.status_code == 422
        assert "Invalid" in response.json()["detail"]

    def test_successful_action_returns_200(self, test_client: TestClient, mock_hook: MockLifecycleHook) -> None:
        """Successful actions should return HTTP 200."""
        mock_hook._execute_mock.return_value = {
            "status": "success",
            "action": "health",
            "tenant": "test",
            "data": {"status": "healthy"},
            "meta": {"trace_id": "test123"},
        }

        response = test_client.post(
            "/v1/execute",
            json={
                "action": "health",
                "tenant": "test",
                "payload": {},
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"


class TestHealthEndpoint:
    """Tests for /v1/health endpoint."""

    def test_healthy_returns_200(self, test_client: TestClient, mock_hook: MockLifecycleHook) -> None:
        """Healthy status should return HTTP 200."""
        mock_hook._execute_mock.return_value = {
            "status": "success",
            "action": "health",
            "tenant": "default",
            "data": {"status": "healthy"},
            "meta": {},
        }

        response = test_client.get("/v1/health")

        assert response.status_code == 200
        assert response.json()["data"]["status"] == "healthy"

    def test_unhealthy_returns_503(self, test_client: TestClient, mock_hook: MockLifecycleHook) -> None:
        """Unhealthy status should return HTTP 503."""
        mock_hook._execute_mock.return_value = {
            "status": "success",
            "action": "health",
            "tenant": "default",
            "data": {"status": "unhealthy", "error": "Neo4j unreachable"},
            "meta": {},
        }

        response = test_client.get("/v1/health")

        assert response.status_code == 503

    def test_health_exception_returns_503(self, test_client: TestClient, mock_hook: MockLifecycleHook) -> None:
        """Health check exception should return HTTP 503."""
        mock_hook._execute_mock.side_effect = Exception("Connection refused")

        response = test_client.get("/v1/health")

        assert response.status_code == 503
        assert response.json()["status"] == "unhealthy"
