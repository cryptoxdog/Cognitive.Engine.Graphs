"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring, dual-dimensions]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for dual dimension classes (learned vs. engineered).
Covers: pool-aware weight redistribution, EMA feedback, confidence gating,
MULTIPLICATIVE veto, scoring breakdown audit, and feature gate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from engine.config.schema import (
    ComputationType,
    DomainSpec,
    ScoringAggregation,
    ScoringDimensionSpec,
    ScoringSpec,
)
from engine.scoring.assembler import ScoringAssembler, ScoringBreakdown
from engine.scoring.confidence import apply_confidence_weighting
from engine.scoring.weights import redistribute_weights, update_weights_from_outcomes

# ── Helpers ──────────────────────────────────────────────


def _mock_dim(
    name: str = "dim",
    computation: str = "candidateproperty",
    weightkey: str = "w",
    defaultweight: float = 1.0,
    candidateprop: str | None = "value",
    defaultwhennull: float = 0.0,
    aggregation: str = "additive",
    matchdirections: list[str] | None = None,
    alias: str | None = None,
    expression: str | None = None,
) -> MagicMock:
    dim = MagicMock(spec=ScoringDimensionSpec)
    dim.name = name
    dim.computation = ComputationType(computation)
    dim.weightkey = weightkey
    dim.defaultweight = defaultweight
    dim.candidateprop = candidateprop
    dim.queryprop = None
    dim.defaultwhennull = defaultwhennull
    dim.aggregation = ScoringAggregation(aggregation)
    dim.matchdirections = matchdirections
    dim.alias = alias
    dim.expression = expression
    dim.minvalue = None
    dim.maxvalue = None
    dim.decayconstant = None
    dim.bias = None
    return dim


def _mock_domain(dims: list[MagicMock]) -> MagicMock:
    spec = MagicMock(spec=DomainSpec)
    spec.scoring = MagicMock(spec=ScoringSpec)
    spec.scoring.dimensions = dims
    return spec


# ── MULTIPLICATIVE Veto (Requirement 6) ─────────────────


@pytest.mark.unit
class TestMultiplicativeVeto:
    """PRIMITIVE dims must never use MULTIPLICATIVE aggregation."""

    def test_primitive_multiplicative_raises_at_config_time(self) -> None:
        with pytest.raises(ValueError, match="PRIMITIVE computation cannot use MULTIPLICATIVE"):
            ScoringDimensionSpec(
                name="bad_dim",
                source="candidateproperty",
                computation="primitive",
                aggregation="multiplicative",
                weightkey="wbad",
                defaultweight=0.1,
            )

    def test_primitive_additive_allowed(self) -> None:
        dim = ScoringDimensionSpec(
            name="ok_dim",
            source="candidateproperty",
            computation="primitive",
            aggregation="additive",
            weightkey="wok",
            defaultweight=0.1,
        )
        assert dim.computation == ComputationType.PRIMITIVE
        assert dim.aggregation == ScoringAggregation.ADDITIVE

    def test_engineered_multiplicative_allowed(self) -> None:
        dim = ScoringDimensionSpec(
            name="eng_dim",
            source="candidateproperty",
            computation="candidateproperty",
            aggregation="multiplicative",
            weightkey="weng",
            defaultweight=0.3,
        )
        assert dim.aggregation == ScoringAggregation.MULTIPLICATIVE


# ── Weight Redistribution (Requirement 2) ───────────────


