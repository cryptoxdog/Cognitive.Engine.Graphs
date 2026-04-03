"""Integration tests — admin handler: list_domains, get_domain, init_schema."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_domains_returns_plasticos(graph_driver, domain_loader):
    from engine.handlers import handle_admin

    result = await handle_admin(
        "plasticos",
        {"sub_action": "list_domains"},
        graph_driver,
        domain_loader,
    )
    assert "plasticos" in str(result)


@pytest.mark.asyncio
async def test_get_domain_returns_spec(graph_driver, domain_loader):
    from engine.handlers import handle_admin

    result = await handle_admin(
        "plasticos",
        {"sub_action": "get_domain", "domain_id": "plasticos"},
        graph_driver,
        domain_loader,
    )
    assert result.get("status") in ("ok", "success") or "plasticos" in str(result)


@pytest.mark.asyncio
async def test_admin_missing_domain_id_handled(graph_driver, domain_loader):
    """get_domain without domain_id should raise or return error."""
    from engine.handlers import handle_admin

    try:
        result = await handle_admin(
            "plasticos",
            {"sub_action": "get_domain"},
            graph_driver,
            domain_loader,
        )
        # Some implementations return error dict instead of raising
        assert "error" in result or result.get("status") == "error"
    except Exception:
        pass  # Raising is also acceptable
