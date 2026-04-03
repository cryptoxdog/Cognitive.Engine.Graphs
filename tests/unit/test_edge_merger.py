"""
--- L9_META ---
l9_schema: 1
origin: tests
engine: graph
layer: [tests]
tags: [hoprag, edge-merger, unit-test]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine.traversal.edge_merger module.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.traversal.edge_merger import (
    EdgeMerger,
    EdgeTriplet,
    MergeResult,
)


def _make_triplet(
    vertex_id: str,
    question: str = "",
    keywords: frozenset[str] | None = None,
    embedding: list[float] | None = None,
) -> EdgeTriplet:
    """Helper to create EdgeTriplet."""
    return EdgeTriplet(
        vertex_id=vertex_id,
        question=question,
        keywords=keywords or frozenset(),
        embedding=np.array(embedding) if embedding else None,
    )


class TestJaccardSimilarity:
    """Tests for Jaccard similarity computation."""

    def test_identical_sets(self) -> None:
        """Identical sets should have similarity 1.0."""
        sim = EdgeMerger._jaccard_similarity(
            frozenset({"a", "b", "c"}),
            frozenset({"a", "b", "c"}),
        )
        assert sim == pytest.approx(1.0, abs=1e-9)

    def test_disjoint_sets(self) -> None:
        """Disjoint sets should have similarity 0.0."""
        sim = EdgeMerger._jaccard_similarity(
            frozenset({"a", "b"}),
            frozenset({"c", "d"}),
        )
        assert sim == pytest.approx(0.0, abs=1e-9)

    def test_partial_overlap(self) -> None:
        """Partial overlap should give correct Jaccard index."""
        sim = EdgeMerger._jaccard_similarity(
            frozenset({"a", "b", "c"}),
            frozenset({"b", "c", "d"}),
        )
        # Intersection: {b, c} = 2, Union: {a, b, c, d} = 4
        assert sim == pytest.approx(0.5, abs=1e-9)

    def test_empty_sets(self) -> None:
        """Both empty sets should return 0.0."""
        sim = EdgeMerger._jaccard_similarity(frozenset(), frozenset())
        assert sim == 0.0

    def test_one_empty_set(self) -> None:
        """One empty set should return 0.0."""
        sim = EdgeMerger._jaccard_similarity(
            frozenset({"a", "b"}),
            frozenset(),
        )
        assert sim == 0.0


class TestCosineSimilarity:
    """Tests for cosine similarity computation."""

    def test_identical_vectors(self) -> None:
        """Identical vectors should have similarity 1.0."""
        v = np.array([1.0, 2.0, 3.0])
        sim = EdgeMerger._cosine_similarity(v, v)
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors should have similarity 0.0."""
        sim = EdgeMerger._cosine_similarity(
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        )
        assert sim == pytest.approx(0.0, abs=1e-6)

    def test_none_vectors(self) -> None:
        """None vectors should return 0.0."""
        assert EdgeMerger._cosine_similarity(None, np.array([1.0])) == 0.0
        assert EdgeMerger._cosine_similarity(np.array([1.0]), None) == 0.0
        assert EdgeMerger._cosine_similarity(None, None) == 0.0

    def test_zero_vector(self) -> None:
        """Zero vector should return 0.0."""
        sim = EdgeMerger._cosine_similarity(
            np.array([0.0, 0.0]),
            np.array([1.0, 0.0]),
        )
        assert sim == 0.0


class TestHybridSimilarity:
    """Tests for hybrid similarity computation."""

    def test_perfect_match(self) -> None:
        """Perfect keyword and embedding match should give 1.0."""
        merger = EdgeMerger()
        hybrid, jaccard, cosine = merger.hybrid_similarity(
            frozenset({"a", "b"}),
            frozenset({"a", "b"}),
            np.array([1.0, 0.0]),
            np.array([1.0, 0.0]),
        )
        assert hybrid == pytest.approx(1.0, abs=1e-6)
        assert jaccard == pytest.approx(1.0, abs=1e-6)
        assert cosine == pytest.approx(1.0, abs=1e-6)

    def test_zero_match(self) -> None:
        """No overlap and orthogonal embeddings should give 0.0."""
        merger = EdgeMerger()
        hybrid, jaccard, cosine = merger.hybrid_similarity(
            frozenset({"a"}),
            frozenset({"b"}),
            np.array([1.0, 0.0]),
            np.array([0.0, 1.0]),
        )
        assert jaccard == pytest.approx(0.0, abs=1e-6)
        assert cosine == pytest.approx(0.0, abs=1e-6)
        assert hybrid == pytest.approx(0.0, abs=1e-6)

    def test_hybrid_is_average(self) -> None:
        """Hybrid should be arithmetic mean of Jaccard and cosine."""
        merger = EdgeMerger()
        hybrid, jaccard, cosine = merger.hybrid_similarity(
            frozenset({"a", "b", "c"}),
            frozenset({"b", "c", "d"}),
            np.array([1.0, 0.0]),
            np.array([1.0, 0.0]),
        )
        expected = (jaccard + cosine) / 2.0
        assert hybrid == pytest.approx(expected, abs=1e-6)