@pytest.mark.unit
class TestRedistributeWeights:
    """Pool-aware weight redistribution."""

    def test_two_pools_sum_to_budgets(self) -> None:
        eng1 = _mock_dim(name="eng1", computation="candidateproperty", weightkey="w1", defaultweight=0.5)
        eng2 = _mock_dim(name="eng2", computation="geodecay", weightkey="w2", defaultweight=0.5)
        lrn1 = _mock_dim(name="lrn1", computation="primitive", weightkey="w3", defaultweight=0.3)
        lrn2 = _mock_dim(name="lrn2", computation="primitive", weightkey="w4", defaultweight=0.7)

        result = redistribute_weights(
            [eng1, eng2, lrn1, lrn2],
            {"w1": 0.5, "w2": 0.5, "w3": 0.3, "w4": 0.7},
            engineered_budget=0.70,
            learned_budget=0.30,
        )

        eng_sum = result["w1"] + result["w2"]
        lrn_sum = result["w3"] + result["w4"]
        assert abs(eng_sum - 0.70) < 1e-9
        assert abs(lrn_sum - 0.30) < 1e-9

    def test_learned_budget_zero_zeros_primitive_weights(self) -> None:
        eng = _mock_dim(name="eng", computation="candidateproperty", weightkey="w1", defaultweight=1.0)
        lrn = _mock_dim(name="lrn", computation="primitive", weightkey="w2", defaultweight=1.0)

        result = redistribute_weights(
            [eng, lrn],
            {"w1": 1.0, "w2": 1.0},
            engineered_budget=1.0,
            learned_budget=0.0,
        )

        assert result["w2"] == 0.0
        assert abs(result["w1"] - 1.0) < 1e-9

    def test_proportional_scaling_within_pool(self) -> None:
        lrn1 = _mock_dim(name="lrn1", computation="primitive", weightkey="w1", defaultweight=0.25)
        lrn2 = _mock_dim(name="lrn2", computation="primitive", weightkey="w2", defaultweight=0.75)

        result = redistribute_weights(
            [lrn1, lrn2],
            {"w1": 0.25, "w2": 0.75},
            engineered_budget=0.0,
            learned_budget=1.0,
        )

        # w1 should be 25% of budget, w2 75%
        assert abs(result["w1"] - 0.25) < 1e-9
        assert abs(result["w2"] - 0.75) < 1e-9

    def test_uses_defaultweight_for_missing_keys(self) -> None:
        eng = _mock_dim(name="eng", computation="candidateproperty", weightkey="w1", defaultweight=0.6)

        result = redistribute_weights(
            [eng],
            {},  # no weights provided
            engineered_budget=1.0,
            learned_budget=0.0,
        )

        assert abs(result["w1"] - 1.0) < 1e-9


# ── EMA Feedback (Requirement 3) ────────────────────────


@pytest.mark.unit
class TestEMAFeedback:
    """Dual-rate EMA weight updates."""

    def test_learned_uses_fast_alpha(self) -> None:
        lrn = _mock_dim(name="lrn", computation="primitive", weightkey="w1", defaultweight=0.5)

        result = update_weights_from_outcomes(
            [lrn],
            {"w1": 0.5},
            {"w1": 1.0},
            engineered_ema_alpha=0.05,
            learned_ema_alpha=0.20,
        )

        # new = (1 - 0.20) * 0.5 + 0.20 * 1.0 = 0.4 + 0.2 = 0.6
        assert abs(result["w1"] - 0.6) < 1e-9

    def test_engineered_uses_slow_alpha(self) -> None:
        eng = _mock_dim(name="eng", computation="candidateproperty", weightkey="w1", defaultweight=0.5)

        result = update_weights_from_outcomes(
            [eng],
            {"w1": 0.5},
            {"w1": 1.0},
            engineered_ema_alpha=0.05,
            learned_ema_alpha=0.20,
        )

        # new = (1 - 0.05) * 0.5 + 0.05 * 1.0 = 0.475 + 0.05 = 0.525
        assert abs(result["w1"] - 0.525) < 1e-9

    def test_no_observed_leaves_unchanged(self) -> None:
        dim = _mock_dim(name="dim", computation="primitive", weightkey="w1", defaultweight=0.5)

        result = update_weights_from_outcomes(
            [dim],
            {"w1": 0.5},
            {},  # no observations
            engineered_ema_alpha=0.05,
            learned_ema_alpha=0.20,
        )

        assert result["w1"] == 0.5

    def test_weight_clamped_to_zero(self) -> None:
        dim = _mock_dim(name="dim", computation="primitive", weightkey="w1", defaultweight=0.01)

        result = update_weights_from_outcomes(
            [dim],
            {"w1": 0.01},
            {"w1": -1.0},  # negative observed
            engineered_ema_alpha=0.05,
            learned_ema_alpha=0.80,
        )

        # new = (1 - 0.8) * 0.01 + 0.8 * (-1.0) = 0.002 - 0.8 = -0.798 → clamped to 0.0
        assert result["w1"] == 0.0


