"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [outcomes]
tags: [outcomes, engine]
owner: engine-team
status: active
--- /L9_META ---
"""

from __future__ import annotations

from typing import Protocol

from engine.outcomes.schema import OutcomeEvent, ReinforcementResult


class OutcomeGraphRecord(Protocol):
    applied: bool


class OutcomeGraphDriver(Protocol):
    def apply_outcome_edge_update(
        self,
        *,
        event_id: str,
        entity_id: str,
        outcome_state: str,
        canonical_label: str,
    ) -> OutcomeGraphRecord: ...


class OutcomeScoringAssembler(Protocol):
    def apply_outcome_feedback(
        self,
        *,
        entity_id: str,
        outcome_state: str,
        event_id: str,
    ) -> float: ...


class OutcomeEngine:
    def __init__(self, graph_driver: OutcomeGraphDriver, scoring_assembler: OutcomeScoringAssembler):
        self.graph_driver = graph_driver
        self.scoring_assembler = scoring_assembler

    async def process(self, tenant: str, event: OutcomeEvent) -> ReinforcementResult:
        graph_record = self.graph_driver.apply_outcome_edge_update(
            event_id=event.event_id,
            entity_id=event.entity_id,
            outcome_state=event.outcome_state,
            canonical_label=event.canonical_label,
        )
        adjustment = self.scoring_assembler.apply_outcome_feedback(
            entity_id=event.entity_id,
            outcome_state=event.outcome_state,
            event_id=event.event_id,
        )
        return ReinforcementResult(
            event_id=event.event_id,
            graph_applied=graph_record.applied,
            scoring_adjustment=adjustment,
        )
