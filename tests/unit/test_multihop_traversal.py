"""
--- L9_META ---
l9_schema: 1
origin: tests
engine: graph
layer: [tests]
tags: [hoprag, multihop, traversal, unit-test]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine.traversal.multihop module.
"""

from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pytest

from engine.traversal.multihop import (
    MultiHopTraverser,
    ReasoningMode,
    TraversalEdge,
    TraversalResult,
)


class MockNeighborFetcher:
    """Mock neighbor fetcher for testing."""

    def __init__(self, graph: dict[str, list[TraversalEdge]]) -> None:
        self._graph = graph

    async def get_outgoing_edges(self, vertex_id: str) -> list[TraversalEdge]:
        return self._graph.get(vertex_id, [])


class MockLLMClient:
    """Mock LLM client that always selects first edge."""

    def evaluate_edges(
        self,
        query: str,
        current_passage: str,
        candidate_edges: list[dict[str, Any]],
    ) -> int:
        return 0


def _make_edge(
    source: str,
    target: str,
    question: str = "",
    embedding: np.ndarray | None = None,
) -> TraversalEdge:
    """Helper to create TraversalEdge."""
    return TraversalEdge(
        source_id=source,
        target_id=target,
        question=question,
        embedding=embedding,
    )


class TestMultiHopTraverser:
    """Tests for MultiHopTraverser class."""

    def test_init_defaults(self) -> None:
        """Default initialization should succeed."""
        fetcher = MockNeighborFetcher({})
        traverser = MultiHopTraverser(neighbor_fetcher=fetcher)
        assert traverser._max_hops == 4
        assert traverser._top_k == 12

    def test_init_invalid_max_hops(self) -> None:
        """max_hops < 1 should raise ValueError."""
        fetcher = MockNeighborFetcher({})
        with pytest.raises(ValueError, match="max_hops must be >= 1"):
            MultiHopTraverser(neighbor_fetcher=fetcher, max_hops=0)

    def test_init_invalid_top_k(self) -> None:
        """top_k < 1 should raise ValueError."""
        fetcher = MockNeighborFetcher({})
        with pytest.raises(ValueError, match="top_k must be >= 1"):
            MultiHopTraverser(neighbor_fetcher=fetcher, top_k=0)

    def test_init_llm_mode_without_client(self) -> None:
        """LLM mode without client should raise ValueError."""
        fetcher = MockNeighborFetcher({})
        with pytest.raises(ValueError, match="llm_client is required"):
            MultiHopTraverser(
                neighbor_fetcher=fetcher,
                reasoning_mode=ReasoningMode.LLM,
            )

    @pytest.mark.asyncio
    async def test_none_mode_returns_empty(self) -> None:
        """NONE mode should return empty result."""
        fetcher = MockNeighborFetcher({})
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.NONE,
        )
        result = await traverser.traverse(start_vertices=["v1"])
        assert isinstance(result, TraversalResult)
        assert result.visit_counts == {}
        assert result.hops_executed == 0

    @pytest.mark.asyncio
    async def test_linear_traversal(self) -> None:
        """Linear graph A→B→C should visit all vertices."""
        emb_b = np.array([1.0, 0.0, 0.0])
        emb_c = np.array([0.0, 1.0, 0.0])
        query_emb = np.array([0.5, 0.5, 0.0])

        graph = {
            "A": [_make_edge("A", "B", embedding=emb_b)],
            "B": [_make_edge("B", "C", embedding=emb_c)],
            "C": [],
        }
        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=3,
            top_k=5,
        )

        result = await traverser.traverse(
            start_vertices=["A"],
            query_embedding=query_emb,
        )

        assert "A" in result.visit_counts
        assert "B" in result.visit_counts
        assert "C" in result.visit_counts

    @pytest.mark.asyncio
    async def test_branching_graph(self) -> None:
        """Branching graph should select best edge at each hop."""
        # A has two outgoing edges: B (high sim) and C (low sim)
        emb_b = np.array([1.0, 0.0, 0.0])
        emb_c = np.array([0.0, 0.0, 1.0])
        query_emb = np.array([1.0, 0.0, 0.0])  # Most similar to B

        graph = {
            "A": [
                _make_edge("A", "B", embedding=emb_b),
                _make_edge("A", "C", embedding=emb_c),
            ],
            "B": [],
            "C": [],
        }
        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=2,
        )

        result = await traverser.traverse(
            start_vertices=["A"],
            query_embedding=query_emb,
        )

        # B should be visited (higher similarity), C should not
        assert "B" in result.visit_counts
        assert "C" not in result.visit_counts

    @pytest.mark.asyncio
    async def test_empty_queue_terminates(self) -> None:
        """Traversal should stop when queue is empty."""
        graph = {"A": []}  # No outgoing edges
        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=10,
        )

        result = await traverser.traverse(
            start_vertices=["A"],
            query_embedding=np.array([1.0, 0.0]),
        )

        assert result.hops_executed <= 1
        assert "A" in result.visit_counts

    @pytest.mark.asyncio
    async def test_max_hops_terminates(self) -> None:
        """Traversal should stop at max_hops even with remaining queue."""
        # Build a long chain: A→B→C→D→E→F
        emb = np.array([1.0, 0.0])
        chain = {}
        nodes = ["A", "B", "C", "D", "E", "F"]
        for i in range(len(nodes) - 1):
            chain[nodes[i]] = [_make_edge(nodes[i], nodes[i + 1], embedding=emb)]
        chain["F"] = []

        fetcher = MockNeighborFetcher(chain)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=2,
        )

        result = await traverser.traverse(
            start_vertices=["A"],
            query_embedding=np.array([1.0, 0.0]),
        )

        assert result.hops_executed <= 2
        # Should not reach F (5 hops away)
        assert "F" not in result.visit_counts

    @pytest.mark.asyncio
    async def test_visit_counts_accumulate(self) -> None:
        """Vertices visited from multiple paths should accumulate counts."""
        emb = np.array([1.0, 0.0])
        # A→C and B→C (both paths converge on C)
        graph = {
            "A": [_make_edge("A", "C", embedding=emb)],
            "B": [_make_edge("B", "C", embedding=emb)],
            "C": [],
        }
        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=2,
        )

        result = await traverser.traverse(
            start_vertices=["A", "B"],
            query_embedding=np.array([1.0, 0.0]),
        )

        # C should be visited twice (once from A, once from B)
        assert result.visit_counts.get("C", 0) == 2

    @pytest.mark.asyncio
    async def test_queue_sizes_recorded(self) -> None:
        """Queue sizes should be recorded at each hop."""
        emb = np.array([1.0, 0.0])
        graph = {
            "A": [_make_edge("A", "B", embedding=emb)],
            "B": [_make_edge("B", "C", embedding=emb)],
            "C": [],
        }
        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=3,
        )

        result = await traverser.traverse(
            start_vertices=["A"],
            query_embedding=np.array([1.0, 0.0]),
        )

        # Initial queue + one per hop executed
        assert len(result.queue_sizes) >= 1

    @pytest.mark.asyncio
    async def test_llm_mode(self) -> None:
        """LLM mode should use LLM client for edge selection."""
        emb = np.array([1.0, 0.0])
        graph = {
            "A": [
                _make_edge("A", "B", question="Q1", embedding=emb),
                _make_edge("A", "C", question="Q2", embedding=emb),
            ],
            "B": [],
            "C": [],
        }
        fetcher = MockNeighborFetcher(graph)
        llm = MockLLMClient()
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.LLM,
            max_hops=1,
            llm_client=llm,
        )

        result = await traverser.traverse(
            start_vertices=["A"],
            query_text="test query",
        )

        assert result.llm_calls >= 1
        # MockLLMClient always returns 0, so B should be selected
        assert "B" in result.visit_counts

    @pytest.mark.asyncio
    async def test_top_k_limits_seeds(self) -> None:
        """top_k should limit the number of seed vertices."""
        graph = {
            "A": [],
            "B": [],
            "C": [],
        }
        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=1,
            top_k=2,
        )

        result = await traverser.traverse(
            start_vertices=["A", "B", "C"],
            query_embedding=np.array([1.0]),
        )

        # Only top_k=2 seeds should be in initial visit counts
        assert len(result.visit_counts) <= 2


class TestCosinesimilarity:
    """Tests for static cosine similarity method."""

    def test_identical_vectors(self) -> None:
        """Identical vectors should have similarity 1.0."""
        a = np.array([1.0, 2.0, 3.0])
        sim = MultiHopTraverser._cosine_similarity(a, a)
        assert sim == pytest.approx(1.0, abs=1e-6)

    def test_orthogonal_vectors(self) -> None:
        """Orthogonal vectors should have similarity 0.0."""
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        sim = MultiHopTraverser._cosine_similarity(a, b)
        assert sim == pytest.approx(0.0, abs=1e-6)

    def test_opposite_vectors(self) -> None:
        """Opposite vectors should have similarity -1.0."""
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        sim = MultiHopTraverser._cosine_similarity(a, b)
        assert sim == pytest.approx(-1.0, abs=1e-6)

    def test_zero_vector(self) -> None:
        """Zero vector should return 0.0."""
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 0.0])
        sim = MultiHopTraverser._cosine_similarity(a, b)
        assert sim == 0.0
