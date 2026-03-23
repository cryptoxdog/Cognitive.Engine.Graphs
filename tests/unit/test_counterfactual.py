"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, counterfactual, scenario-generation]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for R6 counterfactual scenario generation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.causal.counterfactual import (
    _INTERVENTION_ADD_DIMENSION,
    CounterfactualGenerator,
)
from engine.config.schema import CounterfactualSpec


def _make_spec(
    max_scenarios: int = 3,
    min_confidence: float = 0.3,
    pool_size: int = 10,
) -> CounterfactualSpec:
    return CounterfactualSpec(
        enabled=True,
        max_scenarios_per_outcome=max_scenarios,
        min_confidence=min_confidence,
        comparison_pool_size=pool_size,
    )


def _mock_driver() -> MagicMock:
    driver = MagicMock()
    driver.execute_query = AsyncMock()
    return driver


@pytest.mark.unit
class TestCounterfactualGenerator:
    """Test counterfactual scenario generation."""

    @pytest.mark.asyncio
    async def test_generate_missing_dimension_scenario(self) -> None:
        """Generates scenario when positive outcomes have dimensions the negative lacks."""
        spec = _make_spec()
        driver = _mock_driver()

        # Outcome fingerprint (failure): missing "geodecay"
        driver.execute_query.side_effect = [
            # get_outcome_fingerprint
            [
                {
                    "active_dimensions": ["communitymatch", "pricealignment"],
                    "dimension_weights": {"communitymatch": 0.3, "pricealignment": 0.25},
                    "gates_passed": ["density_range"],
                    "match_direction": "forward",
                    "candidate_count": 10,
                    "outcome": "failure",
                }
            ],
            # find_similar_positives: 3 winners all have "geodecay"
            [
                {
                    "active_dimensions": ["geodecay", "communitymatch", "pricealignment"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "outcome_id": "pos_1",
                },
                {
                    "active_dimensions": ["geodecay", "communitymatch"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "outcome_id": "pos_2",
                },
                {
                    "active_dimensions": ["geodecay", "pricealignment"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "outcome_id": "pos_3",
                },
            ],
            # store_scenarios
            [],
        ]

        gen = CounterfactualGenerator(spec, driver, "test_domain")
        scenarios = await gen.generate_for_outcome("out_fail_001")

        assert len(scenarios) >= 1
        geo_scenario = next((s for s in scenarios if s["key_difference"] == "geodecay"), None)
        assert geo_scenario is not None
        assert geo_scenario["intervention_type"] == _INTERVENTION_ADD_DIMENSION
        assert geo_scenario["confidence"] == 1.0  # 3/3

    @pytest.mark.asyncio
    async def test_confidence_filtering(self) -> None:
        """Scenarios below min_confidence are excluded."""
        spec = _make_spec(min_confidence=0.5)
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [
                {
                    "active_dimensions": ["communitymatch"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "match_direction": "forward",
                    "candidate_count": 5,
                    "outcome": "failure",
                }
            ],
            # 10 positives, only 3 have "geodecay" → 3/10 = 0.3 < 0.5
            [
                {
                    "active_dimensions": ["geodecay", "communitymatch"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "outcome_id": f"pos_{i}",
                }
                if i < 3
                else {
                    "active_dimensions": ["communitymatch", "pricealignment"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "outcome_id": f"pos_{i}",
                }
                for i in range(10)
            ],
            [],
        ]

        gen = CounterfactualGenerator(spec, driver, "test_domain")
        scenarios = await gen.generate_for_outcome("out_fail_002")

        # pricealignment is in 7/10 = 0.7 >= 0.5, should appear
        # geodecay is in 3/10 = 0.3 < 0.5, should NOT appear
        geo_scenarios = [s for s in scenarios if s["key_difference"] == "geodecay"]
        price_scenarios = [s for s in scenarios if s["key_difference"] == "pricealignment"]
        assert len(geo_scenarios) == 0
        assert len(price_scenarios) >= 1

    @pytest.mark.asyncio
    async def test_max_scenarios_limit(self) -> None:
        """Number of scenarios is capped at max_scenarios_per_outcome."""
        spec = _make_spec(max_scenarios=2)
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [
                {
                    "active_dimensions": [],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "match_direction": "forward",
                    "candidate_count": 5,
                    "outcome": "failure",
                }
            ],
            # Positives with many different dimensions
            [
                {
                    "active_dimensions": ["dim_a", "dim_b", "dim_c", "dim_d"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "outcome_id": f"pos_{i}",
                }
                for i in range(5)
            ],
            [],
        ]

        gen = CounterfactualGenerator(spec, driver, "test_domain")
        scenarios = await gen.generate_for_outcome("out_fail_003")

        assert len(scenarios) <= 2

    @pytest.mark.asyncio
    async def test_no_fingerprint_returns_empty(self) -> None:
        """Returns empty when outcome has no fingerprint."""
        spec = _make_spec()
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [],  # No outcome found
        ]

        gen = CounterfactualGenerator(spec, driver, "test_domain")
        scenarios = await gen.generate_for_outcome("nonexistent")

        assert scenarios == []

    @pytest.mark.asyncio
    async def test_no_positives_returns_empty(self) -> None:
        """Returns empty when no positive outcomes found for comparison."""
        spec = _make_spec()
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [
                {
                    "active_dimensions": ["geo"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "match_direction": "forward",
                    "candidate_count": 5,
                    "outcome": "failure",
                }
            ],
            [],  # No positives
        ]

        gen = CounterfactualGenerator(spec, driver, "test_domain")
        scenarios = await gen.generate_for_outcome("out_fail_004")

        assert scenarios == []

    @pytest.mark.asyncio
    async def test_scenario_has_required_fields(self) -> None:
        """Each scenario has all required fields."""
        spec = _make_spec()
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [
                {
                    "active_dimensions": ["communitymatch"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "match_direction": "forward",
                    "candidate_count": 5,
                    "outcome": "failure",
                }
            ],
            [
                {
                    "active_dimensions": ["geodecay", "communitymatch"],
                    "dimension_weights": {},
                    "gates_passed": [],
                    "outcome_id": "pos_1",
                },
            ],
            [],
        ]

        gen = CounterfactualGenerator(spec, driver, "test_domain")
        scenarios = await gen.generate_for_outcome("out_fail_005")

        for scenario in scenarios:
            assert "scenario_id" in scenario
            assert "actual_outcome" in scenario
            assert "counterfactual_outcome" in scenario
            assert "intervention_type" in scenario
            assert "confidence" in scenario
            assert "key_difference" in scenario
            assert scenario["actual_outcome"] == "out_fail_005"
            assert scenario["counterfactual_outcome"] == "success"