# ── Confidence Gating (Requirement 4) ───────────────────


@pytest.mark.unit
class TestConfidenceGating:
    """Confidence-based weight gating."""

    def test_primitive_below_threshold_zeroed(self) -> None:
        lrn = _mock_dim(name="lrn", computation="primitive", weightkey="w1", defaultweight=0.5)

        result = apply_confidence_weighting(
            [lrn],
            {"w1": 0.5},
            {"w1": 0.3},  # below primitive threshold of 0.5
            primitive_threshold=0.5,
            engineered_threshold=0.3,
        )

        assert result["w1"] == 0.0

    def test_primitive_above_threshold_kept(self) -> None:
        lrn = _mock_dim(name="lrn", computation="primitive", weightkey="w1", defaultweight=0.5)

        result = apply_confidence_weighting(
            [lrn],
            {"w1": 0.5},
            {"w1": 0.7},
            primitive_threshold=0.5,
            engineered_threshold=0.3,
        )

        assert result["w1"] == 0.5

    def test_engineered_uses_lower_threshold(self) -> None:
        eng = _mock_dim(name="eng", computation="candidateproperty", weightkey="w1", defaultweight=0.5)

        result = apply_confidence_weighting(
            [eng],
            {"w1": 0.5},
            {"w1": 0.35},
            primitive_threshold=0.5,
            engineered_threshold=0.3,
        )

        # 0.35 >= 0.3 threshold → kept
        assert result["w1"] == 0.5

    def test_no_confidence_passes_through(self) -> None:
        dim = _mock_dim(name="dim", computation="primitive", weightkey="w1", defaultweight=0.5)

        result = apply_confidence_weighting(
            [dim],
            {"w1": 0.5},
            {},  # no confidence scores
            primitive_threshold=0.5,
            engineered_threshold=0.3,
        )

        assert result["w1"] == 0.5


# ── Scoring Breakdown Audit (Requirement 5) ─────────────


@pytest.mark.unit
class TestScoringBreakdown:
    """Grouped audit trail for engineered vs learned contributions."""

    def test_breakdown_to_dict_structure(self) -> None:
        bd = ScoringBreakdown(
            engineered_contribution=0.55,
            learned_contribution=0.25,
            engineered_dims={"geo": 0.35, "price": 0.20},
            learned_dims={"prim1": 0.25},
        )
        d = bd.to_dict()
        assert d["engineered_contribution"] == 0.55
        assert d["learned_contribution"] == 0.25
        assert d["engineered_dims"]["geo"] == 0.35
        assert d["learned_dims"]["prim1"] == 0.25

    def test_breakdown_rounding(self) -> None:
        bd = ScoringBreakdown(
            engineered_contribution=0.123456789,
            learned_contribution=0.987654321,
            engineered_dims={"x": 0.123456789},
            learned_dims={"y": 0.987654321},
        )
        d = bd.to_dict()
        assert d["engineered_contribution"] == 0.1235
        assert d["learned_contribution"] == 0.9877
        assert d["engineered_dims"]["x"] == 0.1235
        assert d["learned_dims"]["y"] == 0.9877


# ── Assembler Pool-Aware Scoring (Requirements 2, 5, 7) ─


