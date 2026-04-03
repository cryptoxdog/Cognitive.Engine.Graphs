"""
--- L9_META ---
l9_schema: 1
origin: tests
engine: graph
layer: [tests]
tags: [hoprag, integration, pipeline, test]
owner: engine-team
status: active
--- /L9_META ---

Integration tests for the full HopRAG pipeline.

Tests the end-to-end flow:
1. Pseudo-query generation → edge merging → graph index construction
2. Multi-hop traversal → visit counting → importance scoring → helpfulness ranking
3. Configuration loading → feature gating → fallback behavior

These tests use mock implementations for external dependencies
(Neo4j, LLM) to validate pipeline correctness without infrastructure.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from engine.hoprag.config import HopRAGConfig, ReasoningMode
from engine.scoring.helpfulness import HelpfulnessScorer
from engine.scoring.importance import ImportanceScorer
from engine.traversal.edge_merger import EdgeMerger, EdgeTriplet
from engine.traversal.multihop import (
    MultiHopTraverser,
    TraversalEdge,
)
from engine.traversal.multihop import (
    ReasoningMode as TraversalReasoningMode,
)
from engine.traversal.pseudo_query import PseudoQueryGenerator

# ── Mock Implementations ─────────────────────────────────────────────


class MockLLM:
    """Mock LLM for pseudo-query generation."""

    def generate(self, prompt: str) -> str:
        if "exactly 2" in prompt:
            return "1. What is the main topic?\n2. What are the key findings?"
        if "exactly 4" in prompt:
            return (
                "1. How does this relate to other research?\n"
                "2. What are the implications?\n"
                "3. What methodology was used?\n"
                "4. What are the limitations?"
            )
        return "1. Generic question?\n2. Another question?"


class MockKeywordExtractor:
    """Mock NER keyword extractor."""

    def extract(self, text: str) -> frozenset[str]:
        words = text.lower().split()
        return frozenset(w for w in words if len(w) > 4 and w.isalpha())


class MockEmbeddingEncoder:
    """Mock embedding encoder producing deterministic embeddings."""

    def encode(self, text: str) -> tuple[float, ...]:
        # Deterministic hash-based embedding
        h = hash(text) % 10000
        return (h / 10000.0, (h % 100) / 100.0, ((h * 7) % 100) / 100.0)


class MockNeighborFetcher:
    """Mock graph neighbor fetcher."""

    def __init__(self, graph: dict[str, list[TraversalEdge]]) -> None:
        self._graph = graph

    async def get_outgoing_edges(self, vertex_id: str) -> list[TraversalEdge]:
        return self._graph.get(vertex_id, [])


class MockGraphStore:
    """Mock graph store for indexer tests."""

    def __init__(self, passages: list[dict[str, Any]]) -> None:
        self._passages = passages
        self._written_edges: list[dict[str, Any]] = []

    async def fetch_passages(
        self,
        label: str,
        batch_size: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._passages[offset : offset + batch_size]

    async def write_edges(
        self,
        edges: list[dict[str, Any]],
        edge_type: str = "HOPRAG_EDGE",
    ) -> int:
        self._written_edges.extend(edges)
        return len(edges)

    async def get_vertex_count(self, label: str) -> int:
        return len(self._passages)


# ── Integration Tests ────────────────────────────────────────────────


class TestPseudoQueryToEdgePipeline:
    """Test pseudo-query generation → edge merging pipeline."""

    def test_full_pipeline(self) -> None:
        """Pseudo-queries should produce valid edges via merger."""
        # Step 1: Generate pseudo-queries
        llm = MockLLM()
        kw = MockKeywordExtractor()
        emb = MockEmbeddingEncoder()
        gen = PseudoQueryGenerator(
            llm=llm,
            keyword_extractor=kw,
            embedding_encoder=emb,
        )

        passages = [
            {"id": "p1", "text": "Machine learning uses statistical models to make predictions."},
            {"id": "p2", "text": "Neural networks are a type of machine learning architecture."},
            {"id": "p3", "text": "Transformers revolutionized natural language processing."},
        ]

        all_queries = gen.generate_batch(passages, n_incoming=2, m_outgoing=4)
        assert len(all_queries) == 3

        # Step 2: Build triplet lists
        outgoing_triplets: list[EdgeTriplet] = []
        incoming_triplets: list[EdgeTriplet] = []

        for pq in all_queries:
            for t in pq.outgoing:
                outgoing_triplets.append(
                    EdgeTriplet(
                        vertex_id=pq.passage_id,
                        question=t.question,
                        keywords=t.keywords,
                        embedding=np.array(t.embedding) if t.embedding else None,
                    )
                )
            for t in pq.incoming:
                incoming_triplets.append(
                    EdgeTriplet(
                        vertex_id=pq.passage_id,
                        question=t.question,
                        keywords=t.keywords,
                        embedding=np.array(t.embedding) if t.embedding else None,
                    )
                )

        # Step 3: Merge edges
        merger = EdgeMerger(density_factor=1.0)
        result = merger.merge_edges(
            outgoing_triplets=outgoing_triplets,
            incoming_triplets=incoming_triplets,
            vertex_count=3,
        )

        # Verify edges were created
        assert len(result.edges) > 0
        assert result.vertex_count == 3

        # Verify no self-edges
        for edge in result.edges:
            assert edge.source_id != edge.target_id

        # Verify similarity scores are valid
        for edge in result.edges:
            assert 0.0 <= edge.similarity <= 1.0


class TestTraversalToScoringPipeline:
    """Test multi-hop traversal → importance → helpfulness pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline(self) -> None:
        """Traversal visit counts should produce valid helpfulness scores."""
        # Build a small graph: A→B→C, A→D→C (convergent paths to C)
        emb_b = np.array([0.8, 0.2, 0.0])
        emb_c = np.array([0.6, 0.4, 0.0])
        emb_d = np.array([0.7, 0.3, 0.0])

        graph = {
            "A": [
                TraversalEdge("A", "B", "What is B?", embedding=emb_b),
                TraversalEdge("A", "D", "What is D?", embedding=emb_d),
            ],
            "B": [TraversalEdge("B", "C", "What is C?", embedding=emb_c)],
            "D": [TraversalEdge("D", "C", "What is C via D?", embedding=emb_c)],
            "C": [],
        }

        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=TraversalReasoningMode.SIMILARITY,
            max_hops=3,
            top_k=5,
        )

        # Step 1: Traverse
        query_embedding = np.array([0.7, 0.3, 0.0])
        result = await traverser.traverse(
            start_vertices=["A"],
            query_embedding=query_embedding,
        )

        assert len(result.visit_counts) > 0

        # Step 2: Compute importance
        importance_scorer = ImportanceScorer()
        importance_results = importance_scorer.compute_all(result.visit_counts)

        # Verify importance scores sum to 1.0
        total_importance = sum(r.score for r in importance_results.values())
        assert total_importance == pytest.approx(1.0, abs=1e-6)

        # Step 3: Compute helpfulness (with mock similarity scores)
        helpfulness_scorer = HelpfulnessScorer(alpha=0.5)
        candidates = []
        for vid, imp_result in importance_results.items():
            # Mock similarity score based on embedding distance
            sim = 0.8 if vid in ["B", "C"] else 0.5
            candidates.append({"similarity": sim, "importance": imp_result.score})

        helpfulness_results = helpfulness_scorer.compute_batch(candidates)
        assert len(helpfulness_results) == len(importance_results)

        # Verify all scores are in valid range
        for hr in helpfulness_results:
            assert 0.0 <= hr.score <= 1.0


