"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, hgkr, ensemble, kge]
owner: engine-team
status: active
--- /L9_META ---

Tests for CrossDimensionalEnsemble — HGKR semantic-level fusion.

Validates iterative cross-dimensional fusion, confidence computation,
and query-context attention mechanism.

Reference:
    Liu et al., "Iterative heterogeneous graph learning for knowledge
    graph-based recommendation", Scientific Reports (2023) 13:6987.
"""

from __future__ import annotations

import pytest

from engine.kge.cross_dimensional_ensemble import (
    CrossDimensionalEnsemble,
    DimensionalScore,
)


@pytest.mark.unit
class TestCrossDimensionalEnsemble:
    """Core fusion behavior tests."""

    def test_empty_scores_returns_zero(self) -> None:
        """No dimensional scores -> zero result."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        result = ensemble.fuse([], {})
        assert result.final_score == 0.0
        assert result.confidence == 0.0
        assert result.iteration_count == 0

    def test_single_dimension(self) -> None:
        """Single dimension -> score equals that dimension's contribution."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [DimensionalScore("geo_decay", 0.8, 1.0)]
        result = ensemble.fuse(scores)
        assert abs(result.final_score - 0.8) < 0.01
        assert result.confidence == 1.0  # single dimension = perfect agreement

    def test_uniform_scores_high_confidence(self) -> None:
        """All dimensions agree -> high confidence."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [
            DimensionalScore("geo_decay", 0.7, 0.25),
            DimensionalScore("community_match", 0.7, 0.25),
            DimensionalScore("temporal", 0.7, 0.25),
            DimensionalScore("kge", 0.7, 0.25),
        ]
        result = ensemble.fuse(scores)
        assert abs(result.final_score - 0.7) < 0.05
        assert result.confidence > 0.9

    def test_divergent_scores_low_confidence(self) -> None:
        """Dimensions disagree -> low confidence."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [
            DimensionalScore("geo_decay", 1.0, 0.5),
            DimensionalScore("community_match", 0.0, 0.5),
        ]
        result = ensemble.fuse(scores)
        assert result.confidence < 0.5

    def test_weighted_fusion(self) -> None:
        """Higher-weighted dimensions influence score more."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=1)  # static only
        scores = [
            DimensionalScore("heavy", 0.9, 0.8),
            DimensionalScore("light", 0.1, 0.2),
        ]
        result = ensemble.fuse(scores)
        # Weighted average: (0.9*0.8 + 0.1*0.2) / (0.8+0.2) = 0.74
        assert result.final_score > 0.6

    def test_score_clamped_to_unit(self) -> None:
        """Final score always in [0.0, 1.0]."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [
            DimensionalScore("a", 1.0, 1.0),
            DimensionalScore("b", 1.0, 1.0),
        ]
        result = ensemble.fuse(scores)
        assert 0.0 <= result.final_score <= 1.0

    def test_depth_1_no_attention(self) -> None:
        """Depth=1: only static fusion, no context attention pass."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=1)
        scores = [
            DimensionalScore("a", 0.8, 0.5),
            DimensionalScore("b", 0.4, 0.5),
        ]
        result = ensemble.fuse(scores)
        # Static fusion: (0.8*0.5 + 0.4*0.5) / 1.0 = 0.6
        assert abs(result.pass_1_score - 0.6) < 0.01
        # With depth=1, no attention pass executed
        assert result.iteration_count == 1

    def test_depth_2_refines_score(self) -> None:
        """Depth=2: attention pass refines the static fusion."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [
            DimensionalScore("a", 0.8, 0.5),
            DimensionalScore("b", 0.4, 0.5),
        ]
        result = ensemble.fuse(scores)
        assert result.iteration_count == 2
        # Pass 2 score may differ from pass 1 due to attention reweighting


@pytest.mark.unit
class TestPropagationDepthValidation:
    """Validate depth parameter constraints from HGKR paper."""

    def test_depth_0_rejected(self) -> None:
        """L=0 is invalid (must propagate at least once)."""
        with pytest.raises(ValueError):
            CrossDimensionalEnsemble(propagation_depth=0)

    def test_depth_6_rejected(self) -> None:
        """L=6 is invalid (paper shows L>3 causes overfitting)."""
        with pytest.raises(ValueError):
            CrossDimensionalEnsemble(propagation_depth=6)

    def test_depth_1_accepted(self) -> None:
        """L=1 is valid (static fusion only)."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=1)
        assert ensemble._depth == 1

    def test_depth_5_accepted(self) -> None:
        """L=5 is the maximum allowed."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=5)
        assert ensemble._depth == 5


@pytest.mark.unit
class TestContextAttention:
    """Validate query-context attention mechanism."""

    def test_attention_weights_sum_to_one(self) -> None:
        """Softmax attention weights sum to 1.0."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [
            DimensionalScore("a", 0.8, 0.5),
            DimensionalScore("b", 0.4, 0.3),
            DimensionalScore("c", 0.6, 0.2),
        ]
        fused = ensemble._static_fusion(scores)
        attention = ensemble._compute_context_attention(scores, {}, fused)
        total = sum(attention.values())
        assert abs(total - 1.0) < 1e-6

    def test_closer_scores_get_higher_attention(self) -> None:
        """Dimensions closer to fused score get more attention weight."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [
            DimensionalScore("close", 0.6, 0.4),
            DimensionalScore("medium", 0.3, 0.3),
            DimensionalScore("far", 0.0, 0.3),
        ]
        fused = ensemble._static_fusion(scores)
        attention = ensemble._compute_context_attention(scores, {}, fused)
        assert attention["close"] > attention["far"]

    def test_empty_scores_empty_attention(self) -> None:
        """No scores -> empty attention dict."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        attention = ensemble._compute_context_attention([], {}, 0.5)
        assert attention == {}


