"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, resolver, entity-resolution]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for R8 entity resolution / semantic registry.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.config.schema import SemanticRegistrySpec
from engine.resolution.resolver import EntityResolver
from engine.resolution.similarity import SimilarityScorer


def _make_spec(
    threshold: float = 0.85,
    property_weight: float = 0.5,
    structural_weight: float = 0.3,
    behavioral_weight: float = 0.2,
    comparison_properties: list[str] | None = None,
    entity_labels: list[str] | None = None,
    max_candidates: int = 20,
) -> SemanticRegistrySpec:
    return SemanticRegistrySpec(
        enabled=True,
        entity_labels=entity_labels or ["Supplier"],
        similarity_threshold=threshold,
        property_weight=property_weight,
        structural_weight=structural_weight,
        behavioral_weight=behavioral_weight,
        comparison_properties=comparison_properties or ["name", "region"],
        max_candidates=max_candidates,
    )


def _mock_driver() -> MagicMock:
    driver = MagicMock()
    driver.execute_query = AsyncMock()
    return driver


@pytest.mark.unit
class TestSimilarityScorer:
    """Test multi-signal similarity scoring."""

    @pytest.mark.asyncio
    async def test_property_similarity_identical(self) -> None:
        """Identical properties yield similarity of 1.0."""
        spec = _make_spec(property_weight=1.0, structural_weight=0.0, behavioral_weight=0.0)
        driver = _mock_driver()

        # Property query returns matching values
        driver.execute_query.side_effect = [
            [{"a_name": "Acme", "b_name": "Acme", "a_region": "US", "b_region": "US"}],
            [{"shared_count": 0, "union_count": 0}],  # structural
            [{"shared_count": 0, "union_count": 0}],  # behavioral
        ]

        scorer = SimilarityScorer(spec, driver, "test_domain")
        sim = await scorer.compute_similarity("e1", "e2", "Supplier")

        assert sim == 1.0

    @pytest.mark.asyncio
    async def test_property_similarity_none(self) -> None:
        """No matching properties yield similarity of 0.0."""
        spec = _make_spec(property_weight=1.0, structural_weight=0.0, behavioral_weight=0.0)
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [{"a_name": "Acme", "b_name": "Globe", "a_region": "US", "b_region": "EU"}],
            [{"shared_count": 0, "union_count": 0}],
            [{"shared_count": 0, "union_count": 0}],
        ]

        scorer = SimilarityScorer(spec, driver, "test_domain")
        sim = await scorer.compute_similarity("e1", "e2", "Supplier")

        assert sim == 0.0

    @pytest.mark.asyncio
    async def test_structural_similarity(self) -> None:
        """Shared neighbors increase structural similarity."""
        spec = _make_spec(property_weight=0.0, structural_weight=1.0, behavioral_weight=0.0)
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [{"a_name": "A", "b_name": "B", "a_region": "US", "b_region": "EU"}],  # property
            [{"shared_count": 5, "union_count": 10}],  # structural: 5/10 = 0.5
            [{"shared_count": 0, "union_count": 0}],  # behavioral
        ]

        scorer = SimilarityScorer(spec, driver, "test_domain")
        sim = await scorer.compute_similarity("e1", "e2", "Supplier")

        assert abs(sim - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_behavioral_similarity(self) -> None:
        """Shared transaction patterns increase behavioral similarity."""
        spec = _make_spec(property_weight=0.0, structural_weight=0.0, behavioral_weight=1.0)
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [{"a_name": "A", "b_name": "B", "a_region": "US", "b_region": "EU"}],
            [{"shared_count": 0, "union_count": 0}],
            [{"shared_count": 3, "union_count": 6}],  # behavioral: 3/6 = 0.5
        ]

        scorer = SimilarityScorer(spec, driver, "test_domain")
        sim = await scorer.compute_similarity("e1", "e2", "Supplier")

        assert abs(sim - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_combined_score_weighted(self) -> None:
        """Final score correctly weights three signals."""
        spec = _make_spec(property_weight=0.5, structural_weight=0.3, behavioral_weight=0.2)
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [{"a_name": "Acme", "b_name": "Acme", "a_region": "US", "b_region": "EU"}],  # 1/2 = 0.5
            [{"shared_count": 4, "union_count": 8}],  # 4/8 = 0.5
            [{"shared_count": 2, "union_count": 10}],  # 2/10 = 0.2
        ]

        scorer = SimilarityScorer(spec, driver, "test_domain")
        sim = await scorer.compute_similarity("e1", "e2", "Supplier")

        # 0.5 * 0.5 + 0.3 * 0.5 + 0.2 * 0.2 = 0.25 + 0.15 + 0.04 = 0.44
        assert abs(sim - 0.44) < 0.01

    @pytest.mark.asyncio
    async def test_score_clamped_to_0_1(self) -> None:
        """Score is clamped between 0.0 and 1.0."""
        spec = _make_spec(property_weight=1.0, structural_weight=0.0, behavioral_weight=0.0)
        driver = _mock_driver()

        driver.execute_query.side_effect = [
            [{"a_name": "A", "b_name": "A", "a_region": "US", "b_region": "US"}],
            [{"shared_count": 0, "union_count": 0}],
            [{"shared_count": 0, "union_count": 0}],
        ]

        scorer = SimilarityScorer(spec, driver, "test_domain")
        sim = await scorer.compute_similarity("e1", "e2", "Supplier")

        assert 0.0 <= sim <= 1.0

    @pytest.mark.asyncio
    async def test_find_candidates_filters_by_threshold(self) -> None:
        """find_candidates only returns entities above threshold."""
        spec = _make_spec(threshold=0.6)
        driver = _mock_driver()

        # find_property_candidates returns 2 candidates
        driver.execute_query.side_effect = [
            [{"entity_id": "e2"}, {"entity_id": "e3"}],  # property candidates
            # e2 similarity computation (high)
            [{"a_name": "Acme", "b_name": "Acme", "a_region": "US", "b_region": "US"}],
            [{"shared_count": 5, "union_count": 5}],
            [{"shared_count": 2, "union_count": 4}],
            # e3 similarity computation (low)
            [{"a_name": "Acme", "b_name": "Globe", "a_region": "US", "b_region": "EU"}],
            [{"shared_count": 0, "union_count": 5}],
            [{"shared_count": 0, "union_count": 4}],
        ]

        scorer = SimilarityScorer(spec, driver, "test_domain")
        candidates = await scorer.find_candidates("e1", "Supplier")

        # e2 should pass (high similarity), e3 should not (low similarity)
        assert len(candidates) >= 1
        assert all(c["similarity"] >= 0.6 for c in candidates)


