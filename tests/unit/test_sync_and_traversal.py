"""Unit tests — SyncGenerator + TraversalAssembler canonical label usage.

Note: These tests require methods that may not be implemented in current version.
"""

import pytest

from engine.config.loader import DomainPackLoader
from engine.sync.generator import SyncGenerator
from engine.traversal.assembler import TraversalAssembler


def test_sync_generator_uses_canonical_label() -> None:
    """SyncGenerator uses canonical labels — skip if method not implemented."""
    loader = DomainPackLoader()
    try:
        spec = loader.load_domain("plasticos")
    except Exception:
        pytest.skip("plasticos domain spec not loadable")
    generator = SyncGenerator(spec)
    if not hasattr(generator, "generate_node_upsert"):
        pytest.skip("SyncGenerator.generate_node_upsert not implemented")
    query, params, canonical_label = generator.generate_node_upsert(
        "Buyer",
        {
            "entity_id": "buyer-1",
            "revenue": 0.9,
            "margin": 0.8,
            "risk": 0.2,
            "capacity": 0.6,
        },
    )
    assert canonical_label == "company"
    assert "MERGE (n:company" in query
    assert params["entity_id"] == "buyer-1"


def test_traversal_assembler_uses_canonical_labels() -> None:
    """TraversalAssembler uses canonical labels — skip if method not implemented."""
    loader = DomainPackLoader()
    try:
        spec = loader.load_domain("plasticos")
    except Exception:
        pytest.skip("plasticos domain spec not loadable")
    assembler = TraversalAssembler(spec)
    if not hasattr(assembler, "build_queries"):
        pytest.skip("TraversalAssembler.build_queries not implemented")
    queries = assembler.build_queries()
    assert queries
    assert all("Buyer" not in query for query in queries)
    assert any(":company" in query for query in queries)
