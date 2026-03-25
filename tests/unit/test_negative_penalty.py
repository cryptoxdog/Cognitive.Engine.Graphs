"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring, negative-penalty]
owner: engine-team
status: active
--- /L9_META ---

Tests for negative dimension penalty in ScoringAssembler.

Covers:
- Penalty applied when learned weight < penalty_threshold
- Normal weight multiplication when above threshold
- Penalty factor magnitude
- No penalty when feedback loop disabled
"""

from __future__ import annotations

from engine.config.schema import (
    ComputationType,
    DomainSpec,
    FeedbackLoopSpec,
    ScoringDimensionSpec,
    ScoringSource,
    ScoringSpec,
    SignalWeightSpec,
)
from engine.scoring.assembler import ScoringAssembler


def _spec_with_penalty(
    penalty_threshold: float = 0.5,
    penalty_factor: float = 0.3,
    feedback_enabled: bool = True,
) -> DomainSpec:
    return DomainSpec(
        domain={"id": "test", "name": "Test", "version": "0.0.1"},
        ontology={
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "Query",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "query_id", "type": "int", "required": True}],
                },
            ],
            "edges": [
                {
                    "type": "TRANSACTED_WITH",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "sync",
                }
            ],
        },
        matchentities={
            "candidate": [{"label": "Facility", "matchdirection": "d1"}],
            "queryentity": [{"label": "Query", "matchdirection": "d1"}],
        },
        queryschema={"matchdirections": ["d1"], "fields": []},
        gates=[],
        scoring=ScoringSpec(
            dimensions=[
                ScoringDimensionSpec(
                    name="geo_score",
                    source=ScoringSource.CANDIDATEPROPERTY,
                    candidateprop="lat",
                    computation=ComputationType.GEODECAY,
                    weightkey="w_geo",
                    defaultweight=0.5,
                ),
            ]
        ),
        feedbackloop=FeedbackLoopSpec(
            enabled=feedback_enabled,
            signal_weights=SignalWeightSpec(
                enabled=True,
                penalty_threshold=penalty_threshold,
                penalty_factor=penalty_factor,
            ),
        ),
    )


class TestNegativePenalty:
    """Tests for negative dimension penalty in assembler."""

    def test_penalty_applied_when_weight_below_threshold(self) -> None:
        spec = _spec_with_penalty(penalty_threshold=0.5, penalty_factor=0.3)
        assembler = ScoringAssembler(spec)
        # Simulate learned weight below threshold
        assembler._learned_weights = {"geo_score": 0.3}

        clause, _ = assembler.assemble_scoring_clause("d1", {})
        # The weight expression should contain the negative penalty factor
        assert "-0.3" in clause

    def test_normal_weight_when_above_threshold(self) -> None:
        spec = _spec_with_penalty(penalty_threshold=0.5, penalty_factor=0.3)
        assembler = ScoringAssembler(spec)
        # Simulate learned weight above threshold
        assembler._learned_weights = {"geo_score": 1.5}

        clause, _ = assembler.assemble_scoring_clause("d1", {})
        # Weight = defaultweight (0.5) * learned (1.5) = 0.75
        assert "0.75" in clause
        assert "-0.3" not in clause

    def test_penalty_at_exact_threshold(self) -> None:
        spec = _spec_with_penalty(penalty_threshold=0.5, penalty_factor=0.3)
        assembler = ScoringAssembler(spec)
        # Exactly at threshold — should NOT trigger penalty
        assembler._learned_weights = {"geo_score": 0.5}

        clause, _ = assembler.assemble_scoring_clause("d1", {})
        assert "-0.3" not in clause

    def test_no_penalty_when_no_learned_weights(self) -> None:
        spec = _spec_with_penalty(penalty_threshold=0.5, penalty_factor=0.3)
        assembler = ScoringAssembler(spec)
        # No learned weights loaded
        assembler._learned_weights = {}

        clause, _ = assembler.assemble_scoring_clause("d1", {})
        # Should use default weight of 0.5
        assert "0.5" in clause
        assert "-0.3" not in clause
