"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [traversal]
tags: [hoprag, multihop, bfs, traversal]
owner: engine-team
status: active
--- /L9_META ---

Multi-hop BFS traversal engine for HopRAG-style graph reasoning.

Implements the REASON stage from HopRAG (ACL 2025, §3.3.2):
BFS traversal with optional LLM-guided neighbor selection and visit counting.

Three reasoning modes:
    - "llm":        LLM evaluates edge helpfulness at each hop (Phase C).
    - "similarity": Cosine similarity selects next edge (Phase B, default).
    - "none":       No multi-hop traversal (passthrough).

Consumes:
- Graph neighbor data from Neo4j (via GraphDriver)
- Query embedding for similarity-based edge selection
- HopRAGConfig for traversal parameters (n_hop, top_k, reasoning_mode)

Produces:
- Visit counts per vertex (consumed by ImportanceScorer)
- Traversal audit trail (for observability)

Integrates with:
- engine.handlers.handle_match (invoked before scoring Cypher query)
- engine.scoring.importance.ImportanceScorer (consumes visit counts)
- engine.scoring.helpfulness.HelpfulnessScorer (consumes normalized importance)
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

import numpy as np

logger = logging.getLogger(__name__)


class ReasoningMode(StrEnum):
    """Traversal reasoning mode."""

    LLM = "llm"
    SIMILARITY = "similarity"
    NONE = "none"


class LLMClient(Protocol):
    """Protocol for LLM clients used in reasoning mode."""

    def evaluate_edges(
        self,
        query: str,
        current_passage: str,
        candidate_edges: list[dict[str, Any]],
    ) -> int:
        """Select the most helpful edge index.

        Args:
            query: The user's query text.
            current_passage: Text content of the current vertex.
            candidate_edges: List of edge dicts with 'question' and 'target_id'.

        Returns:
            Index of the selected edge in candidate_edges.
        """
        ...


@dataclass(frozen=True)
class TraversalEdge:
    """An edge in the graph with its metadata.

    Attributes:
        source_id: Source vertex ID.
        target_id: Target vertex ID.
        question: Pseudo-query text on this edge.
        keywords: NER keyword set for sparse matching.
        embedding: Dense embedding vector for similarity matching.
    """

    source_id: str
    target_id: str
    question: str = ""
    keywords: frozenset[str] = frozenset()
    embedding: np.ndarray | None = None


@dataclass
class TraversalResult:
    """Result of a multi-hop BFS traversal.

    Attributes:
        visit_counts: Dict mapping vertex IDs to visit counts.
        visited_order: Ordered list of visited vertex IDs.
        hops_executed: Number of BFS hops completed.
        queue_sizes: Queue size at each hop (for decay analysis).
        execution_time_ms: Total traversal time in milliseconds.
        llm_calls: Number of LLM calls made (0 in similarity mode).
        audit_trail: Detailed traversal log entries.
    """

    visit_counts: dict[str, int] = field(default_factory=dict)
    visited_order: list[str] = field(default_factory=list)
    hops_executed: int = 0
    queue_sizes: list[int] = field(default_factory=list)
    execution_time_ms: float = 0.0  # nosemgrep: float-requires-try-except
    llm_calls: int = 0
    audit_trail: list[dict[str, Any]] = field(default_factory=list)


class NeighborFetcher(Protocol):
    """Protocol for fetching neighbors from the graph store."""

    async def get_outgoing_edges(self, vertex_id: str) -> list[TraversalEdge]:
        """Fetch outgoing edges for a vertex.

        Args:
            vertex_id: The vertex to fetch neighbors for.

        Returns:
            List of TraversalEdge objects.
        """
        ...


