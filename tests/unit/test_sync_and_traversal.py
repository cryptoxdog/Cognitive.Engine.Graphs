from pathlib import Path

from engine.config.loader import DomainPackLoader
from engine.sync.generator import SyncGenerator
from engine.traversal.assembler import TraversalAssembler

SPEC_PATH = Path("domains/plasticos/spec.yaml")


def test_sync_generator_uses_canonical_label() -> None:
    loader = DomainPackLoader(config_path=str(SPEC_PATH))
    generator = SyncGenerator(loader)
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
    loader = DomainPackLoader(config_path=str(SPEC_PATH))
    assembler = TraversalAssembler(loader)
    queries = assembler.build_queries()
    assert queries
    assert all("Buyer" not in query for query in queries)
    assert any(":company" in query for query in queries)
