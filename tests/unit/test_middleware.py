# ============================================================================
# tests/unit/test_middleware.py
# ============================================================================

"""
Middleware tests (tenant resolution, error handling).
Target Coverage: 75%+
"""

import pytest

from engine.middleware import TenantResolver


@pytest.mark.unit
class TestTenantResolver:
    """Test multi-tenant resolution middleware."""

    def test_resolve_from_header(self):
        """Resolve tenant from X-Domain-Key header."""
        resolver = TenantResolver()

        request = MockRequest(headers={"X-Domain-Key": "plasticos"})

        tenant = resolver.resolve(request)
        assert tenant == "plasticos"

    def test_resolve_from_subdomain(self):
        """Resolve tenant from subdomain."""
        resolver = TenantResolver()

        request = MockRequest(host="plasticos.api.example.com")

        tenant = resolver.resolve(request)
        assert tenant == "plasticos"

    def test_missing_tenant_raises(self):
        """Missing tenant identifier raises error."""
        resolver = TenantResolver()

        request = MockRequest()

        with pytest.raises(ValueError):
            resolver.resolve(request)


class MockRequest:
    """Mock request object for testing."""

    def __init__(self, headers=None, host=None):
        self.headers = headers or {}
        self.host = host or "api.example.com"
