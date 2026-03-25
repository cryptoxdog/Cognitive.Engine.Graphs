"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, feedback, signal-weights]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine.feedback.signal_weights — SignalWeightCalculator.

Covers:
- Weight formula: P(win|signal) / P(win) x frequency_factor
- Max/min weight clamping
- Frequency adjustment
- Empty outcome set returns baseline weights
- should_recalculate threshold logic
- get_current_weights
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from engine.config.schema import (
    ComputationType,
    DomainSpec,
    FeedbackLoopSpec,
    ScoringDimensionSpec,
    ScoringSource,
    ScoringSpec,
    SignalWeightSpec,
)
from engine.feedback.signal_weights import SignalWeightCalculator


def _spec_with_dimensions(
    dimensions: list[ScoringDimensionSpec] | None = None,
    min_weight: float = 0.1,
    max_weight: float = 3.0,
    baseline: float = 1.0,
    frequency_adjustment: bool = True,
    min_outcomes: int = 100,
    confidence_dampening: bool = False,
) -> DomainSpec:
    dims = dimensions or [
        ScoringDimensionSpec(
            name="geo_score",
            source=ScoringSource.CANDIDATEPROPERTY,
            candidateprop="lat",
            computation=ComputationType.GEODECAY,
            weightkey="w_geo",
            defaultweight=0.5,
        ),
        ScoringDimensionSpec(
            name="price_score",
            source=ScoringSource.CANDIDATEPROPERTY,
            candidateprop="price",
            computation=ComputationType.PRICEALIGNMENT,
            weightkey="w_price",
            defaultweight=0.5,
        ),
    ]
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
        scoring=ScoringSpec(dimensions=dims),
        feedbackloop=FeedbackLoopSpec(
            enabled=True,
            signal_weights=SignalWeightSpec(
                enabled=True,
                min_weight=min_weight,
                max_weight=max_weight,
                baseline_weight=baseline,
                frequency_adjustment=frequency_adjustment,
                min_outcomes_for_recalculation=min_outcomes,
                confidence_dampening=confidence_dampening,
            ),
        ),
    )


def _mock_driver() -> AsyncMock:
    driver = AsyncMock()
    driver.execute_query = AsyncMock(return_value=[])
    return driver


class TestWeightFormula:
    @pytest.mark.asyncio
    async def test_empty_outcomes_returns_baseline(self):
        spec = _spec_with_dimensions()
        driver = _mock_driver()
        driver.execute_query = AsyncMock(return_value=[{"total": 0, "wins": 0}])

        calc = SignalWeightCalculator(driver, spec)
        weights = await calc.recalculate_weights()

        assert weights["geo_score"] == 1.0
        assert weights["price_score"] == 1.0

    @pytest.mark.asyncio
    async def test_high_correlation_boosts_weight(self):
        """If dimension is correlated with wins, weight > baseline."""
        spec = _spec_with_dimensions()
        driver = _mock_driver()
        # Total: 100 outcomes, 50 wins (50% base rate)
        # geo_score: present in 80 outcomes, 60 wins (75% rate) -> lift = 1.5
        # price_score: present in 0 outcomes -> baseline
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"total": 100, "wins": 50}],  # totals
                [{"dim_total": 80, "dim_wins": 60}],  # geo_score dimension
                [],  # store geo weight
                [{"dim_total": 0, "dim_wins": 0}],  # price_score dimension
                [],  # store price weight
            ]
        )

        calc = SignalWeightCalculator(driver, spec)
        weights = await calc.recalculate_weights()

        # geo: lift=1.5, freq_factor=min(1.0, 0.8*10)=1.0, weight=1.5
        assert weights["geo_score"] == 1.5
        # price: no data -> baseline
        assert weights["price_score"] == 1.0

    @pytest.mark.asyncio
    async def test_max_weight_clamping(self):
        spec = _spec_with_dimensions(max_weight=2.0)
        driver = _mock_driver()
        # Very high correlation -> lift should be clamped
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"total": 100, "wins": 10}],  # totals: 10% base win rate
                [{"dim_total": 50, "dim_wins": 50}],  # geo: 100% win rate -> lift=10
                [],  # store
                [{"dim_total": 0, "dim_wins": 0}],  # price
                [],  # store
            ]
        )

        calc = SignalWeightCalculator(driver, spec)
        weights = await calc.recalculate_weights()

        assert weights["geo_score"] == 2.0  # clamped to max

    @pytest.mark.asyncio
    async def test_min_weight_clamping(self):
        spec = _spec_with_dimensions(min_weight=0.2)
        driver = _mock_driver()
        # Negative correlation -> lift < 1
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"total": 100, "wins": 90}],  # 90% base rate
                [{"dim_total": 10, "dim_wins": 1}],  # geo: 10% rate -> lift=0.111
                [],  # store
                [{"dim_total": 0, "dim_wins": 0}],  # price
                [],  # store
            ]
        )

        calc = SignalWeightCalculator(driver, spec)
        weights = await calc.recalculate_weights()

        assert weights["geo_score"] == 0.2  # clamped to min

    @pytest.mark.asyncio
    async def test_frequency_adjustment_penalizes_rare(self):
        """Rare signals (low frequency) get penalized."""
        spec = _spec_with_dimensions(frequency_adjustment=True)
        driver = _mock_driver()
        # Rare dimension: only in 2/100 outcomes
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"total": 100, "wins": 50}],  # totals
                [{"dim_total": 2, "dim_wins": 2}],  # geo: 100% but rare, freq=0.02*10=0.2
                [],  # store
                [{"dim_total": 0, "dim_wins": 0}],  # price
                [],  # store
            ]
        )

        calc = SignalWeightCalculator(driver, spec)
        weights = await calc.recalculate_weights()

        # lift=2.0, freq_factor=0.2, raw=0.4
        assert weights["geo_score"] == pytest.approx(0.4, abs=0.01)


class TestShouldRecalculate:
    @pytest.mark.asyncio
    async def test_below_threshold_returns_false(self):
        spec = _spec_with_dimensions(min_outcomes=100)
        driver = _mock_driver()
        driver.execute_query = AsyncMock(return_value=[{"new_outcomes": 50}])

        calc = SignalWeightCalculator(driver, spec)
        assert await calc.should_recalculate() is False

    @pytest.mark.asyncio
    async def test_above_threshold_returns_true(self):
        spec = _spec_with_dimensions(min_outcomes=100)
        driver = _mock_driver()
        driver.execute_query = AsyncMock(return_value=[{"new_outcomes": 150}])

        calc = SignalWeightCalculator(driver, spec)
        assert await calc.should_recalculate() is True


class TestGetCurrentWeights:
    @pytest.mark.asyncio
    async def test_no_stored_weights_returns_baseline(self):
        spec = _spec_with_dimensions()
        driver = _mock_driver()
        driver.execute_query = AsyncMock(return_value=[])

        calc = SignalWeightCalculator(driver, spec)
        weights = await calc.get_current_weights()

        assert weights["geo_score"] == 1.0
        assert weights["price_score"] == 1.0

    @pytest.mark.asyncio
    async def test_stored_weights_returned(self):
        spec = _spec_with_dimensions()
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            return_value=[
                {"dimension": "geo_score", "weight": 1.5},
                {"dimension": "price_score", "weight": 0.8},
            ]
        )

        calc = SignalWeightCalculator(driver, spec)
        weights = await calc.get_current_weights()

        assert weights["geo_score"] == 1.5
        assert weights["price_score"] == 0.8