class MultiHopTraverser:
    """Multi-hop BFS traversal engine.

    Performs breadth-first graph traversal with visit counting,
    starting from a set of seed vertices and expanding through
    outgoing edges for up to max_hops levels.

    At each vertex, the next edge is selected by either:
    - Cosine similarity to the query embedding (similarity mode)
    - LLM evaluation of edge helpfulness (llm mode)

    Usage::

        traverser = MultiHopTraverser(
            neighbor_fetcher=my_neo4j_fetcher,
            reasoning_mode=ReasoningMode.SIMILARITY,
            max_hops=4,
            top_k=12,
        )
        result = await traverser.traverse(
            start_vertices=["v1", "v2", "v3"],
            query_embedding=query_emb,
        )
        visit_counts = result.visit_counts  # {"v1": 3, "v4": 2, ...}
    """

    def __init__(
        self,
        neighbor_fetcher: NeighborFetcher,
        reasoning_mode: ReasoningMode = ReasoningMode.SIMILARITY,
        max_hops: int = 4,
        top_k: int = 12,
        min_queue_size: int = 0,
        max_llm_calls: int = 50,
        llm_client: LLMClient | None = None,
    ) -> None:
        """Initialize MultiHopTraverser.

        Args:
            neighbor_fetcher: Implementation for fetching graph neighbors.
            reasoning_mode: Edge selection strategy.
            max_hops: Maximum BFS depth. Default 4 per HopRAG paper.
            top_k: Number of start vertices to use. Default 12.
            min_queue_size: Stop when queue drops below this size. Default 0.
            max_llm_calls: Hard cap on LLM calls per query. Default 50.
            llm_client: LLM client for 'llm' reasoning mode. Required if mode='llm'.

        Raises:
            ValueError: If max_hops < 1, top_k < 1, or llm mode without client.
        """
        if max_hops < 1:
            msg = f"max_hops must be >= 1, got {max_hops}"
            raise ValueError(msg)
        if top_k < 1:
            msg = f"top_k must be >= 1, got {top_k}"
            raise ValueError(msg)
        if reasoning_mode == ReasoningMode.LLM and llm_client is None:
            msg = "llm_client is required when reasoning_mode is 'llm'"
            raise ValueError(msg)

        self._fetcher = neighbor_fetcher
        self._mode = reasoning_mode
        self._max_hops = max_hops
        self._top_k = top_k
        self._min_queue_size = min_queue_size
        self._max_llm_calls = max_llm_calls
        self._llm_client = llm_client

    async def traverse(  # noqa: PLR0915
        self,
        start_vertices: list[str],
        query_embedding: np.ndarray | None = None,
        query_text: str = "",
    ) -> TraversalResult:
        """Execute multi-hop BFS traversal.

        Args:
            start_vertices: Seed vertex IDs to begin traversal from.
            query_embedding: Query embedding for similarity-based selection.
                            Required if reasoning_mode is 'similarity'.
            query_text: Query text for LLM-based selection.
                       Required if reasoning_mode is 'llm'.

        Returns:
            TraversalResult with visit counts and traversal metadata.
        """
        if self._mode == ReasoningMode.NONE:
            return TraversalResult()

        if self._mode == ReasoningMode.SIMILARITY and query_embedding is None:
            msg = "query_embedding is required for similarity reasoning mode"
            raise ValueError(msg)

        start_time = time.monotonic()

        # Initialize BFS
        visit_counts: dict[str, int] = defaultdict(int)
        visited_order: list[str] = []
        queue: deque[str] = deque()
        queue_sizes: list[int] = []
        llm_calls = 0
        audit_trail: list[dict[str, Any]] = []

        # Seed the queue with start vertices (limited to top_k)
        seeds = start_vertices[: self._top_k]
        for vid in seeds:
            queue.append(vid)
            visit_counts[vid] += 1
            visited_order.append(vid)

        queue_sizes.append(len(queue))
        hops_executed = 0

        for hop in range(1, self._max_hops + 1):
            if not queue:
                logger.debug("BFS queue empty at hop %d, stopping", hop)
                break

            if len(queue) < self._min_queue_size:
                logger.debug(
                    "Queue size %d below min_queue_size %d at hop %d, stopping",
                    len(queue),
                    self._min_queue_size,
                    hop,
                )
                break

            next_queue: deque[str] = deque()
            hop_audit: dict[str, Any] = {
                "hop": hop,
                "queue_size": len(queue),
                "expansions": [],
            }

            # Process each vertex in current queue
            current_level = list(queue)
            for vertex_id in current_level:
                # Fetch outgoing edges
                edges = await self._fetcher.get_outgoing_edges(vertex_id)
                if not edges:
                    continue

                # Select best edge
                selected_edge: TraversalEdge | None = None

                if self._mode == ReasoningMode.SIMILARITY:
                    selected_edge = self._select_by_similarity(
                        query_embedding,
                        edges,  # type: ignore[arg-type]
                    )
                elif self._mode == ReasoningMode.LLM:
                    if llm_calls >= self._max_llm_calls:
                        # Fall back to similarity when LLM budget exhausted
                        if query_embedding is not None:
                            selected_edge = self._select_by_similarity(query_embedding, edges)
                        else:
                            selected_edge = edges[0] if edges else None
                    else:
                        selected_edge = self._select_by_llm(query_text, vertex_id, edges)
                        llm_calls += 1

                if selected_edge is not None:
                    target = selected_edge.target_id
                    visit_counts[target] += 1
                    if target not in visited_order:
                        visited_order.append(target)
                    next_queue.append(target)

                    hop_audit["expansions"].append(
                        {
                            "from": vertex_id,
                            "to": target,
                            "edge_question": selected_edge.question[:100],
                        }
                    )

            queue = next_queue
            queue_sizes.append(len(queue))
            hops_executed = hop
            audit_trail.append(hop_audit)

        execution_time_ms = (time.monotonic() - start_time) * 1000

        logger.info(
            "MultiHopTraverser: %d hops, %d vertices visited, %d LLM calls, %.1fms",
            hops_executed,
            len(visit_counts),
            llm_calls,
            execution_time_ms,
        )

        return TraversalResult(
            visit_counts=dict(visit_counts),
            visited_order=visited_order,
            hops_executed=hops_executed,
            queue_sizes=queue_sizes,
            execution_time_ms=execution_time_ms,
            llm_calls=llm_calls,
            audit_trail=audit_trail,
        )

    def _select_by_similarity(
        self,
        query_embedding: np.ndarray,
        edges: list[TraversalEdge],
    ) -> TraversalEdge | None:
        """Select the edge whose embedding is most similar to the query.

        Args:
            query_embedding: Query embedding vector.
            edges: Candidate edges to select from.

        Returns:
            The edge with highest cosine similarity, or None if no edges.
        """
        if not edges:
            return None

        best_edge: TraversalEdge | None = None
        best_sim = -1.0

        for edge in edges:
            if edge.embedding is None:
                continue
            sim = self._cosine_similarity(query_embedding, edge.embedding)
            if sim > best_sim:
                best_sim = sim
                best_edge = edge

        # Fall back to first edge if none have embeddings
        return best_edge if best_edge is not None else edges[0]

    def _select_by_llm(
        self,
        query_text: str,
        current_vertex_id: str,
        edges: list[TraversalEdge],
    ) -> TraversalEdge | None:
        """Select the edge using LLM reasoning.

        Args:
            query_text: The user's query text.
            current_vertex_id: ID of the current vertex (for passage lookup).
            edges: Candidate edges to evaluate.

        Returns:
            The LLM-selected edge, or None if no edges.
        """
        if not edges or self._llm_client is None:
            return None

        edge_dicts = [{"question": e.question, "target_id": e.target_id} for e in edges]

        try:
            selected_idx = self._llm_client.evaluate_edges(
                query=query_text,
                current_passage=current_vertex_id,
                candidate_edges=edge_dicts,
            )
            if 0 <= selected_idx < len(edges):
                return edges[selected_idx]
        except Exception:
            logger.warning(
                "LLM edge evaluation failed, falling back to first edge",
                exc_info=True,
            )

        return edges[0]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            a: First vector.
            b: Second vector.

        Returns:
            Cosine similarity in [-1.0, 1.0].
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))  # nosemgrep: float-requires-try-except