@pytest.mark.unit
class TestEntityResolver:
    """Test entity resolver."""

    @pytest.mark.asyncio
    async def test_resolve_entity_no_duplicates(self) -> None:
        """When no duplicates found, returns original entity as canonical."""
        spec = _make_spec()
        driver = _mock_driver()

        # find_candidates returns empty
        driver.execute_query.side_effect = [
            [],  # find_property_candidates returns nothing
        ]

        resolver = EntityResolver(spec, driver, "test_domain")
        result = await resolver.resolve_entity("e1", "Supplier")

        assert result["canonical_id"] == "e1"
        assert result["merged_count"] == 0
        assert result["resolution_ids"] == []

    @pytest.mark.asyncio
    async def test_resolve_entity_with_duplicate(self) -> None:
        """Duplicate found → creates RESOLVED_FROM edge to canonical."""
        spec = _make_spec(threshold=0.8)
        driver = _mock_driver()

        # find_candidates → find_property_candidates
        # Then compute_similarity for each
        driver.execute_query.side_effect = [
            # find_property_candidates
            [{"entity_id": "e2"}],
            # compute_similarity for e2 (all high)
            [{"a_name": "Acme", "b_name": "Acme", "a_region": "US", "b_region": "US"}],
            [{"shared_count": 8, "union_count": 10}],
            [{"shared_count": 3, "union_count": 4}],
            # find_canonical: e1 has more connections
            [{"entity_id": "e1"}],
            # create_resolution
            [],
        ]

        resolver = EntityResolver(spec, driver, "test_domain")
        result = await resolver.resolve_entity("e1", "Supplier")

        assert result["canonical_id"] == "e1"
        assert result["merged_count"] == 1
        assert len(result["resolution_ids"]) == 1

    @pytest.mark.asyncio
    async def test_resolve_batch_summary(self) -> None:
        """Batch resolution returns summary stats."""
        spec = _make_spec(threshold=0.5)
        driver = _mock_driver()

        # First call: list all entities
        # Second+: resolve each
        driver.execute_query.side_effect = [
            # list entities
            [{"entity_id": "e1"}, {"entity_id": "e2"}],
            # resolve e1: find_property_candidates returns nothing
            [],
            # resolve e2: find_property_candidates returns nothing
            [],
        ]

        resolver = EntityResolver(spec, driver, "test_domain")
        result = await resolver.resolve_batch("Supplier")

        assert result["total_entities"] == 2
        assert result["total_merged"] == 0
        assert result["resolution_groups"] == 0