@pytest.mark.unit
class TestConfidence:
    """Validate dimensional agreement confidence metric."""

    def test_perfect_agreement(self) -> None:
        """All scores identical -> confidence = 1.0."""
        ensemble = CrossDimensionalEnsemble()
        scores = [
            DimensionalScore("a", 0.5, 0.5),
            DimensionalScore("b", 0.5, 0.5),
        ]
        confidence = ensemble._compute_confidence(scores)
        assert confidence == 1.0

    def test_max_disagreement(self) -> None:
        """Scores at 0 and 1 -> low confidence."""
        ensemble = CrossDimensionalEnsemble()
        scores = [
            DimensionalScore("a", 0.0, 0.5),
            DimensionalScore("b", 1.0, 0.5),
        ]
        confidence = ensemble._compute_confidence(scores)
        assert confidence < 0.1

    def test_single_score_perfect_confidence(self) -> None:
        """Single dimension -> perfect confidence (no disagreement possible)."""
        ensemble = CrossDimensionalEnsemble()
        scores = [DimensionalScore("a", 0.5, 1.0)]
        confidence = ensemble._compute_confidence(scores)
        assert confidence == 1.0

    def test_empty_scores_zero_confidence(self) -> None:
        """No scores -> zero confidence."""
        ensemble = CrossDimensionalEnsemble()
        confidence = ensemble._compute_confidence([])
        assert confidence == 0.0


@pytest.mark.unit
class TestExplainability:
    """Validate human-readable explanation generation."""

    def test_explain_produces_string(self) -> None:
        """Explain returns a formatted string with all key info."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [
            DimensionalScore("geo_decay", 0.8, 0.5),
            DimensionalScore("community_match", 0.6, 0.5),
        ]
        result = ensemble.fuse(scores)
        explanation = ensemble.explain(result)
        assert isinstance(explanation, str)
        assert "Cross-Dimensional Ensemble" in explanation
        assert "geo_decay" in explanation
        assert "community_match" in explanation
        assert "L=2" in explanation

    def test_explain_shows_pass_scores(self) -> None:
        """Explain includes both pass 1 and pass 2 scores."""
        ensemble = CrossDimensionalEnsemble(propagation_depth=2)
        scores = [DimensionalScore("test", 0.5, 1.0)]
        result = ensemble.fuse(scores)
        explanation = ensemble.explain(result)
        assert "Pass 1" in explanation
        assert "Pass 2" in explanation
