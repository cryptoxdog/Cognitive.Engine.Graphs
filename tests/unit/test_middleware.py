# ============================================================================
# tests/unit/test_middleware.py
# ============================================================================

"""
Middleware tests (tenant resolution, error handling).
Target Coverage: 75%+
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from engine.middleware import TenantResolver, resolve_tenant


class MockRequest:
    """Mock FastAPI request object for testing."""

    def __init__(
        self,
        headers: dict | None = None,
        host: str = "api.example.com",
        method: str = "GET",
        json_body: dict | None = None,
    ):
        self._headers = {k.lower(): v for k, v in (headers or {}).items()}
        self._headers.setdefault("host", host)
        self.method = method
        self._json_body = json_body

    @property
    def headers(self):
        return self._headers

    async def json(self):
        if self._json_body is None:
            raise ValueError("No JSON body")
        return self._json_body


@pytest.mark.unit
class TestResolveTenantFunction:
    """Test the resolve_tenant function."""

    @pytest.mark.asyncio
    async def test_resolve_from_domain_key_header(self) -> None:
        """Resolve tenant from X-Domain-Key header."""
        request = MockRequest(headers={"X-Domain-Key": "plasticos"})

        tenant = await resolve_tenant(request)

        assert tenant == "plasticos"

    @pytest.mark.asyncio
    async def test_resolve_from_tenant_key_header(self) -> None:
        """Resolve tenant from X-Tenant-Key header."""
        request = MockRequest(headers={"X-Tenant-Key": "mortgage"})

        tenant = await resolve_tenant(request)

        assert tenant == "mortgage"

    @pytest.mark.asyncio
    async def test_resolve_from_subdomain(self) -> None:
        """Resolve tenant from subdomain."""
        request = MockRequest(host="plasticos.api.example.com")

        tenant = await resolve_tenant(request)

        assert tenant == "plasticos"

    @pytest.mark.asyncio
    async def test_resolve_from_api_key_prefix(self) -> None:
        """Resolve tenant from API key prefix."""
        request = MockRequest(headers={"Authorization": "Bearer pk_freight_abc123"})

        tenant = await resolve_tenant(request)

        assert tenant == "freight"

    @pytest.mark.asyncio
    async def test_missing_tenant_raises_http_exception(self) -> None:
        """Missing tenant raises HTTPException 400."""
        request = MockRequest()

        with pytest.raises(HTTPException) as exc_info:
            await resolve_tenant(request)

        assert exc_info.value.status_code == 400


@pytest.mark.unit
class TestTenantResolverClass:
    """Test the TenantResolver class."""

    @pytest.mark.asyncio
    async def test_resolve_from_header(self) -> None:
        """Resolve tenant from X-Domain-Key header."""
        resolver = TenantResolver()
        request = MockRequest(headers={"X-Domain-Key": "plasticos"})

        tenant = await resolver.resolve(request)

        assert tenant == "plasticos"

    @pytest.mark.asyncio
    async def test_resolve_from_subdomain(self) -> None:
        """Resolve tenant from subdomain."""
        resolver = TenantResolver()
        request = MockRequest(host="plasticos.api.example.com")

        tenant = await resolver.resolve(request)

        assert tenant == "plasticos"

    @pytest.mark.asyncio
    async def test_resolve_from_envelope_body(self) -> None:
        """Resolve tenant from JSON body envelope."""
        resolver = TenantResolver()
        request = MockRequest(
            method="POST",
            json_body={"tenant": "healthcare", "action": "match"},
        )

        tenant = await resolver.resolve(request)

        assert tenant == "healthcare"

    @pytest.mark.asyncio
    async def test_default_tenant_fallback(self) -> None:
        """Use default tenant when resolution fails."""
        resolver = TenantResolver(default_tenant="default_org")
        request = MockRequest()

        tenant = await resolver.resolve(request)

        assert tenant == "default_org"

    @pytest.mark.asyncio
    async def test_unknown_tenant_rejected(self) -> None:
        """Unknown tenant rejected when allow_unknown=False."""
        resolver = TenantResolver(
            known_tenants={"plasticos", "mortgage"},
            allow_unknown=False,
        )
        request = MockRequest(headers={"X-Domain-Key": "unknown_tenant"})

        with pytest.raises(HTTPException) as exc_info:
            await resolver.resolve(request)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_known_tenant_accepted(self) -> None:
        """Known tenant accepted when validation enabled."""
        resolver = TenantResolver(
            known_tenants={"plasticos", "mortgage"},
            allow_unknown=False,
        )
        request = MockRequest(headers={"X-Domain-Key": "plasticos"})

        tenant = await resolver.resolve(request)

        assert tenant == "plasticos"

    @pytest.mark.asyncio
    async def test_resolution_stats_tracking(self) -> None:
        """Resolution stats track tenant counts."""
        resolver = TenantResolver()

        await resolver.resolve(MockRequest(headers={"X-Domain-Key": "tenant_a"}))
        await resolver.resolve(MockRequest(headers={"X-Domain-Key": "tenant_a"}))
        await resolver.resolve(MockRequest(headers={"X-Domain-Key": "tenant_b"}))

        stats = resolver.resolution_stats
        assert stats["tenant_a"] == 2
        assert stats["tenant_b"] == 1

    def test_register_tenant(self) -> None:
        """Register new tenant at runtime."""
        resolver = TenantResolver(known_tenants={"existing"})

        resolver.register_tenant("new_tenant")

        assert resolver.is_known("new_tenant")
        assert resolver.is_known("existing")

    @pytest.mark.asyncio
    async def test_callable_interface(self) -> None:
        """TenantResolver works as FastAPI Depends()."""
        resolver = TenantResolver()
        request = MockRequest(headers={"X-Domain-Key": "plasticos"})

        # __call__ delegates to resolve()
        tenant = await resolver(request)

        assert tenant == "plasticos"
