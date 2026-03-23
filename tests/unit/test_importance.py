"""
--- L9_META ---
l9_schema: 1
origin: tests
engine: graph
layer: [tests]
tags: [hoprag, importance, visit-count, unit-test]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine.scoring.importance module.
"""

from __future__ import annotations

import pytest

from engine.scoring.importance import (
    ImportanceResult,
    ImportanceScorer,
    compile_importance_cypher,
    compute_importance,
)


class TestImportanceScorer:
    """Tests for ImportanceScorer class."""

    def test_single_vertex_full_importance(self) -> None:
        """Single vertex with all visits should have importance 1.0."""
        scorer = ImportanceScorer()
        result = scorer.compute("v1", {"v1": 5})
        assert isinstance(result, ImportanceResult)
        assert result.score == pytest.approx(1.0, abs=1e-9)
        assert result.visit_count == 5
        assert result.total_visits == 5

    def test_equal_distribution(self) -> None:
        """Equal visit counts should give equal importance."""
        scorer = ImportanceScorer()
        counts = {"v1": 3, "v2": 3, "v3": 3}
        r1 = scorer.compute("v1", counts)
        r2 = scorer.compute("v2", counts)
        r3 = scorer.compute("v3", counts)
        expected = 1.0 / 3.0
        assert r1.score == pytest.approx(expected, abs=1e-9)
        assert r2.score == pytest.approx(expected, abs=1e-9)
        assert r3.score == pytest.approx(expected, abs=1e-9)

    def test_proportional_importance(self) -> None:
        """Importance should be proportional to visit count."""
        scorer = ImportanceScorer()
        counts = {"v1": 5, "v2": 3, "v3": 2}
        r1 = scorer.compute("v1", counts)
        r2 = scorer.compute("v2", counts)
        r3 = scorer.compute("v3", counts)
        assert r1.score == pytest.approx(0.5, abs=1e-9)
        assert r2.score == pytest.approx(0.3, abs=1e-9)
        assert r3.score == pytest.approx(0.2, abs=1e-9)

    def test_missing_vertex_zero_importance(self) -> None:
        """Vertex not in visit_counts should have importance 0.0."""
        scorer = ImportanceScorer()
        counts = {"v1": 5, "v2": 3}
        result = scorer.compute("v_missing", counts)
        assert result.score == pytest.approx(0.0, abs=1e-9)
        assert result.visit_count == 0

    def test_empty_counts_raises(self) -> None:
        """Empty visit_counts should raise ValueError."""
        scorer = ImportanceScorer()
        with pytest.raises(ValueError, match="visit_counts must be non-empty"):
            scorer.compute("v1", {})

    def test_all_zero_counts(self) -> None:
        """All-zero visit counts should return 0.0."""
        scorer = ImportanceScorer()
        counts = {"v1": 0, "v2": 0}
        result = scorer.compute("v1", counts)
        assert result.score == 0.0
        assert result.total_visits == 0

    def test_compute_all(self) -> None:
        """compute_all should return results for all vertices."""
        scorer = ImportanceScorer()
        counts = {"v1": 5, "v2": 3, "v3": 2}
        results = scorer.compute_all(counts)
        assert len(results) == 3
        assert results["v1"].score == pytest.approx(0.5, abs=1e-9)
        assert results["v2"].score == pytest.approx(0.3, abs=1e-9)
        assert results["v3"].score == pytest.approx(0.2, abs=1e-9)

    def test_compute_all_empty(self) -> None:
        """compute_all on empty dict should return empty dict."""
        scorer = ImportanceScorer()
        results = scorer.compute_all({})
        assert results == {}

    def test_normalize_to_dict(self) -> None:
        """normalize_to_dict should return simple float dict."""
        scorer = ImportanceScorer()
        counts = {"v1": 4, "v2": 6}
        normalized = scorer.normalize_to_dict(counts)
        assert isinstance(normalized, dict)
        assert normalized["v1"] == pytest.approx(0.4, abs=1e-9)
        assert normalized["v2"] == pytest.approx(0.6, abs=1e-9)

    def test_scores_sum_to_one(self) -> None:
        """All importance scores should sum to 1.0."""
        scorer = ImportanceScorer()
        counts = {"v1": 7, "v2": 2, "v3": 4, "v4": 1}
        results = scorer.compute_all(counts)
        total = sum(r.score for r in results.values())
        assert total == pytest.approx(1.0, abs=1e-9)


class TestComputeImportance:
    """Tests for convenience function compute_importance."""

    def test_basic(self) -> None:
        """Basic importance computation."""
        assert compute_importance(5, 10) == pytest.approx(0.5, abs=1e-9)

    def test_zero_visits(self) -> None:
        """Zero visits should return 0.0."""
        assert compute_importance(0, 10) == pytest.approx(0.0, abs=1e-9)

    def test_full_visits(self) -> None:
        """All visits should return 1.0."""
        assert compute_importance(10, 10) == pytest.approx(1.0, abs=1e-9)

    def test_negative_visit_count_raises(self) -> None:
        """Negative visit_count should raise ValueError."""
        with pytest.raises(ValueError, match="visit_count must be >= 0"):
            compute_importance(-1, 10)

    def test_zero_total_raises(self) -> None:
        """Zero total_visits should raise ValueError."""
        with pytest.raises(ValueError, match="total_visits must be > 0"):
            compute_importance(5, 0)

    def test_negative_total_raises(self) -> None:
        """Negative total_visits should raise ValueError."""
        with pytest.raises(ValueError, match="total_visits must be > 0"):
            compute_importance(5, -1)


class TestCompileImportanceCypher:
    """Tests for Cypher expression generation."""

    def test_default_expression(self) -> None:
        """Default parameters should produce valid Cypher."""
        expr = compile_importance_cypher()
        assert "visit_count" in expr
        assert "$total_visits" in expr

    def test_custom_props(self) -> None:
        """Custom property names should appear in expression."""
        expr = compile_importance_cypher(
            visit_count_prop="my_count",
            total_visits_param="my_total",
        )
        assert "candidate.my_count" in expr
        assert "$my_total" in expr

    def test_expression_is_string(self) -> None:
        """Expression should be a string."""
        assert isinstance(compile_importance_cypher(), str)
