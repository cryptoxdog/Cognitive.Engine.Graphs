"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [hoprag, indexing]
tags: [hoprag, indexer, graph-construction, pseudo-query]
owner: engine-team
status: active
--- /L9_META ---

Graph index builder for HopRAG.

Orchestrates the full HopRAG index construction pipeline:
1. Load passages from graph vertices
2. Generate pseudo-queries (in-coming + out-coming) via LLM
3. Merge edges using hybrid similarity
4. Write edges to Neo4j graph

This runs as an offline batch process, not in the query path.
Triggered via admin subaction or scheduled job.

Consumes:
- engine.hoprag.config.HopRAGConfig
- engine.traversal.pseudo_query.PseudoQueryGenerator
- engine.traversal.edge_merger.EdgeMerger
- Neo4j graph driver for read/write

Integrates with:
- engine.handlers.handle_admin (trigger via admin subaction)
- engine.hoprag.config.HopRAGConfig (all parameters)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from engine.hoprag.config import HopRAGConfig
from engine.traversal.edge_merger import EdgeMerger, EdgeTriplet, MergeResult
from engine.traversal.pseudo_query import (
    PassageQueries,
    PseudoQueryGenerator,
)

logger = logging.getLogger(__name__)


class GraphStore(Protocol):
    """Protocol for graph store operations."""

    async def fetch_passages(
        self,
        label: str,
        batch_size: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Fetch passage vertices from the graph.

        Args:
            label: Node label to fetch.
            batch_size: Number of passages per batch.
            offset: Starting offset for pagination.

        Returns:
            List of dicts with 'id' and 'text' keys.
        """
        ...

    async def write_edges(
        self,
        edges: list[dict[str, Any]],
        edge_type: str = "HOPRAG_EDGE",
    ) -> int:
        """Write directed edges to the graph.

        Args:
            edges: List of edge dicts with source_id, target_id, properties.
            edge_type: Neo4j relationship type.

        Returns:
            Number of edges written.
        """
        ...

    async def get_vertex_count(self, label: str) -> int:
        """Count vertices with given label.

        Args:
            label: Node label to count.

        Returns:
            Number of vertices.
        """
        ...


@dataclass
class IndexBuildResult:
    """Result of a graph index build operation.

    Attributes:
        passages_processed: Number of passages analyzed.
        questions_generated: Total pseudo-queries generated.
        edges_created: Number of edges written to graph.
        density_limit: Computed density limit.
        execution_time_s: Total build time in seconds.
        errors: List of error messages.
    """

    passages_processed: int = 0
    questions_generated: int = 0
    edges_created: int = 0
    density_limit: int = 0
    execution_time_s: float = 0.0  # nosemgrep: float-requires-try-except
    errors: list[str] = field(default_factory=list)


class GraphIndexBuilder:
    """Builds HopRAG graph-structured index.

    Orchestrates the full pipeline:
    1. Fetch passages from graph
    2. Generate pseudo-queries per passage
    3. Merge pseudo-queries into directed edges
    4. Write edges to graph

    Usage::

        builder = GraphIndexBuilder(
            config=HopRAGConfig(enabled=True),
            query_generator=pseudo_gen,
            graph_store=neo4j_store,
        )
        result = await builder.build(passage_label="Passage")
        edges_created = result.edges_created
    """

    def __init__(
        self,
        config: HopRAGConfig,
        query_generator: PseudoQueryGenerator,
        graph_store: GraphStore,
        edge_merger: EdgeMerger | None = None,
    ) -> None:
        """Initialize GraphIndexBuilder.

        Args:
            config: HopRAG configuration.
            query_generator: Pseudo-query generator with LLM.
            graph_store: Graph store for read/write.
            edge_merger: Optional edge merger (created from config if None).
        """
        self._config = config
        self._query_gen = query_generator
        self._store = graph_store
        self._merger = edge_merger or EdgeMerger(
            density_factor=config.edge_density_factor,
            min_similarity=config.min_similarity_threshold,
            max_edges_per_vertex=config.max_edges_per_vertex,
        )

    async def build(
        self,
        passage_label: str = "Passage",
    ) -> IndexBuildResult:
        """Build the complete HopRAG graph index.

        Args:
            passage_label: Neo4j node label for passage vertices.

        Returns:
            IndexBuildResult with build statistics.
        """
        start_time = time.monotonic()
        result = IndexBuildResult()

        if not self._config.enabled:
            logger.warning("HopRAG indexer skipped — hoprag.enabled=False")
            return result

        try:
            # Step 1: Get vertex count for density calculation
            vertex_count = await self._store.get_vertex_count(passage_label)
            logger.info("Found %d %s vertices", vertex_count, passage_label)

            if vertex_count == 0:
                return result

            # Step 2: Fetch and process passages in batches
            all_passage_queries: list[PassageQueries] = []
            offset = 0
            batch_size = self._config.index_batch_size

            while offset < vertex_count:
                passages = await self._store.fetch_passages(
                    label=passage_label,
                    batch_size=batch_size,
                    offset=offset,
                )
                if not passages:
                    break

                batch_queries = self._query_gen.generate_batch(
                    passages=passages,
                    n_incoming=self._config.n_incoming_questions,
                    m_outgoing=self._config.m_outgoing_questions,
                )
                all_passage_queries.extend(batch_queries)

                result.passages_processed += len(passages)
                offset += batch_size

                logger.info(
                    "Processed %d/%d passages",
                    result.passages_processed,
                    vertex_count,
                )

            # Count total questions generated
            for pq in all_passage_queries:
                result.questions_generated += len(pq.incoming) + len(pq.outgoing)

            # Step 3: Build triplet lists for edge merging
            outgoing_triplets: list[EdgeTriplet] = []
            incoming_triplets: list[EdgeTriplet] = []

            for pq in all_passage_queries:
                for triplet in pq.outgoing:
                    outgoing_triplets.append(
                        EdgeTriplet(
                            vertex_id=pq.passage_id,
                            question=triplet.question,
                            keywords=triplet.keywords,
                            embedding=(__import__("numpy").array(triplet.embedding) if triplet.embedding else None),
                        )
                    )
                for triplet in pq.incoming:
                    incoming_triplets.append(
                        EdgeTriplet(
                            vertex_id=pq.passage_id,
                            question=triplet.question,
                            keywords=triplet.keywords,
                            embedding=(__import__("numpy").array(triplet.embedding) if triplet.embedding else None),
                        )
                    )

            # Step 4: Merge edges
            merge_result: MergeResult = self._merger.merge_edges(
                outgoing_triplets=outgoing_triplets,
                incoming_triplets=incoming_triplets,
                vertex_count=vertex_count,
            )
            result.density_limit = merge_result.density_limit

            # Step 5: Write edges to graph
            edge_dicts: list[dict[str, Any]] = []
            for edge in merge_result.edges:
                edge_dicts.append(
                    {
                        "source_id": edge.source_id,
                        "target_id": edge.target_id,
                        "similarity": edge.similarity,
                        "question": edge.source_question,
                        "jaccard_score": edge.jaccard_score,
                        "cosine_score": edge.cosine_score,
                    }
                )

            if edge_dicts:
                edges_written = await self._store.write_edges(
                    edges=edge_dicts,
                    edge_type="HOPRAG_EDGE",
                )
                result.edges_created = edges_written

        except Exception as exc:
            error_msg = f"Index build failed: {exc!s}"
            logger.exception(error_msg)
            result.errors.append(error_msg)

        result.execution_time_s = time.monotonic() - start_time

        logger.info(
            "GraphIndexBuilder complete: %d passages, %d questions, %d edges in %.1fs",
            result.passages_processed,
            result.questions_generated,
            result.edges_created,
            result.execution_time_s,
        )

        return result
