"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: "*"
layer: [api]
tags: [chassis, middleware, observability, security, engine-agnostic]
owner: platform-team
status: active
--- /L9_META ---

chassis/middleware.py — Reusable FastAPI Middleware Stack

Every L9 constellation node needs the same cross-cutting concerns:
    - Request ID injection (W3C traceparent)
    - Request timing / metrics
    - Tenant extraction + validation
    - Security headers
    - Structured request logging

Zero engine imports.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


# ── Request ID / Trace Propagation ────────────────────────────────────

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Injects X-Request-ID and X-Trace-ID headers.
    Propagates inbound trace headers (W3C traceparent) if present.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Propagate or generate
        request_id = request.headers.get("x-request-id", uuid.uuid4().hex)
        trace_id = request.headers.get("x-trace-id") or request.headers.get(
            "traceparent", f"trace_{uuid.uuid4().hex[:16]}"
        )

        # Stash on request state for downstream access
        request.state.request_id = request_id
        request.state.trace_id = trace_id

        response = await call_next(request)

        # Echo back on response
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = trace_id
        return response


# ── Request Timing ────────────────────────────────────────────────────

class TimingMiddleware(BaseHTTPMiddleware):
    """
    Measures request duration and sets X-Process-Time-Ms header.
    Also logs slow requests (> threshold_ms).
    """

    def __init__(self, app, slow_threshold_ms: float = 2000.0):
        super().__init__(app)
        self.slow_threshold_ms = slow_threshold_ms

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"

        if elapsed_ms > self.slow_threshold_ms:
            logger.warning(
                "Slow request: %s %s took %.1fms (threshold=%.0fms)",
                request.method,
                request.url.path,
                elapsed_ms,
                self.slow_threshold_ms,
            )

        return response


# ── Security Headers ──────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds standard security headers to every response.
    OWASP baseline for API services.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "0"  # Modern browsers: CSP instead
        return response


# ── Structured Request Logger ─────────────────────────────────────────

class StructuredLogMiddleware(BaseHTTPMiddleware):
    """
    Emits one structured JSON log line per request.
    Compatible with Datadog, Splunk, ELK, CloudWatch.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "http_request",
            extra={
                "http": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(elapsed_ms, 2),
                    "request_id": getattr(request.state, "request_id", None),
                    "trace_id": getattr(request.state, "trace_id", None),
                    "client_ip": request.client.host if request.client else None,
                    "user_agent": request.headers.get("user-agent", ""),
                },
            },
        )
        return response


# ── Convenience: Apply All ────────────────────────────────────────────

def apply_chassis_middleware(
    app,
    *,
    slow_threshold_ms: float = 2000.0,
    security_headers: bool = True,
    structured_logging: bool = True,
) -> None:
    """
    Apply the full L9 chassis middleware stack to a FastAPI app.
    Order matters: outermost middleware listed first.

    Usage (in chassis/app.py create_app):
        from chassis.middleware import apply_chassis_middleware
        apply_chassis_middleware(application)
    """
    # Order: RequestID → Timing → Security → Logging
    # (Starlette applies in reverse order, so add logging first)
    if structured_logging:
        app.add_middleware(StructuredLogMiddleware)
    if security_headers:
        app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(TimingMiddleware, slow_threshold_ms=slow_threshold_ms)
    app.add_middleware(RequestIDMiddleware)
