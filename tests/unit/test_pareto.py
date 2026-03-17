# tests/unit/test_pareto.py
"""Unit tests for Pareto scoring module."""

from __future__ import annotations

import pytest

from engine.scoring.pareto import (
    ParetoCandidate,
    WeightVector,
    compute_pareto_front,
    discover_pareto_weights,
)


@pytest.mark.unit
class TestParetoCandidate:
    """Test ParetoCandidate data structure."""

    def test_create_candidate(self) -> None:
        cand = ParetoCandidate(
            candidate_id="c1",
            dimension_scores={"geo": 0.8, "price": 0.6},
        )
        assert cand.candidate_id == "c1"
        assert cand.dimension_scores["geo"] == 0.8
        assert cand.weighted_score == 0.0
        assert cand.is_dominated is False


@pytest.mark.unit
class TestComputeParetoFront:
    """Test Pareto front computation."""

    def test_empty_candidates(self) -> None:
        front = compute_pareto_front([])
        assert front.front_size == 0
        assert front.non_dominated == []
        assert front.dominated == []

    def test_single_candidate(self) -> None:
        cand = ParetoCandidate(
            candidate_id="c1",
            dimension_scores={"geo": 0.8, "price": 0.6},
        )
        front = compute_pareto_front([cand])
        assert front.front_size == 1
        assert front.non_dominated == [cand]
        assert front.dominated == []

    def test_two_non_dominated(self) -> None:
        """Two candidates that don't dominate each other."""
        c1 = ParetoCandidate(
            candidate_id="c1",
            dimension_scores={"geo": 0.9, "price": 0.3},
        )
        c2 = ParetoCandidate(
            candidate_id="c2",
            dimension_scores={"geo": 0.3, "price": 0.9},
        )
        front = compute_pareto_front([c1, c2])
        assert front.front_size == 2
        assert len(front.dominated) == 0

    def test_one_dominates_other(self) -> None:
        """c1 dominates c2 (better in all dimensions)."""
        c1 = ParetoCandidate(
            candidate_id="c1",
            dimension_scores={"geo": 0.9, "price": 0.8},
        )
        c2 = ParetoCandidate(
            candidate_id="c2",
            dimension_scores={"geo": 0.5, "price": 0.4},
        )
        front = compute_pareto_front([c1, c2])
        assert front.front_size == 1
        assert front.non_dominated[0].candidate_id == "c1"
        assert front.dominated[0].candidate_id == "c2"

    def test_three_candidates_mixed(self) -> None:
        """c1 and c2 on front, c3 dominated."""
        c1 = ParetoCandidate(
            candidate_id="c1",
            dimension_scores={"geo": 0.9, "price": 0.3, "time": 0.5},
        )
        c2 = ParetoCandidate(
            candidate_id="c2",
            dimension_scores={"geo": 0.3, "price": 0.9, "time": 0.5},
        )
        c3 = ParetoCandidate(
            candidate_id="c3",
            dimension_scores={"geo": 0.2, "price": 0.2, "time": 0.2},
        )
        front = compute_pareto_front([c1, c2, c3])
        assert front.front_size == 2
        non_dom_ids = {c.candidate_id for c in front.non_dominated}
        assert non_dom_ids == {"c1", "c2"}
        assert front.dominated[0].candidate_id == "c3"

    def test_dimension_names_extracted(self) -> None:
        c1 = ParetoCandidate(
            candidate_id="c1",
            dimension_scores={"alpha": 0.5, "beta": 0.5, "gamma": 0.5},
        )
        front = compute_pareto_front([c1])
        assert front.dimension_names == ["alpha", "beta", "gamma"]


@pytest.mark.unit
class TestDiscoverParetoWeights:
    """Test Dirichlet-sampled weight discovery."""

    def test_empty_dimensions(self) -> None:
        result = discover_pareto_weights(
            dimension_names=[],
            current_weights={},
        )
        assert result == []

    def test_single_dimension(self) -> None:
        result = discover_pareto_weights(
            dimension_names=["geo"],
            current_weights={"geo": 1.0},
            n_samples=5,
        )
        assert len(result) >= 1
        for wv in result:
            assert "geo" in wv.weights
            assert abs(wv.weights["geo"] - 1.0) < 1e-6

    def test_multiple_dimensions(self) -> None:
        result = discover_pareto_weights(
            dimension_names=["geo", "price", "time"],
            current_weights={"geo": 0.4, "price": 0.4, "time": 0.2},
            n_samples=20,
        )
        assert len(result) >= 1
        for wv in result:
            total = sum(wv.weights.values())
            assert abs(total - 1.0) < 1e-6

    def test_baseline_included(self) -> None:
        """Baseline weight vector should be included in samples."""
        result = discover_pareto_weights(
            dimension_names=["a", "b"],
            current_weights={"a": 0.7, "b": 0.3},
            n_samples=10,
            seed=42,
        )
        assert len(result) >= 1

    def test_deterministic_with_seed(self) -> None:
        """Same seed should produce same results."""
        r1 = discover_pareto_weights(
            dimension_names=["x", "y"],
            current_weights={"x": 0.5, "y": 0.5},
            n_samples=10,
            seed=123,
        )
        r2 = discover_pareto_weights(
            dimension_names=["x", "y"],
            current_weights={"x": 0.5, "y": 0.5},
            n_samples=10,
            seed=123,
        )
        assert len(r1) == len(r2)
        for wv1, wv2 in zip(r1, r2, strict=False):
            assert wv1.weights == wv2.weights


@pytest.mark.unit
class TestWeightVector:
    """Test WeightVector data structure."""

    def test_create_weight_vector(self) -> None:
        wv = WeightVector(
            weights={"a": 0.5, "b": 0.5},
            ndcg_score=0.8,
            diversity_score=0.9,
            coverage_score=1.0,
        )
        assert wv.weights["a"] == 0.5
        assert wv.ndcg_score == 0.8
        assert wv.diversity_score == 0.9
        assert wv.coverage_score == 1.0
