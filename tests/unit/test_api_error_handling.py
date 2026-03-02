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


@pytest.fixture
def mock_graph_driver():
    """Mock GraphDriver for testing without Neo4j."""
    driver = AsyncMock()
    driver.connect = AsyncMock()
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def mock_domain_loader():
    """Mock DomainPackLoader for testing."""
    loader = AsyncMock()
    loader.list_domains = lambda: ["testdomain"]
    return loader


@pytest.fixture
def test_client(mock_graph_driver, mock_domain_loader):
    """Create test client with mocked dependencies."""
    with (
        patch("engine.api.app.GraphDriver", return_value=mock_graph_driver),
        patch("engine.api.app.DomainPackLoader", return_value=mock_domain_loader),
        patch("engine.api.app.init_dependencies"),
    ):
        from engine.api.app import create_app

        app = create_app()
        yield TestClient(app)


class TestErrorHandling:
    """Tests for proper HTTP status code handling."""

    def test_unknown_action_returns_400(self, test_client: TestClient) -> None:
        """Unknown action should return HTTP 400."""
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

    def test_handler_failure_returns_500(self, test_client: TestClient) -> None:
        """Handler execution failure should return HTTP 500, not 200."""
        with patch("chassis.actions.execute_action") as mock_execute:
            # Simulate chassis returning a failed status
            mock_execute.return_value = {
                "status": "failed",
                "action": "match",
                "tenant": "test",
                "data": {"error": "Database connection failed"},
                "meta": {"trace_id": "test123", "execution_ms": 10, "version": "1.0", "timestamp": "2026-01-01"},
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

    def test_validation_error_returns_422(self, test_client: TestClient) -> None:
        """Validation errors should return HTTP 422."""
        with patch("chassis.actions.execute_action") as mock_execute:
            # Simulate chassis returning a validation failure
            mock_execute.return_value = {
                "status": "failed",
                "action": "match",
                "tenant": "test",
                "data": {"error": "Invalid query: missing required field"},
                "meta": {"trace_id": "test123", "execution_ms": 5, "version": "1.0", "timestamp": "2026-01-01"},
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

    def test_successful_action_returns_200(self, test_client: TestClient) -> None:
        """Successful actions should return HTTP 200."""
        with patch("chassis.actions.execute_action") as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "action": "health",
                "tenant": "test",
                "data": {"status": "healthy"},
                "meta": {"trace_id": "test123", "execution_ms": 1, "version": "1.0", "timestamp": "2026-01-01"},
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

    def test_healthy_returns_200(self, test_client: TestClient) -> None:
        """Healthy status should return HTTP 200."""
        with patch("chassis.actions.execute_action") as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "action": "health",
                "tenant": "default",
                "data": {"status": "healthy"},
                "meta": {},
            }

            response = test_client.get("/v1/health")

            assert response.status_code == 200
            assert response.json()["data"]["status"] == "healthy"

    def test_unhealthy_returns_503(self, test_client: TestClient) -> None:
        """Unhealthy status should return HTTP 503."""
        with patch("chassis.actions.execute_action") as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "action": "health",
                "tenant": "default",
                "data": {"status": "unhealthy", "error": "Neo4j unreachable"},
                "meta": {},
            }

            response = test_client.get("/v1/health")

            assert response.status_code == 503

    def test_health_exception_returns_503(self, test_client: TestClient) -> None:
        """Health check exception should return HTTP 503."""
        with patch("chassis.actions.execute_action") as mock_execute:
            mock_execute.side_effect = Exception("Connection refused")

            response = test_client.get("/v1/health")

            assert response.status_code == 503
            assert response.json()["status"] == "unhealthy"
