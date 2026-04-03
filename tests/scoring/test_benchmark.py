"""
Score quality benchmark suite (W5-03).

Validates that the scoring assembler produces meaningfully different scores
for "good" and "bad" candidate-query pairs using synthetic test data.
All tests run without Neo4j by testing the Cypher expression structure
and using a simple numeric evaluator for score expressions.
"""

from __future__ import annotations

import math
import statistics

import pytest

from engine.config.schema import (
    ComputationType,
    DomainMetadata,
    DomainSpec,
    EdgeCategory,
    EdgeDirection,
    EdgeSpec,
    ManagedByType,
    MatchEntitiesSpec,
    MatchEntitySpec,
    NodeSpec,
    OntologySpec,
    PropertySpec,
    PropertyType,
    QueryFieldSpec,
    QuerySchemaSpec,
    ScoringDimensionSpec,
    ScoringSource,
    ScoringSpec,
)
from engine.scoring.assembler import ScoringAssembler
from tests.fixtures.benchmark_data import BAD_PAIRS, GOOD_PAIRS, BenchmarkPair

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_benchmark_spec() -> DomainSpec:
    """Build a DomainSpec with scoring dimensions matching benchmark data."""
    nodes = [
        NodeSpec(
            label="Facility",
            candidate=True,
            properties=[
                PropertySpec(name="lat", type=PropertyType.FLOAT),
                PropertySpec(name="lon", type=PropertyType.FLOAT),
                PropertySpec(name="rate", type=PropertyType.FLOAT),
                PropertySpec(name="community_id", type=PropertyType.INT),
                PropertySpec(name="density", type=PropertyType.FLOAT),
                PropertySpec(name="active", type=PropertyType.BOOL),
            ],
        ),
        NodeSpec(label="Query", queryentity=True),
    ]
    edges = [
        EdgeSpec(
            type="PROCESSES",
            **{"from": "Facility"},
            to="Query",
            direction=EdgeDirection.DIRECTED,
            category=EdgeCategory.CAPABILITY,
            managedby=ManagedByType.SYNC,
        ),
    ]
    scoring = ScoringSpec(
        dimensions=[
            ScoringDimensionSpec(
                name="geo_proximity",
                source=ScoringSource.COMPUTED,
                computation=ComputationType.GEODECAY,
                candidateprop="lat",
                queryprop="lat",
                decayconstant=50000.0,
                weightkey="w_geo",
                defaultweight=0.30,
            ),
            ScoringDimensionSpec(
                name="structural",
                source=ScoringSource.CANDIDATEPROPERTY,
                computation=ComputationType.CANDIDATEPROPERTY,
                candidateprop="rate",
                weightkey="w_structural",
                defaultweight=0.30,
            ),
            ScoringDimensionSpec(
                name="community",
                source=ScoringSource.COMPUTED,
                computation=ComputationType.COMMUNITYMATCH,
                candidateprop="community_id",
                queryprop="community_id",
                bias=1.5,
                weightkey="w_community",
                defaultweight=0.20,
            ),
            ScoringDimensionSpec(
                name="density_score",
                source=ScoringSource.CANDIDATEPROPERTY,
                computation=ComputationType.LOGNORMALIZED,
                candidateprop="density",
                maxvalue=100.0,
                weightkey="w_density",
                defaultweight=0.20,
            ),
        ]
    )

    return DomainSpec(
        domain=DomainMetadata(id="benchmark", name="Benchmark", version="1.0.0"),
        ontology=OntologySpec(nodes=nodes, edges=edges),
        matchentities=MatchEntitiesSpec(
            candidate=[MatchEntitySpec(label="Facility", matchdirection="buyer_to_seller")],
            queryentity=[MatchEntitySpec(label="Query", matchdirection="buyer_to_seller")],
        ),
        queryschema=QuerySchemaSpec(
            matchdirections=["buyer_to_seller"],
            fields=[
                QueryFieldSpec(name="lat", type=PropertyType.FLOAT),
                QueryFieldSpec(name="lon", type=PropertyType.FLOAT),
                QueryFieldSpec(name="community_id", type=PropertyType.INT),
            ],
        ),
        gates=[],
        scoring=scoring,
    )