class TestDensityLimit:
    """Tests for edge density control."""

    def test_small_graph(self) -> None:
        """Small graph should have reasonable density limit."""
        merger = EdgeMerger()
        limit = merger.compute_density_limit(10)
        # 10 * log(10) ≈ 23
        assert limit == int(10 * math.log(10))

    def test_single_vertex(self) -> None:
        """Single vertex should have limit 1."""
        merger = EdgeMerger()
        assert merger.compute_density_limit(1) == 1

    def test_density_factor(self) -> None:
        """Density factor should scale the limit."""
        merger_low = EdgeMerger(density_factor=0.5)
        merger_high = EdgeMerger(density_factor=2.0)
        low_limit = merger_low.compute_density_limit(100)
        high_limit = merger_high.compute_density_limit(100)
        assert high_limit > low_limit
        assert high_limit == pytest.approx(low_limit * 4, abs=2)  # 2.0/0.5 = 4x


class TestEdgeMerger:
    """Tests for the full merge_edges operation."""

    def test_basic_merge(self) -> None:
        """Basic merge should create edges between different vertices."""
        merger = EdgeMerger()
        outgoing = [
            _make_triplet("A", "Q_out_A", frozenset({"x", "y"}), [1.0, 0.0]),
        ]
        incoming = [
            _make_triplet("B", "Q_in_B", frozenset({"y", "z"}), [0.8, 0.2]),
        ]
        result = merger.merge_edges(outgoing, incoming)
        assert isinstance(result, MergeResult)
        assert len(result.edges) == 1
        edge = result.edges[0]
        assert edge.source_id == "A"
        assert edge.target_id == "B"
        assert 0.0 <= edge.similarity <= 1.0

    def test_no_self_edges(self) -> None:
        """Edges from a vertex to itself should be excluded."""
        merger = EdgeMerger()
        outgoing = [_make_triplet("A", "Q1", frozenset({"x"}), [1.0, 0.0])]
        incoming = [_make_triplet("A", "Q2", frozenset({"x"}), [1.0, 0.0])]
        result = merger.merge_edges(outgoing, incoming)
        assert len(result.edges) == 0

    def test_density_limit_enforced(self) -> None:
        """Number of edges should not exceed density limit."""
        merger = EdgeMerger(density_factor=0.1)
        # Create many triplets
        outgoing = [_make_triplet(f"s{i}", f"Q_out_{i}", frozenset({f"k{i}"}), [float(i) / 10, 0.5]) for i in range(20)]
        incoming = [_make_triplet(f"t{i}", f"Q_in_{i}", frozenset({f"k{i}"}), [0.5, float(i) / 10]) for i in range(20)]
        result = merger.merge_edges(outgoing, incoming, vertex_count=40)
        density_limit = merger.compute_density_limit(40)
        assert len(result.edges) <= density_limit

    def test_min_similarity_threshold(self) -> None:
        """Edges below min_similarity should be filtered."""
        merger = EdgeMerger(min_similarity=0.9)
        outgoing = [_make_triplet("A", "Q1", frozenset({"x"}), [1.0, 0.0])]
        incoming = [_make_triplet("B", "Q2", frozenset({"y"}), [0.0, 1.0])]
        result = merger.merge_edges(outgoing, incoming)
        # Jaccard: 0/2 = 0, Cosine: 0, Hybrid: 0 < 0.9
        assert len(result.edges) == 0

    def test_per_vertex_cap(self) -> None:
        """Per-vertex cap should limit outgoing edges per source."""
        merger = EdgeMerger(max_edges_per_vertex=1)
        outgoing = [_make_triplet("A", "Q1", frozenset({"x"}), [1.0, 0.0])]
        incoming = [
            _make_triplet("B", "Q2", frozenset({"x"}), [1.0, 0.0]),
            _make_triplet("C", "Q3", frozenset({"x"}), [0.9, 0.1]),
        ]
        result = merger.merge_edges(outgoing, incoming)
        # A should have at most 1 outgoing edge
        a_edges = [e for e in result.edges if e.source_id == "A"]
        assert len(a_edges) <= 1

    def test_empty_inputs(self) -> None:
        """Empty inputs should return empty result."""
        merger = EdgeMerger()
        result = merger.merge_edges([], [])
        assert len(result.edges) == 0

    def test_edges_sorted_by_similarity(self) -> None:
        """Edges should be sorted by similarity descending."""
        merger = EdgeMerger()
        outgoing = [
            _make_triplet("A", "Q1", frozenset({"x", "y"}), [1.0, 0.0]),
        ]
        incoming = [
            _make_triplet("B", "Q2", frozenset({"x", "y"}), [1.0, 0.0]),  # High sim
            _make_triplet("C", "Q3", frozenset({"z"}), [0.0, 1.0]),  # Low sim
        ]
        result = merger.merge_edges(outgoing, incoming)
        if len(result.edges) >= 2:
            assert result.edges[0].similarity >= result.edges[1].similarity

    def test_merge_result_metadata(self) -> None:
        """MergeResult should contain correct metadata."""
        merger = EdgeMerger()
        outgoing = [_make_triplet("A", "Q1", frozenset({"x"}), [1.0, 0.0])]
        incoming = [_make_triplet("B", "Q2", frozenset({"x"}), [0.8, 0.2])]
        result = merger.merge_edges(outgoing, incoming, vertex_count=10)
        assert result.vertex_count == 10
        assert result.density_limit > 0
        assert result.total_candidates >= 0