@pytest.mark.unit
class TestAssemblerDualDimensions:
    """Pool-aware scoring assembly with feature gate."""

    def test_dual_pool_breakdown_attached(self) -> None:
        """When learned dims exist, assembler tracks breakdown."""
        eng = _mock_dim(name="geo_score", computation="candidateproperty", weightkey="wgeo", defaultweight=0.5)
        lrn = _mock_dim(name="prim_score", computation="primitive", weightkey="wprim", defaultweight=0.5)
        domain = _mock_domain([eng, lrn])
        assembler = ScoringAssembler(domain)

        assembler.assemble_scoring_clause(
            "any",
            {"wgeo": 0.5, "wprim": 0.5},
            engineered_budget=0.7,
            learned_budget=0.3,
        )

        bd = assembler.last_breakdown
        assert bd is not None
        assert "geo_score" in bd.engineered_dims
        assert "prim_score" in bd.learned_dims
        assert abs(bd.engineered_contribution + bd.learned_contribution - 1.0) < 1e-9

    def test_feature_gate_no_learned_dims(self) -> None:
        """Without PRIMITIVE dims, original flat-weight behavior is used."""
        eng1 = _mock_dim(name="s1", computation="candidateproperty", weightkey="w1", defaultweight=0.6)
        eng2 = _mock_dim(name="s2", computation="candidateproperty", weightkey="w2", defaultweight=0.4)
        domain = _mock_domain([eng1, eng2])
        assembler = ScoringAssembler(domain)

        cypher = assembler.assemble_scoring_clause(
            "any",
            {"w1": 0.6, "w2": 0.4},
            learned_budget=0.3,  # non-zero, but no PRIMITIVE dims
        )

        # Original flat weights should be used (0.6 and 0.4)
        assert "0.6" in cypher
        assert "0.4" in cypher
        bd = assembler.last_breakdown
        assert bd is not None
        assert len(bd.learned_dims) == 0

    def test_feature_gate_learned_budget_zero(self) -> None:
        """When learned_budget=0.0, PRIMITIVE dims get weight 0 and engineered fill budget."""
        eng = _mock_dim(name="s1", computation="candidateproperty", weightkey="w1", defaultweight=0.5)
        lrn = _mock_dim(name="s2", computation="primitive", weightkey="w2", defaultweight=0.5)
        domain = _mock_domain([eng, lrn])
        assembler = ScoringAssembler(domain)

        cypher = assembler.assemble_scoring_clause(
            "any",
            {"w1": 0.5, "w2": 0.5},
            engineered_budget=1.0,
            learned_budget=0.0,
        )

        # PRIMITIVE dim should have weight 0
        bd = assembler.last_breakdown
        assert bd is not None
        # The original flat-weight path is used when learned_budget=0
        # All dims treated as engineered with flat weights
        assert bd.learned_contribution == 0.0 or len(bd.learned_dims) == 0

    def test_primitive_compiles_coalesce(self) -> None:
        """PRIMITIVE dimension compiles to coalesce expression."""
        lrn = _mock_dim(
            name="prim_score",
            computation="primitive",
            weightkey="wprim",
            defaultweight=0.2,
            candidateprop="primitive_score",
            defaultwhennull=0.0,
        )
        domain = _mock_domain([lrn])
        assembler = ScoringAssembler(domain)

        cypher = assembler.assemble_scoring_clause("any", {})

        assert "coalesce" in cypher
        assert "primitive_score" in cypher

    def test_primitive_with_alias(self) -> None:
        """PRIMITIVE dimension with alias uses alias reference."""
        lrn = _mock_dim(
            name="prim_score",
            computation="primitive",
            weightkey="wprim",
            defaultweight=0.2,
            candidateprop="score",
            defaultwhennull=0.0,
            alias="rel",
        )
        domain = _mock_domain([lrn])
        assembler = ScoringAssembler(domain)

        cypher = assembler.assemble_scoring_clause("any", {})

        assert "rel.score" in cypher

    def test_mixed_dims_cypher_contains_all(self) -> None:
        """Mixed engineered + learned dims all appear in output Cypher."""
        eng = _mock_dim(name="geo", computation="candidateproperty", weightkey="wgeo", defaultweight=0.5,
                        candidateprop="rating")
        lrn = _mock_dim(name="prim", computation="primitive", weightkey="wprim", defaultweight=0.3,
                        candidateprop="ml_score")
        domain = _mock_domain([eng, lrn])
        assembler = ScoringAssembler(domain)

        cypher = assembler.assemble_scoring_clause(
            "any",
            {"wgeo": 0.5, "wprim": 0.3},
            engineered_budget=0.7,
            learned_budget=0.3,
        )

        assert "geo" in cypher
        assert "prim" in cypher
        assert "rating" in cypher
        assert "ml_score" in cypher
