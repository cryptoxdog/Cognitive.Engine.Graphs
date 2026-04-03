"""Integration tests — sync handler: merge, idempotency, unknown entity."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_sync_merges_facilities(graph_driver, domain_loader, clean_db):
    from engine.handlers import handle_sync

    result = await handle_sync(
        "plasticos",
        {
            "entity_type": "facilities",
            "batch": [
                {"id": "fac-001", "name": "Omega Plastics", "contamination_tolerance": 0.03},
                {"id": "fac-002", "name": "Delta Recycle", "contamination_tolerance": 0.07},
            ],
        },
        graph_driver,
        domain_loader,
    )
    assert result.get("status") in ("ok", "success")


@pytest.mark.asyncio
async def test_sync_idempotent_on_second_call(graph_driver, domain_loader, clean_db):
    from engine.handlers import handle_sync

    payload = {
        "entity_type": "facilities",
        "batch": [{"id": "fac-idem", "name": "Idem Facility"}],
    }
    r1 = await handle_sync("plasticos", payload, graph_driver, domain_loader)
    r2 = await handle_sync("plasticos", payload, graph_driver, domain_loader)
    assert r1.get("status") in ("ok", "success")
    assert r2.get("status") in ("ok", "success")


def test_sync_unknown_entity_type_raises(domain_loader):
    """RULE 3: unknown entity_type raises, not silent pass-through."""
    from engine.sync.generator import SyncGenerator

    spec = domain_loader.load_domain("plasticos")
    gen = SyncGenerator(spec)
    with pytest.raises(Exception):
        gen.resolve_endpoint("nonexistent_entity_type_xyz")
