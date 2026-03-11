"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api, auth, test]
tags: [chassis, auth, test]
owner: platform-team
status: active
--- /L9_META ---

Tests for BearerAuthMiddleware.

Covers:
- Valid key passes through to handler
- Missing Authorization header returns 401
- Malformed Authorization header returns 401
- Invalid/wrong token returns 403
- Health endpoint passes without any key
- OPTIONS (CORS preflight) passes without key
- Empty L9_API_KEY rejects all authenticated requests
"""

from __future__ import annotations

import pytest
from engine.api.auth import BearerAuthMiddleware
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

# ── Test fixtures ────────────────────────────────────────────

TEST_API_KEY = "test-key-abc123-secure-token-xyz789"


def _build_test_app(api_key: str = TEST_API_KEY) -> FastAPI:
    """Build minimal FastAPI app with auth middleware for testing."""
    app = FastAPI()
    app.add_middleware(BearerAuthMiddleware, api_key=api_key)

    @app.post("/v1/execute")
    async def execute() -> JSONResponse:
        return JSONResponse(content={"status": "success", "action": "test"})

    @app.get("/v1/health")
    async def health() -> JSONResponse:
        return JSONResponse(content={"status": "healthy"})

    @app.get("/docs")
    async def docs() -> JSONResponse:
        return JSONResponse(content={"docs": True})

    return app


@pytest.fixture
def app() -> FastAPI:
    return _build_test_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Valid key passes ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_key_passes(client: AsyncClient) -> None:
    """Request with correct Bearer token reaches the handler."""
    response = await client.post(
        "/v1/execute",
        json={"action": "health", "tenant": "test"},
        headers={"Authorization": f"Bearer {TEST_API_KEY}"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


@pytest.mark.asyncio
async def test_valid_key_case_insensitive_scheme(client: AsyncClient) -> None:
    """Bearer scheme matching is case-insensitive per RFC 7235."""
    response = await client.post(
        "/v1/execute",
        json={},
        headers={"Authorization": f"bearer {TEST_API_KEY}"},
    )
    assert response.status_code == 200


# ── Missing key → 401 ───────────────────────────────────────


@pytest.mark.asyncio
async def test_missing_auth_header_returns_401(client: AsyncClient) -> None:
    """No Authorization header → 401 Unauthorized."""
    response = await client.post("/v1/execute", json={})
    assert response.status_code == 401
    body = response.json()
    assert body["status"] == "error"
    assert "Missing" in body["detail"]


# ── Malformed header → 401 ───────────────────────────────────


@pytest.mark.asyncio
async def test_malformed_auth_no_scheme(client: AsyncClient) -> None:
    """Authorization header without scheme → 401."""
    response = await client.post(
        "/v1/execute",
        json={},
        headers={"Authorization": TEST_API_KEY},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_malformed_auth_wrong_scheme(client: AsyncClient) -> None:
    """Non-Bearer scheme → 401."""
    response = await client.post(
        "/v1/execute",
        json={},
        headers={"Authorization": f"Basic {TEST_API_KEY}"},
    )
    assert response.status_code == 401


# ── Bad key → 403 ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_wrong_key_returns_403(client: AsyncClient) -> None:
    """Incorrect Bearer token → 403 Forbidden."""
    response = await client.post(
        "/v1/execute",
        json={},
        headers={"Authorization": "Bearer wrong-key-definitely-not-valid"},
    )
    assert response.status_code == 403
    body = response.json()
    assert body["status"] == "error"
    assert "Invalid" in body["detail"]


@pytest.mark.asyncio
async def test_empty_bearer_token_returns_403(client: AsyncClient) -> None:
    """Empty token after Bearer → 403."""
    response = await client.post(
        "/v1/execute",
        json={},
        headers={"Authorization": "Bearer "},
    )
    assert response.status_code == 403


# ── Health endpoint needs no key ─────────────────────────────


@pytest.mark.asyncio
async def test_health_no_auth_required(client: AsyncClient) -> None:
    """/v1/health is public — no Authorization header needed."""
    response = await client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_with_trailing_slash(client: AsyncClient) -> None:
    """/v1/health/ (trailing slash) is also public."""
    response = await client.get("/v1/health/")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_docs_no_auth_required(client: AsyncClient) -> None:
    """/docs is public."""
    response = await client.get("/docs")
    assert response.status_code == 200


# ── OPTIONS (CORS preflight) ────────────────────────────────


@pytest.mark.asyncio
async def test_options_preflight_no_auth(client: AsyncClient) -> None:
    """CORS preflight OPTIONS requests skip auth."""
    response = await client.options("/v1/execute")
    # FastAPI returns 405 for unhandled OPTIONS, but NOT 401/403
    assert response.status_code != 401
    assert response.status_code != 403


# ── Empty API key rejects everything ─────────────────────────


@pytest.mark.asyncio
async def test_empty_api_key_rejects_all() -> None:
    """When L9_API_KEY is empty, all authenticated endpoints return 403."""
    app = _build_test_app(api_key="")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/execute",
            json={},
            headers={"Authorization": "Bearer some-token"},
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_empty_api_key_health_still_public() -> None:
    """Even with empty L9_API_KEY, health endpoint stays public."""
    app = _build_test_app(api_key="")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/health")
        assert response.status_code == 200
