"""
Scoring assembler: dimensions → WITH clause.
Compiles scoring dimensions into Cypher WITH clause with weighted aggregation.
"""

import logging

from engine.config.schema import ComputationType, DomainSpec, ScoringDimensionSpec

logger = logging.getLogger(__name__)


class ScoringAssembler:
    """Assembles scoring dimensions into Cypher WITH clause."""

    def __init__(self, domain_spec: DomainSpec):
        self.domain_spec = domain_spec
        self.scoring_spec = domain_spec.scoring

    def assemble_scoring_clause(self, match_direction: str, weights: dict[str, float]) -> str:
        """
        Assemble WITH clause for scoring.

        Args:
            match_direction: Current match direction
            weights: Weight overrides from query

        Returns:
            Cypher WITH clause
        """
        dimension_exprs = []
        weight_exprs = []

        for dim in self.scoring_spec.dimensions:
            # Check direction applicability
            if dim.matchdirections and match_direction not in dim.matchdirections:
                continue

            # Get computation expression
            expr = self._compile_dimension(dim)
            dimension_exprs.append(f"{expr} AS {dim.name}")

            # Get weight
            weight = weights.get(dim.weightkey, dim.defaultweight)
            weight_exprs.append(f"({weight} * {dim.name})")

        # Combine dimensions
        all_exprs = ", ".join(dimension_exprs)

        # Compute final score (additive by default, multiplicative modifiers applied)
        score_expr = self._build_score_expression(weight_exprs)

        return f"WITH candidate, {all_exprs}, {score_expr} AS score"

    def _compile_dimension(self, dim: ScoringDimensionSpec) -> str:
        """Compile single scoring dimension."""
        if dim.computation == ComputationType.GEODECAY:
            return self._compile_geodecay(dim)
        elif dim.computation == ComputationType.LOGNORMALIZED:
            return self._compile_lognormalized(dim)
        elif dim.computation == ComputationType.COMMUNITYMATCH:
            return self._compile_communitymatch(dim)
        elif dim.computation == ComputationType.INVERSELINEAR:
            return self._compile_inverselinear(dim)
        elif dim.computation == ComputationType.CANDIDATEPROPERTY:
            return f"coalesce(candidate.{dim.candidateprop}, {dim.defaultwhennull})"
        elif dim.computation == ComputationType.CUSTOMCYPHER:
            return dim.expression
        else:
            logger.warning(f"Unknown computation type: {dim.computation}")
            return str(dim.defaultwhennull)

    def _compile_geodecay(self, dim: ScoringDimensionSpec) -> str:
        """Geodecay: 1 / (1 + distance / k)."""
        # Assumes candidateprop contains "lat,lon" or separate lat/lon props
        return "1.0 / (1.0 + point.distance(point({latitude: candidate.lat, longitude: candidate.lon}), point({latitude: $query.lat, longitude: $query.lon})) / 50000.0)"

    def _compile_lognormalized(self, dim: ScoringDimensionSpec) -> str:
        """Log-normalized: ln(1 + x) / ln(1 + max)."""
        max_val = dim.maxvalue or 1000.0
        return f"log(1 + coalesce(candidate.{dim.candidateprop}, 0)) / log(1 + {max_val})"

    def _compile_communitymatch(self, dim: ScoringDimensionSpec) -> str:
        """Community match: multiplicative bias when communities match."""
        bias = 1.5  # Default bias
        return f"CASE WHEN candidate.{dim.candidateprop} = $query.{dim.queryprop} THEN {bias} ELSE 1.0 END"

    def _compile_inverselinear(self, dim: ScoringDimensionSpec) -> str:
        """Inverse linear: lower is better."""
        min_val = dim.minvalue or 0.0
        max_val = dim.maxvalue or 100.0
        return f"1.0 - (coalesce(candidate.{dim.candidateprop}, {max_val}) - {min_val}) / ({max_val} - {min_val})"

    def _build_score_expression(self, weight_exprs: list[str]) -> str:
        """Build final score expression from weighted dimensions."""
        if not weight_exprs:
            return "0.0"
        return " + ".join(weight_exprs)
