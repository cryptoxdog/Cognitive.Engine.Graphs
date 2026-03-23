"""
--- L9_META ---
l9_schema: 1
origin: tests
engine: graph
layer: [tests]
tags: [hoprag, helpfulness, unit-test]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine.scoring.helpfulness module.
"""

from __future__ import annotations

import pytest

from engine.scoring.helpfulness import (
    HelpfulnessResult,
    HelpfulnessScorer,
    compile_helpfulness_cypher,
    compute_helpfulness,
)


class TestHelpfulnessScorer:
    """Tests for HelpfulnessScorer class."""

    def test_default_alpha(self) -> None:
        """Default alpha should be 0.5."""
        scorer = HelpfulnessScorer()
        assert scorer.alpha == 0.5

    def test_custom_alpha(self) -> None:
        """Custom alpha should be stored correctly."""
        scorer = HelpfulnessScorer(alpha=0.7)
        assert scorer.alpha == 0.7

    def test_alpha_out_of_range_low(self) -> None:
        """Alpha below 0.0 should raise ValueError."""
        with pytest.raises(ValueError, match="alpha must be in"):
            HelpfulnessScorer(alpha=-0.1)

    def test_alpha_out_of_range_high(self) -> None:
        """Alpha above 1.0 should raise ValueError."""
        with pytest.raises(ValueError, match="alpha must be in"):
            HelpfulnessScorer(alpha=1.1)

    def test_compute_equal_balance(self) -> None:
        """alpha=0.5 should give arithmetic mean."""
        scorer = HelpfulnessScorer(alpha=0.5)
        result = scorer.compute(similarity=0.8, importance=0.4)
        assert isinstance(result, HelpfulnessResult)
        assert result.score == pytest.approx(0.6, abs=1e-9)

    def test_compute_pure_similarity(self) -> None:
        """alpha=1.0 should return pure similarity."""
        scorer = HelpfulnessScorer(alpha=1.0)
        result = scorer.compute(similarity=0.8, importance=0.2)
        assert result.score == pytest.approx(0.8, abs=1e-9)

    def test_compute_pure_importance(self) -> None:
        """alpha=0.0 should return pure importance."""
        scorer = HelpfulnessScorer(alpha=0.0)
        result = scorer.compute(similarity=0.8, importance=0.2)
        assert result.score == pytest.approx(0.2, abs=1e-9)

    def test_compute_boundary_zeros(self) -> None:
        """Both inputs zero should produce zero score."""
        scorer = HelpfulnessScorer()
        result = scorer.compute(similarity=0.0, importance=0.0)
        assert result.score == pytest.approx(0.0, abs=1e-9)

    def test_compute_boundary_ones(self) -> None:
        """Both inputs one should produce one score."""
        scorer = HelpfulnessScorer()
        result = scorer.compute(similarity=1.0, importance=1.0)
        assert result.score == pytest.approx(1.0, abs=1e-9)

    def test_compute_similarity_out_of_range(self) -> None:
        """Similarity outside [0, 1] should raise ValueError."""
        scorer = HelpfulnessScorer()
        with pytest.raises(ValueError, match="similarity must be in"):
            scorer.compute(similarity=1.5, importance=0.5)

    def test_compute_importance_out_of_range(self) -> None:
        """Importance outside [0, 1] should raise ValueError."""
        scorer = HelpfulnessScorer()
        with pytest.raises(ValueError, match="importance must be in"):
            scorer.compute(similarity=0.5, importance=-0.1)

    def test_result_fields(self) -> None:
        """Result should preserve all input values."""
        scorer = HelpfulnessScorer(alpha=0.3)
        result = scorer.compute(similarity=0.7, importance=0.9)
        assert result.similarity == 0.7
        assert result.importance == 0.9
        assert result.alpha == 0.3

    def test_compute_batch(self) -> None:
        """Batch computation should return correct number of results."""
        scorer = HelpfulnessScorer(alpha=0.5)
        candidates = [
            {"similarity": 0.8, "importance": 0.4},
            {"similarity": 0.6, "importance": 0.6},
            {"similarity": 0.9, "importance": 0.1},
        ]
        results = scorer.compute_batch(candidates)
        assert len(results) == 3
        assert results[0].score == pytest.approx(0.6, abs=1e-9)
        assert results[1].score == pytest.approx(0.6, abs=1e-9)
        assert results[2].score == pytest.approx(0.5, abs=1e-9)

    def test_rank_ordering(self) -> None:
        """Rank should return candidates sorted by score descending."""
        scorer = HelpfulnessScorer(alpha=0.5)
        candidates = [
            {"similarity": 0.3, "importance": 0.1},  # 0.2
            {"similarity": 0.9, "importance": 0.9},  # 0.9
            {"similarity": 0.5, "importance": 0.5},  # 0.5
        ]
        ranked = scorer.rank(candidates)
        assert ranked[0][0] == 1  # Original index 1 (score 0.9)
        assert ranked[1][0] == 2  # Original index 2 (score 0.5)
        assert ranked[2][0] == 0  # Original index 0 (score 0.2)

    def test_rank_top_k(self) -> None:
        """Rank with top_k should limit results."""
        scorer = HelpfulnessScorer()
        candidates = [
            {"similarity": 0.1, "importance": 0.1},
            {"similarity": 0.5, "importance": 0.5},
            {"similarity": 0.9, "importance": 0.9},
        ]
        ranked = scorer.rank(candidates, top_k=2)
        assert len(ranked) == 2


class TestComputeHelpfulness:
    """Tests for convenience function compute_helpfulness."""

    def test_basic(self) -> None:
        """Basic computation with defaults."""
        assert compute_helpfulness(0.8, 0.4) == pytest.approx(0.6, abs=1e-9)

    def test_custom_alpha(self) -> None:
        """Custom alpha parameter."""
        result = compute_helpfulness(0.8, 0.4, alpha=0.7)
        expected = 0.7 * 0.8 + 0.3 * 0.4
        assert result == pytest.approx(expected, abs=1e-9)


class TestCompileHelpfulnessCypher:
    """Tests for Cypher expression generation."""

    def test_default_expression(self) -> None:
        """Default parameters should produce valid Cypher."""
        expr = compile_helpfulness_cypher()
        assert "similarity_score" in expr
        assert "visit_count_normalized" in expr
        assert "0.5" in expr

    def test_custom_props(self) -> None:
        """Custom property names should appear in expression."""
        expr = compile_helpfulness_cypher(
            similarity_prop="sim",
            importance_prop="imp",
            alpha=0.7,
        )
        assert "candidate.sim" in expr
        assert "candidate.imp" in expr
        assert "0.7" in expr

    def test_expression_is_string(self) -> None:
        """Expression should be a string."""
        expr = compile_helpfulness_cypher()
        assert isinstance(expr, str)
