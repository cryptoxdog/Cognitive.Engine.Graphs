"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: "*"
layer: [api]
tags: [chassis, errors, exceptions, engine-agnostic]
owner: platform-team
status: active
--- /L9_META ---

chassis/errors.py — L9 Structured Error Hierarchy

Every constellation node raises the same error types so the chassis
can map them to HTTP status codes deterministically.

    ChassisError (base)
    ├── ValidationError   → 422
    ├── NotFoundError     → 404
    ├── AuthorizationError→ 403
    ├── RateLimitError    → 429
    └── ExecutionError    → 500

Engines subclass these freely. The chassis only catches the base types.
"""

from __future__ import annotations

from typing import Any


class ChassisError(Exception):
    """
    Base error for all L9 chassis-routable exceptions.

    Attributes:
        action:  The action that failed (match, sync, enrich, etc.)
        tenant:  Tenant context
        detail:  Machine-readable detail string
        context: Arbitrary metadata for audit/debugging
    """

    status_code: int = 500

    def __init__(
        self,
        message: str,
        *,
        action: str = "",
        tenant: str = "",
        detail: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.action = action
        self.tenant = tenant
        self.detail = detail
        self.context = context or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire-safe dict for error responses."""
        return {
            "error": type(self).__name__,
            "message": str(self),
            "action": self.action,
            "tenant": self.tenant,
            "detail": self.detail,
            "context": self.context,
        }


class ValidationError(ChassisError):
    """Payload or schema validation failure → HTTP 422."""
    status_code: int = 422


class NotFoundError(ChassisError):
    """Resource not found (domain, entity, etc.) → HTTP 404."""
    status_code: int = 404


class AuthorizationError(ChassisError):
    """Tenant not authorized for this action → HTTP 403."""
    status_code: int = 403


class RateLimitError(ChassisError):
    """Rate limit exceeded → HTTP 429."""
    status_code: int = 429

    def __init__(self, message: str = "Rate limit exceeded", *, retry_after: int = 60, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, **kwargs)


class ExecutionError(ChassisError):
    """Runtime execution failure (DB down, timeout, etc.) → HTTP 500."""
    status_code: int = 500
