"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api, auth]
tags: [chassis, auth, middleware]
owner: platform-team
status: active
--- /L9_META ---

Bearer token authentication middleware for L9 Graph Cognitive Engine.

Validates L9_API_KEY from Authorization header on all routes except
health endpoints. Single-token model: one key in AWS Secrets Manager,
one consumer (Clawdbot).

Consumes:
- engine.config.settings.settings.l9_api_key (from L9_API_KEY env var)

Security model:
- Bearer token comparison uses hmac.compare_digest (timing-safe)
- Health endpoints are exempt (Cloudflare/Coolify uptime checks)
- Missing Authorization header → 401 Unauthorized
- Invalid token → 403 Forbidden
- Token loaded once at startup, not per-request
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from fastapi import Request, Response
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Paths that never require authentication.
# Health must stay public for Cloudflare, Coolify, and external uptime monitors.
PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/v1/health",
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
)


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates Bearer token from Authorization header against L9_API_KEY.

    Exempt paths (PUBLIC_PATHS) pass through without authentication.
    All other paths require: Authorization: Bearer <token>

    Responses:
        401 - Missing or malformed Authorization header
        403 - Token does not match L9_API_KEY
    """

    def __init__(self, app: ASGIApp, *, api_key: str) -> None:
        super().__init__(app)
        if not api_key or api_key in ("", "change-me-in-production"):
            logger.critical(
                "L9_API_KEY is not set or uses a default value. "
                "Authentication is DISABLED — all requests will be rejected."
            )
        self._api_key: str = api_key
        self._api_key_bytes: bytes = api_key.encode("utf-8") if api_key else b""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """Authenticate request or pass through if public path."""
        path = request.url.path.rstrip("/")

        # Public paths skip auth entirely
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # OPTIONS requests skip auth (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            logger.warning(
                "Missing Authorization header: %s %s from %s",
                request.method,
                path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "detail": "Missing Authorization header",
                    "hint": "Include header: Authorization: Bearer <L9_API_KEY>",
                },
            )

        # Validate Bearer scheme
        parts = auth_header.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            logger.warning("Malformed Authorization header: scheme=%r", parts[0] if parts else "empty")
            return JSONResponse(
                status_code=401,
                content={
                    "status": "error",
                    "detail": "Malformed Authorization header — expected: Bearer <token>",
                },
            )

        token = parts[1]

        # Timing-safe comparison to prevent timing attacks
        if not self._api_key_bytes or not hmac.compare_digest(
            token.encode("utf-8"),
            self._api_key_bytes,
        ):
            logger.warning(
                "Invalid API key: %s %s from %s",
                request.method,
                path,
                request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={
                    "status": "error",
                    "detail": "Invalid API key",
                },
            )

        return await call_next(request)
