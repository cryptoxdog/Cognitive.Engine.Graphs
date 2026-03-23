"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, feedback, convergence]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine.feedback.convergence — ConvergenceLoop.

Covers:
- Disabled feedback loop returns immediately
- Enabled loop triggers propagation and weight check
- Weight recalculation gated by should_recalculate
- Full convergence cycle with mock graph driver
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from engine.config.schema import (
    DomainSpec,
    FeedbackLoopSpec,
    SignalWeightSpec,
)
from engine.feedback.convergence import ConvergenceLoop


def _minimal_spec(
    feedback_enabled: bool = False,
    signal_weights_enabled: bool = False,
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
        scoring={"dimensions": []},
        feedbackloop=FeedbackLoopSpec(
            enabled=feedback_enabled,
            signal_weights=SignalWeightSpec(enabled=signal_weights_enabled),
            propagation_boost_factor=1.15,
            propagation_similarity_threshold=0.4,
        ),
    )


def _mock_driver() -> AsyncMock:
    driver = AsyncMock()
    driver.execute_query = AsyncMock(return_value=[])
    return driver


class TestConvergenceLoopDisabled:
    @pytest.mark.asyncio
    async def test_disabled_returns_immediately(self):
        spec = _minimal_spec(feedback_enabled=False)
        driver = _mock_driver()
        loop = ConvergenceLoop(driver, spec)

        result = await loop.on_outcome_recorded({"outcome": "success", "candidate_id": "c1"})

        assert result["feedback_loop"] == "disabled"
        driver.execute_query.assert_not_called()


class TestConvergenceLoopEnabled:
    @pytest.mark.asyncio
    async def test_enabled_triggers_propagation(self):
        spec = _minimal_spec(feedback_enabled=True)
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"affected": 3}],  # propagate_outcome
                [{"new_outcomes": 5}],  # should_recalculate (below threshold)
                [],  # drift_detector: recent
                [],  # drift_detector: baseline
            ]
        )
        loop = ConvergenceLoop(driver, spec)

        result = await loop.on_outcome_recorded(
            {
                "outcome": "success",
                "candidate_id": "c1",
                "match_id": "m1",
            }
        )

        assert result["feedback_loop"] == "enabled"
        assert result["propagation"]["propagated"] is True
        assert result["weights_recalculated"] is False
        assert "drift" in result

    @pytest.mark.asyncio
    async def test_enabled_triggers_weight_recalculation(self):
        spec = _minimal_spec(feedback_enabled=True)
        driver = _mock_driver()

        driver.execute_query = AsyncMock(
            side_effect=[
                [{"affected": 1}],  # propagate_outcome
                [{"new_outcomes": 200}],  # should_recalculate (above threshold)
                [{"total": 200, "wins": 120}],  # recalculate_weights: totals
                # No scoring dimensions so no per-dimension queries
                [],  # drift_detector: recent
                [],  # drift_detector: baseline
            ]
        )
        loop = ConvergenceLoop(driver, spec)

        result = await loop.on_outcome_recorded(
            {
                "outcome": "success",
                "candidate_id": "c1",
            }
        )

        assert result["feedback_loop"] == "enabled"
        assert result["weights_recalculated"] is True
        assert "drift" in result

    @pytest.mark.asyncio
    async def test_failure_outcome_triggers_penalty(self):
        spec = _minimal_spec(feedback_enabled=True)
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"affected": 2}],  # propagate_outcome (penalty)
                [{"new_outcomes": 0}],  # should_recalculate (below threshold)
                [],  # drift_detector: recent
                [],  # drift_detector: baseline
            ]
        )
        loop = ConvergenceLoop(driver, spec)

        result = await loop.on_outcome_recorded(
            {
                "outcome": "failure",
                "candidate_id": "c2",
            }
        )

        assert result["propagation"]["propagated"] is True
        assert result["propagation"]["outcome_type"] == "failure"

    @pytest.mark.asyncio
    async def test_partial_outcome_no_propagation(self):
        spec = _minimal_spec(feedback_enabled=True)
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"new_outcomes": 0}],  # should_recalculate
                [],  # drift_detector: recent
                [],  # drift_detector: baseline
            ]
        )
        loop = ConvergenceLoop(driver, spec)

        result = await loop.on_outcome_recorded(
            {
                "outcome": "partial",
                "candidate_id": "c3",
            }
        )

        assert result["propagation"]["propagated"] is False
