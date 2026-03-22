"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, feedback, pattern-matcher]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine.feedback.pattern_matcher — ConfigurationMatcher + jaccard_similarity.

Covers:
- Jaccard similarity calculation (pure function)
- Similarity threshold filtering
- Negative pattern detection
- Empty history returns empty results
- Config key extraction
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from engine.config.schema import DomainSpec, FeedbackLoopSpec
from engine.feedback.pattern_matcher import ConfigurationMatcher, jaccard_similarity

# ── Jaccard Similarity (pure function) ──────────────────


class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"}) == 1.0

    def test_disjoint_sets(self):
        assert jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        # {a,b,c} & {b,c,d} = {b,c}, union = {a,b,c,d}
        result = jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
        assert result == pytest.approx(0.5)

    def test_empty_sets(self):
        assert jaccard_similarity(set(), set()) == 0.0

    def test_one_empty_set(self):
        assert jaccard_similarity({"a"}, set()) == 0.0

    def test_single_element_match(self):
        assert jaccard_similarity({"a"}, {"a"}) == 1.0

    def test_superset_subset(self):
        # {a,b} & {a,b,c} = {a,b}, union={a,b,c}
        result = jaccard_similarity({"a", "b"}, {"a", "b", "c"})
        assert result == pytest.approx(2.0 / 3.0, abs=0.001)


# ── Config Key Extraction ────────────────────────────────


class TestConfigKeyExtraction:
    def test_flat_keys(self):
        config = {"region": "US", "material": "PET", "active": True}
        keys = ConfigurationMatcher._extract_config_keys(config)
        assert "region" in keys
        assert "material" in keys
        assert "active" in keys

    def test_nested_dict_keys(self):
        config = {"weights": {"geo": 1.0, "price": 0.5}}
        keys = ConfigurationMatcher._extract_config_keys(config)
        assert "weights.geo" in keys
        assert "weights.price" in keys

    def test_list_keys(self):
        config = {"materials": ["PET", "HDPE", "PP"]}
        keys = ConfigurationMatcher._extract_config_keys(config)
        assert "materials[3]" in keys

    def test_none_values_excluded(self):
        config = {"region": "US", "extra": None}
        keys = ConfigurationMatcher._extract_config_keys(config)
        assert "region" in keys
        assert "extra" not in keys


# ── ConfigurationMatcher ─────────────────────────────────


def _minimal_spec() -> DomainSpec:
    return DomainSpec(
        domain={"id": "test", "name": "Test", "version": "0.0.1"},
        ontology={
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "Query",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "query_id", "type": "int", "required": True}],
                },
            ],
            "edges": [
                {
                    "type": "TRANSACTED_WITH",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "sync",
                }
            ],
        },
        matchentities={
            "candidate": [{"label": "Facility", "matchdirection": "d1"}],
            "queryentity": [{"label": "Query", "matchdirection": "d1"}],
        },
        queryschema={"matchdirections": ["d1"], "fields": []},
        gates=[],
        scoring={"dimensions": []},
        feedbackloop=FeedbackLoopSpec(enabled=True),
    )


def _mock_driver() -> AsyncMock:
    driver = AsyncMock()
    driver.execute_query = AsyncMock(return_value=[])
    return driver


class TestFindSimilarOutcomes:
    @pytest.mark.asyncio
    async def test_empty_history_returns_empty(self):
        spec = _minimal_spec()
        driver = _mock_driver()
        matcher = ConfigurationMatcher(driver, spec)

        result = await matcher.find_similar_outcomes(
            current_config={"region": "US"},
            outcome_type="success",
        )
        assert result == []

    @pytest.mark.asyncio
    async def test_matching_outcomes_returned(self):
        spec = _minimal_spec()
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            return_value=[
                {
                    "outcome_id": "out_1",
                    "match_id": "m1",
                    "candidate_id": "c1",
                    "config_keys": ["region", "material", "price"],
                    "outcome": "success",
                    "value": 100,
                },
            ]
        )

        matcher = ConfigurationMatcher(driver, spec)
        result = await matcher.find_similar_outcomes(
            current_config={"region": "US", "material": "PET", "volume": 500},
            outcome_type="success",
            similarity_threshold=0.3,
        )

        assert len(result) == 1
        assert result[0]["outcome_id"] == "out_1"
        assert result[0]["similarity"] > 0.3

    @pytest.mark.asyncio
    async def test_threshold_filters_low_similarity(self):
        spec = _minimal_spec()
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            return_value=[
                {
                    "outcome_id": "out_1",
                    "match_id": "m1",
                    "candidate_id": "c1",
                    "config_keys": ["completely", "different", "keys"],
                    "outcome": "success",
                    "value": 100,
                },
            ]
        )

        matcher = ConfigurationMatcher(driver, spec)
        result = await matcher.find_similar_outcomes(
            current_config={"region": "US"},
            outcome_type="success",
            similarity_threshold=0.5,
        )

        # Different keys -> low similarity -> filtered out
        assert result == []


class TestDetectNegativePatterns:
    @pytest.mark.asyncio
    async def test_detect_failure_patterns(self):
        spec = _minimal_spec()
        driver = _mock_driver()
        driver.execute_query = AsyncMock(
            return_value=[
                {
                    "outcome_id": "out_bad",
                    "match_id": "m2",
                    "candidate_id": "c2",
                    "config_keys": ["region", "material"],
                    "outcome": "failure",
                    "value": None,
                },
            ]
        )

        matcher = ConfigurationMatcher(driver, spec)
        result = await matcher.detect_negative_patterns(
            current_config={"region": "US", "material": "PET"},
            similarity_threshold=0.5,
        )

        assert len(result) == 1
        assert result[0]["outcome"] == "failure"
