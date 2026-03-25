"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, feedback, drift-detection]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine.feedback.drift_detector — DriftDetector.

Covers:
- chi-squared divergence calculation
- Identical distributions return 0.0
- Disjoint distributions return high divergence
- Threshold alerting (above and below threshold)
- Empty data handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from engine.config.schema import (
    DomainSpec,
    FeedbackLoopSpec,
    SignalWeightSpec,
)
from engine.feedback.drift_detector import DriftDetector


def _minimal_spec(
    drift_threshold: float = 0.15,
    drift_window_days: int = 30,
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
            enabled=True,
            signal_weights=SignalWeightSpec(enabled=True),
            drift_threshold=drift_threshold,
            drift_window_days=drift_window_days,
        ),
    )


class TestChiSquaredDivergence:
    """Tests for the static chi-squared divergence calculation."""

    def test_identical_distributions_return_zero(self) -> None:
        dist = {"a": 0.5, "b": 0.3, "c": 0.2}
        assert DriftDetector.chi_squared_divergence(dist, dist) == 0.0

    def test_disjoint_distributions_return_high_divergence(self) -> None:
        recent = {"a": 1.0}
        baseline = {"b": 1.0}
        divergence = DriftDetector.chi_squared_divergence(recent, baseline)
        assert divergence == 2.0  # Each key contributes (1-0)^2 / (1+0) = 1.0

    def test_empty_distributions_return_zero(self) -> None:
        assert DriftDetector.chi_squared_divergence({}, {}) == 0.0

    def test_partial_overlap(self) -> None:
        recent = {"a": 0.6, "b": 0.4}
        baseline = {"a": 0.4, "b": 0.4, "c": 0.2}
        divergence = DriftDetector.chi_squared_divergence(recent, baseline)
        assert divergence > 0.0

    def test_one_empty_distribution(self) -> None:
        recent = {"a": 0.5, "b": 0.5}
        divergence = DriftDetector.chi_squared_divergence(recent, {})
        assert divergence == 1.0  # Each key: (0.5)^2 / 0.5 = 0.5, total 1.0


class TestDriftDetectorCheckAndAlert:
    """Tests for threshold alerting."""

    @pytest.mark.asyncio
    async def test_alert_when_divergence_exceeds_threshold(self) -> None:
        spec = _minimal_spec(drift_threshold=0.1)
        driver = AsyncMock()
        detector = DriftDetector(driver, spec)

        # Mock: recent returns different distribution than baseline
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"dimension": "geo", "frequency": 0.9}, {"dimension": "price", "frequency": 0.1}],
                [{"dimension": "geo", "frequency": 0.3}, {"dimension": "price", "frequency": 0.7}],
            ]
        )

        result = await detector.check_and_alert(threshold=0.1, window_days=30)
        assert result["alert"] is True
        assert result["divergence"] > 0.1

    @pytest.mark.asyncio
    async def test_no_alert_when_divergence_below_threshold(self) -> None:
        spec = _minimal_spec(drift_threshold=10.0)
        driver = AsyncMock()
        detector = DriftDetector(driver, spec)

        # Mock: very similar distributions
        driver.execute_query = AsyncMock(
            side_effect=[
                [{"dimension": "geo", "frequency": 0.5}],
                [{"dimension": "geo", "frequency": 0.5}],
            ]
        )

        result = await detector.check_and_alert(threshold=10.0, window_days=30)
        assert result["alert"] is False
        assert result["divergence"] == 0.0

    @pytest.mark.asyncio
    async def test_insufficient_data_returns_status(self) -> None:
        spec = _minimal_spec()
        driver = AsyncMock()
        detector = DriftDetector(driver, spec)

        # Mock: both queries return empty
        driver.execute_query = AsyncMock(return_value=[])

        result = await detector.check_and_alert(threshold=0.15, window_days=30)
        assert result["status"] == "insufficient_data"
        assert result["divergence"] == 0.0
