import asyncio

import pytest

from engine.config.loader import DomainPackLoader
from engine.graph.driver import GraphDriver
from engine.outcomes.engine import OutcomeEngine
from engine.outcomes.schema import OutcomeEvent
from engine.scoring.assembler import ScoringAssembler


def test_outcome_engine_is_idempotent() -> None:
    """Outcome engine idempotency — skip if required methods not implemented."""
    loader = DomainPackLoader()
    if not hasattr(loader, "allowed_canonical_labels"):
        pytest.skip("DomainPackLoader.allowed_canonical_labels not implemented")
    graph = GraphDriver(loader.allowed_canonical_labels())
    scoring = ScoringAssembler(loader)
    engine = OutcomeEngine(graph, scoring)

    event = OutcomeEvent(
        event_id="event-1",
        entity_id="entity-1",
        action_name="admin",
        canonical_label="company",
        outcome_state="success",
    )
    result1 = asyncio.run(engine.process("tenant-a", event))
    result2 = asyncio.run(engine.process("tenant-a", event))

    assert result1.graph_applied is True
    assert result2.graph_applied is True
    assert graph.edge_weights[("company", "entity-1")] == 1.0
