# ============================================================================
# tests/unit/test_scoring.py
# ============================================================================

"""
Unit tests for scoring dimension assembly.
Target Coverage: 75%+
"""

import pytest

from engine.scoring.assembler import ScoringAssembler


@pytest.mark.unit
class TestScoringAssembler:
    """Test scoring dimension compilation."""

    def test_geodecay_compiles(self, scoring_dimension_geodecay):
        """Geodecay dimension compiles distance formula."""
        assembler = ScoringAssembler(dimensions=[scoring_dimension_geodecay])

        cypher = assembler.assemble(candidate_alias="c", query_alias="$query", match_direction="buyertosupplier")

        assert "distance" in cypher.lower()
        assert "point.distance" in cypher or "haversine" in cypher

    def test_inverselinear_compiles(self, scoring_dimension_inverselinear):
        """Inverse linear dimension compiles formula."""
        assembler = ScoringAssembler(dimensions=[scoring_dimension_inverselinear])

        cypher = assembler.assemble("c", "$query", "buyertosupplier")

        assert "priceperlb" in cypher

    def test_weighted_aggregation(self):
        """Multiple dimensions aggregate with weights."""
        dimensions = [
            {
                "name": "score1",
                "source": "candidateproperty",
                "candidateprop": "prop1",
                "computation": "candidateproperty",
                "weightkey": "w1",
                "defaultweight": 0.5,
            },
            {
                "name": "score2",
                "source": "candidateproperty",
                "candidateprop": "prop2",
                "computation": "candidateproperty",
                "weightkey": "w2",
                "defaultweight": 0.5,
            },
        ]

        assembler = ScoringAssembler(dimensions=dimensions)
        cypher = assembler.assemble("c", "$query", "querytocandidate")

        assert "w1" in cypher
        assert "w2" in cypher

    def test_direction_scoped_filtering(self):
        """Direction-scoped dimensions only apply to specific directions."""
        dimension = {
            "name": "directional_score",
            "source": "candidateproperty",
            "candidateprop": "score",
            "computation": "candidateproperty",
            "weightkey": "wscore",
            "defaultweight": 1.0,
            "directionscoped": ["buyertosupplier"],  # Only this direction
        }

        assembler = ScoringAssembler(dimensions=[dimension])

        # Should include in buyertosupplier
        cypher1 = assembler.assemble("c", "$query", "buyertosupplier")
        assert "score" in cypher1

        # Should exclude in other direction
        cypher2 = assembler.assemble("c", "$query", "suppliertobuyer")
        assert "score" not in cypher2 or cypher2 == ""
