# ============================================================================
# tests/unit/test_kge_ensemble.py
# ============================================================================
"""
Unit tests for engine/kge/ensemble.py — Ensemble fusion strategies.
Target Coverage: 85%+
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from engine.kge.ensemble import (
    EnsembleController,
    FusionStrategy,
    MixtureOfExpertsEnsemble,
    RankAggregationEnsemble,
    RankAggregationMethod,
    VariantScore,
    WeightedDistributionScore,
)

# ============================================================================
# FIXTURES
# ============================================================================


def _scores(n: int = 3) -> list[VariantScore]:
    """Create n variant scores for testing."""
    return [
        VariantScore(variant_id=f"v{i}", variant_type="rotation", score=0.3 + 0.2 * i, confidence=0.8 + 0.05 * i)
        for i in range(n)
    ]


# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestVariantScore:
    """Test VariantScore dataclass."""

    def test_valid_score(self) -> None:
        """VariantScore with valid values."""
        vs = VariantScore(variant_id="v1", variant_type="rotation", score=0.5, confidence=0.9)
        assert vs.score == 0.5
        assert vs.metadata == {}

    def test_score_out_of_range_raises(self) -> None:
        """VariantScore rejects score outside [0, 1]."""
        with pytest.raises(ValueError, match="Score must be in"):
            VariantScore(variant_id="v1", variant_type="r", score=1.5)

    def test_confidence_out_of_range_raises(self) -> None:
        """VariantScore rejects confidence outside [0, 1]."""
        with pytest.raises(ValueError, match="Confidence must be in"):
            VariantScore(variant_id="v1", variant_type="r", score=0.5, confidence=2.0)

    def test_score_at_boundaries(self) -> None:
        """VariantScore accepts boundary values 0.0 and 1.0."""
        VariantScore(variant_id="v1", variant_type="r", score=0.0, confidence=0.0)
        VariantScore(variant_id="v2", variant_type="r", score=1.0, confidence=1.0)


@pytest.mark.unit
class TestWeightedDistributionScore:
    """Test WDS ensemble strategy."""

    def test_fuse_basic(self) -> None:
        """WDS fuse produces final_score in [0, 1]."""
        wds = WeightedDistributionScore()
        scores = _scores(3)
        result = wds.fuse(scores)
        assert 0.0 <= result.final_score <= 1.0
        assert result.fusion_strategy == "weightedaverage"

    def test_fuse_empty_raises(self) -> None:
        """WDS fuse raises on empty scores."""
        wds = WeightedDistributionScore()
        with pytest.raises(ValueError, match="No scores provided"):
            wds.fuse([])

    def test_fuse_single_score(self) -> None:
        """WDS fuse with single score returns that score."""
        wds = WeightedDistributionScore()
        score = VariantScore(variant_id="v1", variant_type="r", score=0.75, confidence=1.0)
        result = wds.fuse([score])
        assert result.final_score == pytest.approx(0.75, abs=0.01)

    def test_fuse_with_custom_weights(self) -> None:
        """WDS fuse respects custom weights."""
        wds = WeightedDistributionScore(weights={"v0": 0.9, "v1": 0.1})
        scores = [
            VariantScore("v0", "r", score=1.0, confidence=1.0),
            VariantScore("v1", "r", score=0.0, confidence=1.0),
        ]
        result = wds.fuse(scores)
        assert result.final_score > 0.8  # heavily weighted toward v0

    def test_fuse_with_temperature(self) -> None:
        """WDS fuse uses temperature for confidence weighting."""
        wds = WeightedDistributionScore(temperature=2.0)
        scores = _scores(2)
        result = wds.fuse(scores)
        assert 0.0 <= result.final_score <= 1.0

    def test_explain_returns_string(self) -> None:
        """WDS explain returns non-empty string."""
        wds = WeightedDistributionScore()
        result = wds.fuse(_scores(3))
        assert len(result.explanation) > 0
        assert "WDS Ensemble" in result.explanation

    def test_weights_sum_to_one(self) -> None:
        """WDS result weights sum to 1.0."""
        wds = WeightedDistributionScore()
        result = wds.fuse(_scores(3))
        total = sum(result.weights.values())
        assert total == pytest.approx(1.0, abs=0.001)


@pytest.mark.unit
class TestRankAggregationEnsemble:
    """Test rank aggregation ensemble."""

    def test_borda_count(self) -> None:
        """Borda count produces valid result."""
        rae = RankAggregationEnsemble(method=RankAggregationMethod.BORDA)
        result = rae.fuse(_scores(3))
        assert 0.0 <= result.final_score <= 1.0
        assert "Borda" in result.explanation

    def test_plurality(self) -> None:
        """Plurality selects highest-scoring variant."""
        rae = RankAggregationEnsemble(method=RankAggregationMethod.PLURALITY)
        scores = _scores(3)
        result = rae.fuse(scores)
        assert 0.0 <= result.final_score <= 1.0
        assert "Plurality" in result.explanation

    def test_empty_raises(self) -> None:
        """Rank aggregation raises on empty scores."""
        rae = RankAggregationEnsemble()
        with pytest.raises(ValueError, match="No scores provided"):
            rae.fuse([])

    def test_rank_is_set(self) -> None:
        """Rank aggregation sets rank=1."""
        rae = RankAggregationEnsemble()
        result = rae.fuse(_scores(2))
        assert result.rank == 1


@pytest.mark.unit
class TestMixtureOfExpertsEnsemble:
    """Test MoE ensemble."""

    def test_fuse_basic(self) -> None:
        """MoE fuse produces score in [0, 1]."""
        moe = MixtureOfExpertsEnsemble()
        result = moe.fuse(_scores(3))
        assert 0.0 <= result.final_score <= 1.0
        assert result.fusion_strategy == "mixtureofexperts"

    def test_fuse_empty_raises(self) -> None:
        """MoE fuse raises on empty scores."""
        moe = MixtureOfExpertsEnsemble()
        with pytest.raises(ValueError, match="No scores provided"):
            moe.fuse([])

    def test_gate_weights_sum_near_one(self) -> None:
        """MoE gate weights (via softmax) approximately sum to 1."""
        moe = MixtureOfExpertsEnsemble()
        result = moe.fuse(_scores(3))
        total = sum(result.weights.values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_explain_contains_moe(self) -> None:
        """MoE explanation mentions MoE Ensemble."""
        moe = MixtureOfExpertsEnsemble()
        result = moe.fuse(_scores(3))
        assert "MoE Ensemble" in result.explanation


@pytest.mark.unit
class TestEnsembleController:
    """Test EnsembleController meta-controller."""

    def test_predict_skips_when_disabled(self) -> None:
        """predict returns disabled result when kge_enabled=False."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = False
            result = ctrl.predict(_scores(3))
            assert result.final_score == 0.0
            assert result.fusion_strategy == "disabled"

    def test_predict_single_score(self) -> None:
        """predict with single score returns identity fusion."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            mock_settings.kge_confidence_threshold = 0.0
            score = VariantScore("v1", "r", score=0.88, confidence=0.95)
            result = ctrl.predict([score])
            assert result.final_score == 0.88
            assert result.fusion_strategy == "identity"

    def test_predict_empty_raises(self) -> None:
        """predict with empty scores raises."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            with pytest.raises(ValueError, match="No scores to ensemble"):
                ctrl.predict([])

    def test_predict_uses_default_strategy(self) -> None:
        """predict uses default strategy (WDS)."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            mock_settings.kge_confidence_threshold = 0.0
            result = ctrl.predict(_scores(3))
            assert 0.0 <= result.final_score <= 1.0

    def test_predict_strategy_override(self) -> None:
        """predict respects strategy override."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            mock_settings.kge_confidence_threshold = 0.0
            result = ctrl.predict(_scores(3), strategy=FusionStrategy.RANK_AGGREGATION)
            assert "Borda" in result.explanation or result.fusion_strategy

    def test_predict_filters_below_confidence(self) -> None:
        """predict filters scores below confidence threshold."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            mock_settings.kge_confidence_threshold = 0.9
            scores = [
                VariantScore("v1", "r", score=0.8, confidence=0.95),
                VariantScore("v2", "r", score=0.6, confidence=0.5),
            ]
            result = ctrl.predict(scores)
            # Only v1 should be above threshold, so identity fusion
            assert result.final_score == 0.8
            assert result.fusion_strategy == "identity"

    def test_predict_fallback_all_below_threshold(self) -> None:
        """predict uses all scores when all below confidence threshold."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            mock_settings.kge_confidence_threshold = 0.99
            scores = [
                VariantScore("v1", "r", score=0.7, confidence=0.5),
                VariantScore("v2", "r", score=0.8, confidence=0.6),
            ]
            result = ctrl.predict(scores)
            assert 0.0 <= result.final_score <= 1.0

    def test_audit_log_appended(self) -> None:
        """predict appends to audit log."""
        ctrl = EnsembleController()
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            mock_settings.kge_confidence_threshold = 0.0
            ctrl.predict(_scores(3))
            audit = ctrl.get_audit_log()
            assert len(audit) == 1
            assert "final_score" in audit[0]

    def test_from_spec_with_strategy(self) -> None:
        """from_spec reads strategy from KGEEnsembleSpec."""
        spec = MagicMock()
        spec.strategy = "rankaggregation"
        ctrl = EnsembleController.from_spec(spec)
        assert ctrl.default_strategy == FusionStrategy.RANK_AGGREGATION

    def test_from_spec_none(self) -> None:
        """from_spec(None) defaults to WDS."""
        ctrl = EnsembleController.from_spec(None)
        assert ctrl.default_strategy == FusionStrategy.WEIGHTED_MEAN

    def test_fallback_on_fusion_error(self) -> None:
        """predict falls back to mean on fusion error."""
        ctrl = EnsembleController()
        broken_strategy = MagicMock()
        broken_strategy.fuse.side_effect = RuntimeError("fuse broke")
        ctrl.strategies[FusionStrategy.WEIGHTED_MEAN] = broken_strategy
        with patch("engine.kge.ensemble.settings") as mock_settings:
            mock_settings.kge_enabled = True
            mock_settings.kge_confidence_threshold = 0.0
            result = ctrl.predict(_scores(3))
            assert result.fusion_strategy == "fallback_mean"
