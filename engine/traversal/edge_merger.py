"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [traversal]
tags: [hoprag, edge-merger, hybrid-similarity, indexing]
owner: engine-team
status: active
--- /L9_META ---

Edge merging with hybrid similarity for HopRAG graph construction.

Implements Edge Merging from HopRAG (ACL 2025, §3.2):

    SIM(r+_s,i, r-_t,j) = (Jaccard(k+, k-) + cosine(v+, v-)) / 2

Where:
    - Jaccard operates on NER keyword sets (sparse signal)
    - Cosine operates on embedding vectors (dense signal)
    - Arithmetic mean provides balanced sparse-dense fusion

Edge density is controlled to O(n·log(n)) to prevent graph explosion.

Consumes:
- QuestionTriplet objects from PseudoQueryGenerator
- Edge density parameters from HopRAGConfig

Produces:
- Directed edges with hybrid similarity scores
- Consumed by engine.hoprag.indexer.GraphIndexBuilder

Integrates with:
- engine.traversal.pseudo_query.PseudoQueryGenerator (provides triplets)
- engine.hoprag.config.HopRAGConfig (provides density parameters)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EdgeTriplet:
    """A question triplet on a vertex edge endpoint.

    Attributes:
        vertex_id: The vertex this triplet belongs to.
        question: Question text.
        keywords: NER keyword set for Jaccard matching.
        embedding: Dense embedding vector for cosine matching.
    """

    vertex_id: str
    question: str = ""
    keywords: frozenset[str] = frozenset()
    embedding: npt.NDArray[Any] | None = None


@dataclass(frozen=True)
class MergedEdge:
    """A directed edge created by merging outgoing and incoming triplets.

    Attributes:
        source_id: Source vertex ID.
        target_id: Target vertex ID.
        similarity: Hybrid similarity score in [0.0, 1.0].
        source_question: The out-coming question from source.
        target_question: The in-coming question from target.
        jaccard_score: Sparse (keyword) similarity component.
        cosine_score: Dense (embedding) similarity component.
    """

    source_id: str
    target_id: str
    similarity: float
    source_question: str = ""
    target_question: str = ""
    jaccard_score: float = 0.0  # nosemgrep: float-requires-try-except
    cosine_score: float = 0.0  # nosemgrep: float-requires-try-except


@dataclass
class MergeResult:
    """Result of edge merging operation.

    Attributes:
        edges: List of merged edges, sorted by similarity descending.
        total_candidates: Number of candidate edge pairs evaluated.
        density_limit: Maximum edges allowed by density control.
        vertex_count: Number of unique vertices involved.
    """

    edges: list[MergedEdge] = field(default_factory=list)
    total_candidates: int = 0
    density_limit: int = 0
    vertex_count: int = 0