class TestConfigurationGating:
    """Test feature gating and configuration behavior."""

    def test_disabled_config(self) -> None:
        """Disabled config should prevent pipeline execution."""
        config = HopRAGConfig(enabled=False)
        assert not config.enabled

    def test_default_config_values(self) -> None:
        """Default config should match HopRAG paper defaults."""
        config = HopRAGConfig()
        assert config.n_hop == 4
        assert config.top_k == 12
        assert config.alpha == 0.5
        assert config.reasoning_mode == "similarity"

    def test_config_from_dict(self) -> None:
        """Config should load from dictionary."""
        data = {
            "enabled": True,
            "n_hop": 3,
            "top_k": 10,
            "alpha": 0.7,
        }
        config = HopRAGConfig.from_dict(data)
        assert config.enabled is True
        assert config.n_hop == 3
        assert config.alpha == 0.7

    def test_effective_reasoning_mode_fallback(self) -> None:
        """LLM mode with no model should fall back to similarity."""
        config = HopRAGConfig(
            reasoning_mode=ReasoningMode.LLM,
            traversal_model="none",
        )
        effective = config.effective_reasoning_mode()
        assert effective == ReasoningMode.SIMILARITY

    def test_invalid_n_hop_raises(self) -> None:
        """Invalid n_hop should raise ValueError."""
        with pytest.raises(ValueError, match="n_hop must be >= 1"):
            HopRAGConfig(n_hop=0)

    def test_invalid_alpha_raises(self) -> None:
        """Invalid alpha should raise ValueError."""
        with pytest.raises(ValueError, match="alpha must be in"):
            HopRAGConfig(alpha=1.5)


class TestEndToEndScenario:
    """Test a realistic end-to-end scenario."""

    @pytest.mark.asyncio
    async def test_multi_query_scenario(self) -> None:
        """Multiple queries against the same graph should produce ranked results."""
        # Build a knowledge graph about science
        emb_physics = np.array([1.0, 0.0, 0.0])
        emb_chemistry = np.array([0.0, 1.0, 0.0])
        emb_biology = np.array([0.0, 0.0, 1.0])
        emb_quantum = np.array([0.9, 0.1, 0.0])
        emb_organic = np.array([0.1, 0.9, 0.0])

        graph = {
            "physics": [
                TraversalEdge("physics", "quantum", "What is quantum physics?", embedding=emb_quantum),
            ],
            "chemistry": [
                TraversalEdge("chemistry", "organic", "What is organic chemistry?", embedding=emb_organic),
            ],
            "biology": [],
            "quantum": [
                TraversalEdge(
                    "quantum", "chemistry", "How does quantum mechanics apply to chemistry?", embedding=emb_chemistry
                ),
            ],
            "organic": [],
        }

        fetcher = MockNeighborFetcher(graph)
        traverser = MultiHopTraverser(
            neighbor_fetcher=fetcher,
            reasoning_mode=TraversalReasoningMode.SIMILARITY,
            max_hops=3,
            top_k=5,
        )

        # Query 1: Physics-related query
        physics_query = np.array([0.9, 0.1, 0.0])
        result1 = await traverser.traverse(
            start_vertices=["physics"],
            query_embedding=physics_query,
        )

        # Query 2: Chemistry-related query
        chemistry_query = np.array([0.1, 0.9, 0.0])
        result2 = await traverser.traverse(
            start_vertices=["chemistry"],
            query_embedding=chemistry_query,
        )

        # Physics query should visit quantum (high similarity)
        assert "quantum" in result1.visit_counts

        # Chemistry query should visit organic
        assert "organic" in result2.visit_counts

        # Both queries should have valid visit count distributions
        for result in [result1, result2]:
            imp_scorer = ImportanceScorer()
            if result.visit_counts:
                scores = imp_scorer.compute_all(result.visit_counts)
                total = sum(s.score for s in scores.values())
                assert total == pytest.approx(1.0, abs=1e-6)
