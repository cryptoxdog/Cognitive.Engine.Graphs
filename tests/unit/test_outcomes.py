from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from engine.outcomes.engine import OutcomeEngine
from engine.outcomes.schema import OutcomeEvent


@dataclass
class _GraphRecord:
    applied: bool


@dataclass
class _GraphStub:
    seen_event_ids: set[str] = field(default_factory=set)
    edge_weights: dict[tuple[str, str], float] = field(default_factory=dict)

    def apply_outcome_edge_update(
        self,
        *,
        event_id: str,
        entity_id: str,
        outcome_state: str,
        canonical_label: str,
    ) -> _GraphRecord:
        if event_id not in self.seen_event_ids:
            self.seen_event_ids.add(event_id)
            self.edge_weights[(canonical_label, entity_id)] = 1.0
        return _GraphRecord(applied=True)


@dataclass
class _ScoringStub:
    seen_event_ids: set[str] = field(default_factory=set)

    def apply_outcome_feedback(self, *, entity_id: str, outcome_state: str, event_id: str) -> float:
        if event_id in self.seen_event_ids:
            return 0.0
        self.seen_event_ids.add(event_id)
        return 1.0 if outcome_state == "success" else -1.0


def test_outcome_engine_is_idempotent() -> None:
    graph = _GraphStub()
    scoring = _ScoringStub()
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
    assert result1.scoring_adjustment == 1.0
    assert result2.scoring_adjustment == 0.0