class EdgeMerger:
    """Merges pseudo-query triplets into directed graph edges.

    For each pair of (source_outgoing_triplet, target_incoming_triplet),
    computes hybrid similarity and retains edges above threshold,
    subject to O(n·log(n)) density control.

    Usage::

        merger = EdgeMerger(density_factor=1.0, min_similarity=0.3)
        result = merger.merge_edges(
            outgoing_triplets=source_triplets,
            incoming_triplets=target_triplets,
            vertex_count=1000,
        )
        edge_count = len(result.edges)  # <= n * log(n)
    """

    def __init__(
        self,
        density_factor: float = 1.0,
        min_similarity: float = 0.0,
        max_edges_per_vertex: int | None = None,
    ) -> None:
        """Initialize EdgeMerger.

        Args:
            density_factor: Multiplier on n*log(n) density limit.
                           1.0 = paper default. Lower = sparser graph.
            min_similarity: Minimum hybrid similarity to create an edge.
                           Default 0.0 (no threshold, rely on density limit).
            max_edges_per_vertex: Hard cap on outgoing edges per vertex.
                                None = no per-vertex cap.
        """
        self._density_factor = density_factor
        self._min_similarity = min_similarity
        self._max_per_vertex = max_edges_per_vertex

    def hybrid_similarity(
        self,
        keywords1: frozenset[str],
        keywords2: frozenset[str],
        embedding1: npt.NDArray[Any] | None,
        embedding2: npt.NDArray[Any] | None,
    ) -> tuple[float, float, float]:
        """Compute hybrid similarity between two triplets.

        Args:
            keywords1: Keyword set from first triplet.
            keywords2: Keyword set from second triplet.
            embedding1: Embedding vector from first triplet.
            embedding2: Embedding vector from second triplet.

        Returns:
            Tuple of (hybrid_sim, jaccard_sim, cosine_sim).
            Each value in [0.0, 1.0].
        """
        jaccard = self._jaccard_similarity(keywords1, keywords2)
        cosine = self._cosine_similarity(embedding1, embedding2)
        hybrid = (jaccard + cosine) / 2.0
        return hybrid, jaccard, cosine

    def compute_density_limit(self, vertex_count: int) -> int:
        """Compute maximum edge count from O(n·log(n)) formula.

        Args:
            vertex_count: Number of vertices in the graph.

        Returns:
            Maximum number of edges allowed.
        """
        if vertex_count <= 1:
            return vertex_count
        base = vertex_count * math.log(vertex_count)
        return max(1, int(base * self._density_factor))

    def merge_edges(
        self,
        outgoing_triplets: list[EdgeTriplet],
        incoming_triplets: list[EdgeTriplet],
        vertex_count: int | None = None,
    ) -> MergeResult:
        """Merge outgoing and incoming triplets into directed edges.

        For each (source_out, target_in) pair where source != target,
        compute hybrid similarity and retain top edges by density limit.

        Args:
            outgoing_triplets: Out-coming triplets from source vertices.
            incoming_triplets: In-coming triplets from target vertices.
            vertex_count: Total vertex count for density limit. If None,
                         inferred from unique vertex IDs in triplets.

        Returns:
            MergeResult with edges sorted by similarity descending.
        """
        if not outgoing_triplets or not incoming_triplets:
            return MergeResult()

        # Infer vertex count if not provided
        if vertex_count is None:
            vertex_ids = {t.vertex_id for t in outgoing_triplets} | {t.vertex_id for t in incoming_triplets}
            vertex_count = len(vertex_ids)

        density_limit = self.compute_density_limit(vertex_count)

        # Compute all candidate edges
        candidates: list[MergedEdge] = []
        for out_triplet in outgoing_triplets:
            for in_triplet in incoming_triplets:
                # No self-edges
                if out_triplet.vertex_id == in_triplet.vertex_id:
                    continue

                hybrid, jaccard, cosine = self.hybrid_similarity(
                    out_triplet.keywords,
                    in_triplet.keywords,
                    out_triplet.embedding,
                    in_triplet.embedding,
                )

                # Apply minimum similarity threshold
                if hybrid < self._min_similarity:
                    continue

                candidates.append(
                    MergedEdge(
                        source_id=out_triplet.vertex_id,
                        target_id=in_triplet.vertex_id,
                        similarity=hybrid,
                        source_question=out_triplet.question,
                        target_question=in_triplet.question,
                        jaccard_score=jaccard,
                        cosine_score=cosine,
                    )
                )

        total_candidates = len(candidates)

        # Sort by similarity descending
        candidates.sort(key=lambda e: -e.similarity)

        # Apply density limit
        edges = candidates[:density_limit]

        # Apply per-vertex cap if configured
        if self._max_per_vertex is not None:
            edges = self._apply_per_vertex_cap(edges, self._max_per_vertex)

        logger.info(
            "EdgeMerger: %d candidates → %d edges (density_limit=%d, vertex_count=%d)",
            total_candidates,
            len(edges),
            density_limit,
            vertex_count,
        )

        return MergeResult(
            edges=edges,
            total_candidates=total_candidates,
            density_limit=density_limit,
            vertex_count=vertex_count,
        )

    @staticmethod
    def _apply_per_vertex_cap(
        edges: list[MergedEdge],
        max_per_vertex: int,
    ) -> list[MergedEdge]:
        """Enforce per-vertex outgoing edge cap.

        Args:
            edges: Edges sorted by similarity descending.
            max_per_vertex: Maximum outgoing edges per source vertex.

        Returns:
            Filtered edge list respecting per-vertex cap.
        """
        vertex_counts: dict[str, int] = {}
        filtered: list[MergedEdge] = []

        for edge in edges:
            count = vertex_counts.get(edge.source_id, 0)
            if count < max_per_vertex:
                filtered.append(edge)
                vertex_counts[edge.source_id] = count + 1

        return filtered

    @staticmethod
    def _jaccard_similarity(
        set1: frozenset[str],
        set2: frozenset[str],
    ) -> float:
        """Compute Jaccard similarity between two keyword sets.

        Args:
            set1: First keyword set.
            set2: Second keyword set.

        Returns:
            Jaccard similarity in [0.0, 1.0]. Returns 0.0 if both sets empty.
        """
        if not set1 and not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        if union == 0:
            return 0.0
        return intersection / union

    @staticmethod
    def _cosine_similarity(
        vec1: npt.NDArray[Any] | None,
        vec2: npt.NDArray[Any] | None,
    ) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec1: First embedding vector.
            vec2: Second embedding vector.

        Returns:
            Cosine similarity in [-1.0, 1.0]. Returns 0.0 if either is None.
        """
        if vec1 is None or vec2 is None:
            return 0.0
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))  # nosemgrep: float-requires-try-except
