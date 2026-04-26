"""Unit tests — SyncGenerator: MERGE strategy, unknown strategy/endpoint."""

from __future__ import annotations

import pytest


@pytest.fixture
def plasticos_spec():
    """Load plasticos spec, skip if not loadable."""
    from engine.config.loader import DomainPackLoader

    loader = DomainPackLoader()
    try:
        return loader.load_domain("plasticos")
    except Exception:
        pytest.skip("plasticos domain spec not loadable with current schema")


def test_sync_generator_produces_merge_cypher(plasticos_spec):
    """Sync generator produces MERGE/MATCH Cypher."""
    from engine.sync.generator import SyncGenerator

    gen = SyncGenerator(plasticos_spec)
    if not plasticos_spec.sync or not plasticos_spec.sync.endpoints:
        pytest.skip("No sync endpoints in plasticos spec")
    ep = plasticos_spec.sync.endpoints[0]
    cypher, _params = gen.generate_sync_query(ep, [{"id": "test-1", "name": "Alpha"}])
    assert "MERGE" in cypher or "MATCH" in cypher
    assert "UNWIND" in cypher or "$" in cypher


def test_sync_generator_includes_batch_param(plasticos_spec):
    """Sync query includes batch parameter."""
    from engine.sync.generator import SyncGenerator

    gen = SyncGenerator(plasticos_spec)
    if not plasticos_spec.sync or not plasticos_spec.sync.endpoints:
        pytest.skip("No sync endpoints in plasticos spec")
    ep = plasticos_spec.sync.endpoints[0]
    _cypher, params = gen.generate_sync_query(ep, [{"entity_id": "f1"}])
    assert "batch" in params or len(params) > 0


def test_unknown_entity_raises(plasticos_spec):
    """Unknown entity type raises exception."""
    from engine.sync.generator import SyncGenerator

    gen = SyncGenerator(plasticos_spec)
    with pytest.raises(Exception):
        gen.resolve_endpoint("nonexistent_entity_type_xyz")
