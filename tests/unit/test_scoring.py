"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, scoring]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for scoring dimension assembly.
Target Coverage: 75%+
"""

from unittest.mock import MagicMock

import pytest

from engine.config.schema import ComputationType, DomainSpec, ScoringDimensionSpec, ScoringSpec
from engine.scoring.assembler import ScoringAssembler


def make_mock_domain_spec(dimensions: list[dict] | None = None) -> MagicMock:
    """Create a mock DomainSpec with scoring config."""
    spec = MagicMock(spec=DomainSpec)
    spec.scoring = MagicMock(spec=ScoringSpec)

    mock_dims = []
    for dim_dict in dimensions or []:
        dim = MagicMock(spec=ScoringDimensionSpec)
        dim.name = dim_dict.get("name", "test_dim")
        dim.candidateprop = dim_dict.get("candidateprop")
        dim.queryprop = dim_dict.get("queryprop")
        dim.computation = ComputationType(dim_dict.get("computation", "candidateproperty"))
        dim.weightkey = dim_dict.get("weightkey", "w")
        dim.defaultweight = dim_dict.get("defaultweight", 1.0)
        dim.matchdirections = dim_dict.get("matchdirections") or dim_dict.get("directionscoped")
        dim.minvalue = dim_dict.get("minvalue")
        dim.maxvalue = dim_dict.get("maxvalue")
        dim.defaultwhennull = dim_dict.get("defaultwhennull", 0.0)
        dim.expression = dim_dict.get("expression")
        dim.alias = dim_dict.get("alias")
        dim.decayconstant = dim_dict.get("decayconstant")
        dim.bias = dim_dict.get("bias")
        mock_dims.append(dim)

    spec.scoring.dimensions = mock_dims
    return spec


@pytest.mark.unit
class TestScoringAssembler:
    """Test scoring dimension compilation."""

    def test_geodecay_compiles(self) -> None:
        """Geodecay dimension compiles distance formula."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "distance_score",
                    "computation": "geodecay",
                    "weightkey": "wgeo",
                    "defaultweight": 0.35,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="buyertosupplier", weights={})

        assert "distance" in cypher.lower()

    def test_inverselinear_compiles(self) -> None:
        """Inverse linear dimension compiles formula."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "price_score",
                    "candidateprop": "priceperlb",
                    "computation": "inverselinear",
                    "minvalue": 0.5,
                    "maxvalue": 2.0,
                    "weightkey": "wprice",
                    "defaultweight": 0.30,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="buyertosupplier", weights={})

        assert "priceperlb" in cypher

    def test_weighted_aggregation(self) -> None:
        """Multiple dimensions aggregate with weights."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "score1",
                    "candidateprop": "prop1",
                    "computation": "candidateproperty",
                    "weightkey": "w1",
                    "defaultweight": 0.5,
                },
                {
                    "name": "score2",
                    "candidateprop": "prop2",
                    "computation": "candidateproperty",
                    "weightkey": "w2",
                    "defaultweight": 0.5,
                },
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(
            match_direction="querytocandidate", weights={"w1": 0.6, "w2": 0.4}
        )

        assert "score1" in cypher
        assert "score2" in cypher
        assert "0.6" in cypher
        assert "0.4" in cypher

    def test_direction_scoped_filtering(self) -> None:
        """Direction-scoped dimensions only apply to specific directions."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "directional_score",
                    "candidateprop": "score",
                    "computation": "candidateproperty",
                    "weightkey": "wscore",
                    "defaultweight": 1.0,
                    "matchdirections": ["buyertosupplier"],
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        # Should include in buyertosupplier
        cypher1, _ = assembler.assemble_scoring_clause(match_direction="buyertosupplier", weights={})
        assert "directional_score" in cypher1

        # Should exclude in other direction
        cypher2, _ = assembler.assemble_scoring_clause(match_direction="suppliertobuyer", weights={})
        assert "directional_score" not in cypher2

    def test_empty_dimensions_returns_zero_score(self) -> None:
        """Empty dimensions list returns 0.0 score."""
        domain_spec = make_mock_domain_spec([])
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="any", weights={})

        assert "0.0" in cypher

    def test_candidateproperty_computation(self) -> None:
        """CandidateProperty computation uses coalesce."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "prop_score",
                    "candidateprop": "rating",
                    "computation": "candidateproperty",
                    "defaultwhennull": 0.5,
                    "weightkey": "wrating",
                    "defaultweight": 1.0,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="any", weights={})

        assert "coalesce" in cypher
        assert "rating" in cypher

    def test_variantdiscovery_compiles(self) -> None:
        """VariantDiscovery dimension reads pre-computed beam search score."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "variant_score",
                    "candidateprop": "variant_discovery_score",
                    "computation": "variantdiscovery",
                    "defaultwhennull": 0.0,
                    "weightkey": "wvariant",
                    "defaultweight": 0.15,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="any", weights={})

        assert "variant_discovery_score" in cypher
        assert "coalesce" in cypher
        assert "variant_score" in cypher

    def test_variantdiscovery_default_prop(self) -> None:
        """VariantDiscovery uses default property name when not specified."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "variant_score",
                    "computation": "variantdiscovery",
                    "defaultwhennull": 0.5,
                    "weightkey": "wvariant",
                    "defaultweight": 0.1,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="any", weights={})

        assert "variant_discovery_score" in cypher
        assert "0.5" in cypher

    def test_ensembleconfidence_compiles(self) -> None:
        """EnsembleConfidence dimension reads pre-computed fusion confidence."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "ensemble_conf",
                    "candidateprop": "ensemble_confidence",
                    "computation": "ensembleconfidence",
                    "defaultwhennull": 0.5,
                    "weightkey": "wensemble",
                    "defaultweight": 0.10,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="any", weights={})

        assert "ensemble_confidence" in cypher
        assert "coalesce" in cypher
        assert "ensemble_conf" in cypher

    def test_ensembleconfidence_default_prop(self) -> None:
        """EnsembleConfidence uses default property name when not specified."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "ensemble_conf",
                    "computation": "ensembleconfidence",
                    "defaultwhennull": 0.5,
                    "weightkey": "wensemble",
                    "defaultweight": 0.1,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(match_direction="any", weights={})

        assert "ensemble_confidence" in cypher
        assert "0.5" in cypher

    def test_kge_scoring_dimensions_combined(self) -> None:
        """All 3 KGE scoring dimensions (kge, variantdiscovery, ensembleconfidence) work together."""
        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "kge_score",
                    "candidateprop": "kge_score",
                    "computation": "kge",
                    "defaultwhennull": 0.0,
                    "weightkey": "wkge",
                    "defaultweight": 0.40,
                },
                {
                    "name": "variant_score",
                    "candidateprop": "variant_discovery_score",
                    "computation": "variantdiscovery",
                    "defaultwhennull": 0.0,
                    "weightkey": "wvariant",
                    "defaultweight": 0.15,
                },
                {
                    "name": "ensemble_conf",
                    "candidateprop": "ensemble_confidence",
                    "computation": "ensembleconfidence",
                    "defaultwhennull": 0.5,
                    "weightkey": "wensemble",
                    "defaultweight": 0.10,
                },
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        cypher, _ = assembler.assemble_scoring_clause(
            match_direction="any",
            weights={"wkge": 0.5, "wvariant": 0.3, "wensemble": 0.2},
        )

        assert "kge_score" in cypher
        assert "variant_discovery_score" in cypher
        assert "ensemble_confidence" in cypher
        assert "0.5" in cypher
        assert "0.3" in cypher
        assert "0.2" in cypher

    def test_pareto_metadata_returned_when_enabled(self) -> None:
        """Pareto metadata is returned when pareto_candidates provided and enabled."""
        from unittest.mock import patch

        from engine.scoring.pareto import ParetoCandidate

        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "score1",
                    "candidateprop": "prop1",
                    "computation": "candidateproperty",
                    "weightkey": "w1",
                    "defaultweight": 1.0,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        candidates = [
            ParetoCandidate(candidate_id="c1", dimension_scores={"geo": 0.9, "price": 0.3}),
            ParetoCandidate(candidate_id="c2", dimension_scores={"geo": 0.3, "price": 0.9}),
            ParetoCandidate(candidate_id="c3", dimension_scores={"geo": 0.2, "price": 0.2}),
        ]

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.pareto_enabled = True

            _, pareto_meta = assembler.assemble_scoring_clause(
                match_direction="any",
                weights={},
                pareto_candidates=candidates,
            )

        assert pareto_meta is not None
        assert pareto_meta["front_size"] == 2
        assert pareto_meta["total_candidates"] == 3
        assert set(pareto_meta["non_dominated_ids"]) == {"c1", "c2"}

    def test_pareto_disabled_returns_none_metadata(self) -> None:
        """Pareto metadata is None when pareto_enabled=False."""
        from unittest.mock import patch

        from engine.scoring.pareto import ParetoCandidate

        domain_spec = make_mock_domain_spec(
            [
                {
                    "name": "score1",
                    "candidateprop": "prop1",
                    "computation": "candidateproperty",
                    "weightkey": "w1",
                    "defaultweight": 1.0,
                }
            ]
        )
        assembler = ScoringAssembler(domain_spec)

        candidates = [
            ParetoCandidate(candidate_id="c1", dimension_scores={"geo": 0.9}),
            ParetoCandidate(candidate_id="c2", dimension_scores={"geo": 0.3}),
        ]

        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.pareto_enabled = False

            _, pareto_meta = assembler.assemble_scoring_clause(
                match_direction="any",
                weights={},
                pareto_candidates=candidates,
            )

        assert pareto_meta is None
