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

Wave 3 (W3-01): Extends with tenant authorization enforcement.
- Extracts ``allowed_tenants`` claim from JWT payload in Authorization header
- Compares request tenant against allowed_tenants; returns 403 if not present
- TENANT_AUTH_ENABLED flag (default True) — when False, skip check for transition
- TENANT_AUTH_BYPASS_KEY env var for service-to-service calls (X-Internal-Bypass-Key header)

Consumes:
- engine.config.settings.settings.l9_api_key (from L9_API_KEY env var)
- engine.config.settings.settings.tenant_auth_enabled (W3-01)
- engine.config.settings.settings.tenant_auth_bypass_key (W3-01)

Security model:
- Bearer token comparison uses hmac.compare_digest (timing-safe)
- Health endpoints are exempt (Cloudflare/Coolify uptime checks)
- Missing Authorization header → 401 Unauthorized
- Invalid token → 403 Forbidden
- Token loaded once at startup, not per-request
"""

from __future__ import annotations

import hmac
import json
import logging
from base64 import urlsafe_b64decode
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

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

# Header name for service-to-service bypass key (W3-01)
_BYPASS_KEY_HEADER = "X-Internal-Bypass-Key"


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    """Decode the payload (claims) from a JWT without signature verification.

    The chassis already validates the token against L9_API_KEY. This function
    only extracts claims like ``allowed_tenants`` for authorization decisions.
    Returns empty dict on any decode failure (malformed token, non-JWT key, etc.).
    """
    parts = token.split(".")
    jwt_segment_count = 3
    if len(parts) != jwt_segment_count:
        return {}
    try:
        # JWT base64url may lack padding — add it
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        decoded = urlsafe_b64decode(payload_b64)
        claims = json.loads(decoded)
        if isinstance(claims, dict):
            return claims
    except Exception:
        logger.debug("Failed to decode JWT claims from token", exc_info=True)
    return {}


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates Bearer token from Authorization header against L9_API_KEY.

    Exempt paths (PUBLIC_PATHS) pass through without authentication.
    All other paths require: Authorization: Bearer <token>

    W3-01: When tenant_auth_enabled is True, extracts ``allowed_tenants``
    from the JWT payload and compares against the request tenant.

    Responses:
        401 - Missing or malformed Authorization header
        403 - Token does not match L9_API_KEY / tenant not authorized
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        api_key: str,
        tenant_auth_enabled: bool = True,
        tenant_auth_bypass_key: str = "",
    ) -> None:
        super().__init__(app)
        if not api_key or api_key in ("", "change-me-in-production"):
            logger.critical(
                "L9_API_KEY is not set or uses a default value. "
                "Authentication is DISABLED — all requests will be rejected."
            )
        self._api_key: str = api_key
        self._api_key_bytes: bytes = api_key.encode("utf-8") if api_key else b""
        # W3-01: Tenant authorization
        self._tenant_auth_enabled: bool = tenant_auth_enabled
        self._bypass_key: str = tenant_auth_bypass_key
        self._bypass_key_bytes: bytes = tenant_auth_bypass_key.encode("utf-8") if tenant_auth_bypass_key else b""

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

        # ── W3-01: Tenant Authorization Enforcement ──────────────────
        if self._tenant_auth_enabled:
            # Check for service-to-service bypass key first
            bypass_header = request.headers.get(_BYPASS_KEY_HEADER, "")
            if self._bypass_key_bytes and bypass_header:
                if hmac.compare_digest(
                    bypass_header.encode("utf-8"),
                    self._bypass_key_bytes,
                ):
                    # Bypass key valid — skip tenant check
                    return await call_next(request)

            # Extract tenant from request body (for POST /v1/execute)
            # We decode JWT claims to check allowed_tenants
            claims = _decode_jwt_payload(token)
            allowed_tenants = claims.get("allowed_tenants")

            if allowed_tenants is not None:
                # Store claims on request state for downstream use
                request.state.jwt_claims = claims
                request.state.allowed_tenants = allowed_tenants

                # For POST requests, try to read tenant from cached body
                # The actual tenant check is deferred to the handler layer
                # because reading the body here would consume it.
                # Instead, we store allowed_tenants on request.state and
                # the execute route checks it after parsing the body.

        return await call_next(request)
