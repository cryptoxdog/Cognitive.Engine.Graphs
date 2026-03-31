from __future__ import annotations

from engine.graph.driver import GraphDriver
from engine.outcomes.schema import OutcomeEvent, ReinforcementResult
from engine.scoring.assembler import ScoringAssembler


class OutcomeEngine:
    def __init__(self, graph_driver: GraphDriver, scoring_assembler: ScoringAssembler):
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
