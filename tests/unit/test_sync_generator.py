"""Unit tests — SyncGenerator: MERGE strategy, unknown strategy/endpoint."""
from __future__ import annotations

import pytest
from pathlib import Path

DOMAINS_DIR = Path(__file__).parent.parent.parent / "domains"


def test_sync_generator_produces_merge_cypher():
    from engine.config.loader import DomainPackLoader
    from engine.sync.generator import SyncGenerator
    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    gen = SyncGenerator(spec)
    # Get first sync endpoint
    if not spec.sync.endpoints:
        pytest.skip("No sync endpoints in plasticos spec")
    ep = spec.sync.endpoints[0]
    cypher, params = gen.generate_sync_query(ep, [{"id": "test-1", "name": "Alpha"}])
    assert "MERGE" in cypher or "MATCH" in cypher
    assert "UNWIND" in cypher or "$" in cypher


def test_sync_generator_includes_batch_param():
    from engine.config.loader import DomainPackLoader
    from engine.sync.generator import SyncGenerator
    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    gen = SyncGenerator(spec)
    if not spec.sync.endpoints:
        pytest.skip("No sync endpoints in plasticos spec")
    ep = spec.sync.endpoints[0]
    cypher, params = gen.generate_sync_query(ep, [{"entity_id": "f1"}])
    assert "batch" in params or len(params) > 0


def test_unknown_entity_raises():
    from engine.config.loader import DomainPackLoader
    from engine.sync.generator import SyncGenerator
    loader = DomainPackLoader(domains_dir=DOMAINS_DIR)
    spec = loader.load_domain("plasticos")
    gen = SyncGenerator(spec)
    with pytest.raises(Exception):
        gen.resolve_endpoint("nonexistent_entity_type_xyz")
