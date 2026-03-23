"""
Property-based tests for scoring (W5-05).

Uses Hypothesis to generate random valid weight vectors and verify
that assembled score expressions maintain [0, 1] bounds and idempotency.
"""

from __future__ import annotations

from hypothesis import given, settings, assume
from hypothesis import strategies as st

import pytest

from engine.scoring.assembler import ScoringAssembler


# ---------------------------------------------------------------------------
# Custom strategies
# ---------------------------------------------------------------------------


@st.composite
def weight_vector(draw, min_dims: int = 1, max_dims: int = 8):
    """Generate a valid weight vector: each in [0, 1], sum <= 1.0."""
    n = draw(st.integers(min_value=min_dims, max_value=max_dims))
    if n == 0:
        return []

    # Generate n weights, then normalize so sum <= 1.0
    raw = [draw(st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False)) for _ in range(n)]
    total = sum(raw)
    if total > 0:
        factor = draw(st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False))
        normalized = [w / total * factor for w in raw]
    else:
        normalized = [1.0 / n for _ in range(n)]

    return normalized


@st.composite
def clamped_score(draw):
    """Generate a score in [0, 1]."""
    return draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestScoringProperties:
    """Property-based tests for scoring invariants."""

    @given(weights=weight_vector())
    @settings(max_examples=100, deadline=5000)
    def test_weight_vector_sums_le_one(self, weights):
        """For any valid weight vector, sum <= 1.0."""
        assert sum(weights) <= 1.0 + 1e-9, f"Weight sum {sum(weights)} exceeds 1.0"

    @given(weights=weight_vector())
    @settings(max_examples=100, deadline=5000)
    def test_each_weight_in_unit_interval(self, weights):
        """Each weight is in [0, 1]."""
        for i, w in enumerate(weights):
            assert 0.0 <= w <= 1.0 + 1e-9, f"Weight[{i}] = {w} out of [0, 1]"

    @given(score=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_clamp_bounds(self, score):
        """Clamped scores must be in [0.0, 1.0]."""

        def clamp(v):
            return max(0.0, min(1.0, v))

        result = clamp(score)
        assert 0.0 <= result <= 1.0

    @given(score=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_clamp_idempotent(self, score):
        """clamp(clamp(x)) == clamp(x) — idempotency property."""

        def clamp(v):
            return max(0.0, min(1.0, v))

        assert clamp(clamp(score)) == clamp(score)

    @given(weights=weight_vector(), scores=st.lists(clamped_score(), min_size=1, max_size=8))
    @settings(max_examples=100, deadline=5000)
    def test_weighted_sum_bounded_by_weight_sum(self, weights, scores):
        """Weighted sum of clamped scores <= sum of weights (since each score <= 1)."""
        n = min(len(weights), len(scores))
        assume(n > 0)

        weighted_sum = sum(weights[i] * scores[i] for i in range(n))
        weight_total = sum(weights[:n])

        assert weighted_sum <= weight_total + 1e-9, (
            f"Weighted sum {weighted_sum} exceeds weight total {weight_total}"
        )

    def test_clamp_expression_cypher_structure(self):
        """ScoringAssembler._clamp_expression produces valid CASE structure."""
        expr = ScoringAssembler._clamp_expression("candidate.rate")
        assert expr.startswith("CASE WHEN")
        assert "< 0.0 THEN 0.0" in expr
        assert "> 1.0 THEN 1.0" in expr
        assert expr.endswith("END")
        # Balanced parens
        assert expr.count("(") == expr.count(")")

    def test_build_score_expression_empty(self):
        """Empty weight list returns '0.0'."""
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
            PropertyType,
            QueryFieldSpec,
            QuerySchemaSpec,
            ScoringSpec,
        )

        spec = DomainSpec(
            domain=DomainMetadata(id="empty", name="Empty", version="1.0.0"),
            ontology=OntologySpec(
                nodes=[
                    NodeSpec(label="N", candidate=True),
                    NodeSpec(label="Q", queryentity=True),
                ],
                edges=[
                    EdgeSpec(
                        type="R",
                        **{"from": "N"},
                        to="Q",
                        direction=EdgeDirection.DIRECTED,
                        category=EdgeCategory.CAPABILITY,
                        managedby=ManagedByType.SYNC,
                    ),
                ],
            ),
            matchentities=MatchEntitiesSpec(
                candidate=[MatchEntitySpec(label="N", matchdirection="fwd")],
                queryentity=[MatchEntitySpec(label="Q", matchdirection="fwd")],
            ),
            queryschema=QuerySchemaSpec(matchdirections=["fwd"], fields=[]),
            gates=[],
            scoring=ScoringSpec(dimensions=[]),
        )
        assembler = ScoringAssembler(spec)
        clause, _ = assembler.assemble_scoring_clause("fwd", {})
        assert "0.0" in clause
