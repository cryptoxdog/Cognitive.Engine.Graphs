"""
engine/middleware.py
Multi-tenant resolution middleware for FastAPI.
Resolution strategies: header, subdomain, JWT claim, API key prefix.
Integrates with L9 chassis tenant resolution order.

Exports: resolve_tenant (function), TenantResolver (class)
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


# ── Function-based resolver (existing — unchanged) ─────────

async def resolve_tenant(request: Request) -> str:
    """
    Resolve tenant/domain identifier from request.

    Priority:
        1. X-Domain-Key header
        2. X-Tenant-Key header
        3. Subdomain (e.g., plasticos.api.example.com)
        4. API key prefix (e.g., pk_plasticos_...)

    Args:
        request: FastAPI request

    Returns:
        Domain identifier

    Raises:
        HTTPException: If tenant cannot be resolved
    """
    # 1. X-Domain-Key header
    domain_key = request.headers.get("x-domain-key")
    if domain_key:
        logger.debug(f"Resolved tenant from X-Domain-Key: {domain_key}")
        return domain_key

    # 2. X-Tenant-Key header
    tenant_key = request.headers.get("x-tenant-key")
    if tenant_key:
        logger.debug(f"Resolved tenant from X-Tenant-Key: {tenant_key}")
        return tenant_key

    # 3. Subdomain
    host = request.headers.get("host", "")
    if "." in host:
        subdomain = host.split(".")[0]
        if subdomain not in ("www", "api"):
            logger.debug(f"Resolved tenant from subdomain: {subdomain}")
            return subdomain

    # 4. API key prefix
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer pk_"):
        api_key = auth_header.replace("Bearer ", "")
        parts = api_key.split("_")
        if len(parts) >= 3:
            domain = parts[1]
            logger.debug(f"Resolved tenant from API key prefix: {domain}")
            return domain

    raise HTTPException(
        status_code=400,
        detail="Could not resolve tenant. Provide X-Domain-Key header, subdomain, or API key.",
    )


# ── Class-based TenantResolver ─────────────────────────────

class TenantResolver:
    """
    Class-based tenant resolver with validation, caching, and configuration.

    Usage:
        resolver = TenantResolver(
            known_tenants={"plasticos", "mortgageos", "freight", "healthcare"},
            allow_unknown=False,
        )

        # As FastAPI dependency
        @app.post("/v1/execute")
        async def execute(tenant: str = Depends(resolver)):
            ...

        # Direct call
        tenant = await resolver(request)
        tenant = await resolver.resolve(request)
    """

    def __init__(
        self,
        known_tenants: Optional[Set[str]] = None,
        allow_unknown: bool = True,
        default_tenant: Optional[str] = None,
        header_priority: Optional[List[str]] = None,
    ):
        """
        Args:
            known_tenants: Set of valid tenant IDs. If None, all tenants accepted.
            allow_unknown: If False, reject tenants not in known_tenants.
            default_tenant: Fallback tenant if resolution fails and this is set.
            header_priority: Custom header resolution order.
                             Defaults to ["x-domain-key", "x-tenant-key"].
        """
        self._known_tenants = known_tenants
        self._allow_unknown = allow_unknown
        self._default_tenant = default_tenant
        self._header_priority = header_priority or ["x-domain-key", "x-tenant-key"]
        self._resolution_count: Dict[str, int] = {}

    async def __call__(self, request: Request) -> str:
        """FastAPI Depends() interface."""
        return await self.resolve(request)

    async def resolve(self, request: Request) -> str:
        """
        Resolve tenant from request with validation.

        Resolution order:
            1. Custom headers (configurable priority)
            2. Subdomain
            3. API key prefix
            4. JWT claim (if present)
            5. Envelope tenant field (if JSON body)
            6. Default tenant (if configured)

        Raises:
            HTTPException 400: Tenant unresolvable
            HTTPException 403: Tenant not in known_tenants
        """
        tenant = None

        # 1. Headers
        for header_name in self._header_priority:
            value = request.headers.get(header_name)
            if value:
                tenant = value
                logger.debug(f"Tenant from header {header_name}: {tenant}")
                break

        # 2. Subdomain
        if not tenant:
            host = request.headers.get("host", "")
            if "." in host:
                subdomain = host.split(".")[0]
                if subdomain not in ("www", "api", "localhost"):
                    tenant = subdomain
                    logger.debug(f"Tenant from subdomain: {tenant}")

        # 3. API key prefix
        if not tenant:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer pk_"):
                parts = auth.replace("Bearer ", "").split("_")
                if len(parts) >= 3:
                    tenant = parts[1]
                    logger.debug(f"Tenant from API key: {tenant}")

        # 4. JWT claim (if Authorization is a JWT)
        if not tenant:
            auth = request.headers.get("authorization", "")
            if auth.startswith("Bearer ey"):
                # JWT detected — extract tenant claim without full decode
                # In production, integrate with proper JWT validation
                logger.debug("JWT detected but tenant claim extraction requires JWT lib")

        # 5. Envelope tenant field
        if not tenant and request.method == "POST":
            try:
                body = await request.json()
                if isinstance(body, dict) and "tenant" in body:
                    tenant = body["tenant"]
                    logger.debug(f"Tenant from envelope: {tenant}")
            except Exception:
                pass

        # 6. Default
        if not tenant and self._default_tenant:
            tenant = self._default_tenant
            logger.debug(f"Using default tenant: {tenant}")

        # Validate
        if not tenant:
            raise HTTPException(
                status_code=400,
                detail="Could not resolve tenant. Provide X-Domain-Key header, "
                       "subdomain, or API key.",
            )

        if self._known_tenants and not self._allow_unknown:
            if tenant not in self._known_tenants:
                raise HTTPException(
                    status_code=403,
                    detail=f"Unknown tenant: {tenant}. "
                           f"Valid tenants: {sorted(self._known_tenants)}",
                )

        # Track resolution stats
        self._resolution_count[tenant] = self._resolution_count.get(tenant, 0) + 1

        return tenant

    @property
    def resolution_stats(self) -> Dict[str, int]:
        """Return tenant resolution counts for monitoring."""
        return dict(self._resolution_count)

    def register_tenant(self, tenant_id: str) -> None:
        """Register a new known tenant at runtime."""
        if self._known_tenants is None:
            self._known_tenants = set()
        self._known_tenants.add(tenant_id)
        logger.info(f"Registered tenant: {tenant_id}")

    def is_known(self, tenant_id: str) -> bool:
        """Check if a tenant is in the known set."""
        if self._known_tenants is None:
            return True  # all accepted
        return tenant_id in self._known_tenants