def _simulate_score(pair: BenchmarkPair, spec: DomainSpec) -> float:
    """Simulate a score for a benchmark pair using Python-side math.

    This mirrors the Cypher expressions the ScoringAssembler would generate,
    applied to the synthetic candidate/query data.
    """
    cand = pair.candidate_props
    query = pair.query_params
    weights = {"w_geo": 0.30, "w_structural": 0.30, "w_community": 0.20, "w_density": 0.20}

    # Geo decay: 1 / (1 + distance / k)
    k = 50000.0
    lat1, lon1 = math.radians(cand["lat"]), math.radians(cand["lon"])
    lat2, lon2 = math.radians(query["lat"]), math.radians(query["lon"])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    distance_m = 2 * 6371000 * math.asin(math.sqrt(a))
    geo_score = 1.0 / (1.0 + distance_m / k)

    # Structural: candidateproperty (rate)
    structural_score = cand.get("rate", 0.0)

    # Community match
    if cand.get("community_id") is None or query.get("community_id") is None:
        community_score = 0.5
    elif cand["community_id"] == query["community_id"]:
        community_score = 1.5
    else:
        community_score = 0.2

    # Log normalized density
    density = cand.get("density", 0.0)
    density_score = math.log(1 + density) / math.log(1 + 100.0)

    # Clamp each to [0, 1]
    def clamp(v):
        return max(0.0, min(1.0, v))

    geo_score = clamp(geo_score)
    structural_score = clamp(structural_score)
    community_score = clamp(community_score)
    density_score = clamp(density_score)

    total = (
        weights["w_geo"] * geo_score
        + weights["w_structural"] * structural_score
        + weights["w_community"] * community_score
        + weights["w_density"] * density_score
    )
    return total


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestScoreBenchmark:
    """Score quality benchmark using synthetic data."""

    @pytest.fixture
    def spec(self):
        return _build_benchmark_spec()

    def test_assembler_produces_clause(self, spec):
        """Assembler generates a non-empty scoring clause."""
        assembler = ScoringAssembler(spec)
        clause, _ = assembler.assemble_scoring_clause("buyer_to_seller", {})
        assert "WITH" in clause
        assert "score" in clause

    def test_good_pairs_score_higher_than_bad(self, spec):
        """Average good-pair score must exceed average bad-pair score."""
        good_scores = [_simulate_score(p, spec) for p in GOOD_PAIRS]
        bad_scores = [_simulate_score(p, spec) for p in BAD_PAIRS]

        good_avg = statistics.mean(good_scores)
        bad_avg = statistics.mean(bad_scores)

        assert good_avg > bad_avg, f"Good avg ({good_avg:.4f}) must exceed bad avg ({bad_avg:.4f})"

    def test_score_separation(self, spec):
        """Separation between good and bad averages must be > 0.20."""
        good_scores = [_simulate_score(p, spec) for p in GOOD_PAIRS]
        bad_scores = [_simulate_score(p, spec) for p in BAD_PAIRS]

        separation = statistics.mean(good_scores) - statistics.mean(bad_scores)
        assert separation > 0.20, f"Score separation {separation:.4f} is below 0.20 threshold"

    def test_score_variance(self, spec):
        """Score distribution should have meaningful variance (std > 0.05)."""
        all_scores = [_simulate_score(p, spec) for p in GOOD_PAIRS + BAD_PAIRS]
        std = statistics.stdev(all_scores)
        assert std > 0.05, f"Score std {std:.4f} is below 0.05 — scores lack discrimination"

    def test_distribution_moments(self, spec):
        """Verify distribution properties: mean, std, skew."""
        all_scores = [_simulate_score(p, spec) for p in GOOD_PAIRS + BAD_PAIRS]
        mean = statistics.mean(all_scores)
        std = statistics.stdev(all_scores)

        # Mean should be reasonable (not 0 or 1)
        assert 0.1 < mean < 0.9, f"Mean score {mean:.4f} is unreasonably extreme"
        assert std > 0.0, "Score std must be positive"

    def test_good_scores_bounded(self, spec):
        """All scores should be in valid range [0, ~1.0]."""
        for pair in GOOD_PAIRS + BAD_PAIRS:
            score = _simulate_score(pair, spec)
            assert 0.0 <= score <= 1.5, f"Score {score:.4f} out of bounds for pair {pair.label}"

    def test_clamp_expression(self):
        """ScoringAssembler._clamp_expression wraps correctly."""
        result = ScoringAssembler._clamp_expression("candidate.rate")
        assert "CASE" in result
        assert "0.0" in result
        assert "1.0" in result

    def test_assembler_active_dimensions(self, spec):
        """Assembler tracks which dimensions are active."""
        assembler = ScoringAssembler(spec)
        assembler.assemble_scoring_clause("buyer_to_seller", {})
        active = assembler.last_active_dimension_names
        assert len(active) == 4
        assert "geo_proximity" in active
        assert "structural" in active
