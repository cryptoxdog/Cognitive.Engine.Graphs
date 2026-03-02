# engine/scoring/assembler.py
"""
Scoring assembler: dimensions -> WITH clause.
Compiles scoring dimensions into Cypher WITH clause with weighted aggregation.
"""

from __future__ import annotations

import logging
import re

from engine.config.schema import ComputationType, DomainSpec, ScoringDimensionSpec
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)

# Dangerous Cypher keywords that must be blocked in CUSTOMCYPHER expressions
_DANGEROUS_CYPHER_KEYWORDS = frozenset([
    "call",
    "create",
    "merge",
    "delete",
    "remove",
    "set",
    "match",
    "return",
    "with",
    "unwind",
    "foreach",
    "load",
    "using",
    "detach",
    "optional",
    "union",
    "apoc",
    "gds",
    "dbms",
])


def _validate_custom_expression(expression: str, dim_name: str) -> str:
    """
    Validate CUSTOMCYPHER expression for dangerous patterns.
    Raises ValueError if expression contains potentially dangerous Cypher keywords.
    """
    expr_lower = expression.lower()

    # Check for dangerous keywords as word boundaries
    for keyword in _DANGEROUS_CYPHER_KEYWORDS:
        keyword_re = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
        if keyword_re.search(expression):
            msg = f"Dimension '{dim_name}': CUSTOMCYPHER expression contains forbidden keyword '{keyword}'"
            raise ValueError(msg)

    # Block comment injection
    if "//" in expression or "/*" in expression:
        msg = f"Dimension '{dim_name}': CUSTOMCYPHER expression contains comment syntax"
        raise ValueError(msg)

    # Block shell/template injection patterns
    if "$$" in expression or "${" in expression:
        msg = f"Dimension '{dim_name}': CUSTOMCYPHER expression contains injection pattern"
        raise ValueError(msg)

    return expression


class ScoringAssembler:
    """Assembles scoring dimensions into Cypher WITH clause."""

    def __init__(self, domain_spec: DomainSpec) -> None:
        self.domain_spec = domain_spec
        self.scoring_spec = domain_spec.scoring

    def assemble_scoring_clause(
        self,
        match_direction: str,
        weights: dict[str, float],
    ) -> str:
        """Assemble WITH clause for scoring."""
        dimension_exprs: list[str] = []
        weight_exprs: list[str] = []

        for dim in self.scoring_spec.dimensions:
            if dim.matchdirections and match_direction not in dim.matchdirections:
                continue
            expr = self._compile_dimension(dim)
            dimension_exprs.append(f"{expr} AS {dim.name}")
            weight = weights.get(dim.weightkey, dim.defaultweight)
            weight_exprs.append(f"({weight} * {dim.name})")

        all_exprs = ", ".join(dimension_exprs)
        score_expr = self._build_score_expression(weight_exprs)

        if all_exprs:
            return f"WITH candidate, {all_exprs}, {score_expr} AS score"
        return f"WITH candidate, {score_expr} AS score"

    def _compile_dimension(self, dim: ScoringDimensionSpec) -> str:
        """Dispatch to computation-specific compiler."""
        dispatch = {
            ComputationType.GEODECAY: self._compile_geodecay,
            ComputationType.LOGNORMALIZED: self._compile_lognormalized,
            ComputationType.COMMUNITYMATCH: self._compile_communitymatch,
            ComputationType.INVERSELINEAR: self._compile_inverselinear,
            ComputationType.WEIGHTEDRATE: self._compile_weightedrate,
            ComputationType.PRICEALIGNMENT: self._compile_pricealignment,
            ComputationType.TEMPORALPROXIMITY: self._compile_temporalproximity,
            ComputationType.TRAVERSALALIAS: self._compile_traversalalias,
            ComputationType.KGE: self._compile_kge,
        }

        if dim.computation == ComputationType.CANDIDATEPROPERTY:
            return self._compile_candidateproperty(dim)
        if dim.computation == ComputationType.CUSTOMCYPHER:
            if not dim.expression:
                raise ValueError(f"Dimension '{dim.name}': customcypher requires 'expression'")
            return _validate_custom_expression(dim.expression, dim.name)

        compiler = dispatch.get(dim.computation)
        if compiler is None:
            logger.warning("Unknown computation type: %s", dim.computation)
            return str(dim.defaultwhennull)
        return compiler(dim)

    def _compile_geodecay(self, dim: ScoringDimensionSpec) -> str:
        k = dim.decayconstant or 50000.0
        lat_prop = sanitize_label(dim.candidateprop or "lat")
        return (
            f"1.0 / (1.0 + point.distance("
            f"point({{latitude: candidate.{lat_prop}, longitude: candidate.lon}}),"
            f" point({{latitude: $query.{lat_prop}, longitude: $query.lon}})"
            f") / {k})"
        )

    def _compile_lognormalized(self, dim: ScoringDimensionSpec) -> str:
        max_val = dim.maxvalue or 1000.0
        prop = sanitize_label(dim.candidateprop or "value")
        return f"log(1 + coalesce(candidate.{prop}, 0)) / log(1 + {max_val})"

    def _compile_communitymatch(self, dim: ScoringDimensionSpec) -> str:
        bias = dim.bias or 1.5
        cand_prop = sanitize_label(dim.candidateprop or "community")
        query_prop = sanitize_label(dim.queryprop or "community")
        return f"CASE WHEN candidate.{cand_prop} = $query.{query_prop} THEN {bias} ELSE 1.0 END"

    def _compile_inverselinear(self, dim: ScoringDimensionSpec) -> str:
        min_val = dim.minvalue or 0.0
        max_val = dim.maxvalue or 100.0
        prop = sanitize_label(dim.candidateprop or "value")
        return f"1.0 - (coalesce(candidate.{prop}, {max_val}) - {min_val}) / ({max_val} - {min_val})"

    def _compile_candidateproperty(self, dim: ScoringDimensionSpec) -> str:
        """C-06 FIX: defaultwhennull emitted as validated numeric literal."""
        default = float(dim.defaultwhennull)
        prop = sanitize_label(dim.candidateprop or "value")
        return f"coalesce(candidate.{prop}, {default})"

    def _compile_weightedrate(self, dim: ScoringDimensionSpec) -> str:
        rate_prop = sanitize_label(dim.candidateprop or "rate")
        confidence_prop = sanitize_label(dim.queryprop or "confidence")
        default = float(dim.defaultwhennull)
        return f"coalesce(candidate.{rate_prop}, {default}) * coalesce(candidate.{confidence_prop}, 1.0)"

    def _compile_pricealignment(self, dim: ScoringDimensionSpec) -> str:
        cand_prop = sanitize_label(dim.candidateprop or "price_per_unit")
        query_prop = sanitize_label(dim.queryprop or "target_price")
        max_spread = dim.maxvalue or 1.0
        default = float(dim.defaultwhennull)
        return (
            f"CASE WHEN $query.{query_prop} IS NULL THEN {default} "
            f"ELSE 1.0 - (abs(candidate.{cand_prop} - $query.{query_prop}) / {max_spread}) END"
        )

    def _compile_temporalproximity(self, dim: ScoringDimensionSpec) -> str:
        date_prop = sanitize_label(dim.candidateprop or "last_transaction_date")
        decay_constant = dim.maxvalue or 90.0
        default = float(dim.defaultwhennull)
        return (
            f"CASE WHEN candidate.{date_prop} IS NULL THEN {default} "
            f"ELSE exp(-1.0 * duration.inDays(candidate.{date_prop}, datetime()).days "
            f"/ {decay_constant}) END"
        )

    def _compile_traversalalias(self, dim: ScoringDimensionSpec) -> str:
        """Read a property from a traversal step alias."""
        if not dim.alias:
            raise ValueError(f"Dimension '{dim.name}': traversalalias requires 'alias' field")
        alias = sanitize_label(dim.alias)
        prop = sanitize_label(dim.candidateprop or "score")
        default = float(dim.defaultwhennull)
        return f"coalesce({alias}.{prop}, {default})"

    def _compile_kge(self, dim: ScoringDimensionSpec) -> str:
        """KGE embedding similarity score (CompoundE3D)."""
        default = float(dim.defaultwhennull)
        if dim.alias:
            alias = sanitize_label(dim.alias)
            prop = sanitize_label(dim.candidateprop or "kge_score")
            return f"coalesce({alias}.{prop}, {default})"
        if dim.candidateprop:
            prop = sanitize_label(dim.candidateprop)
            return f"coalesce(candidate.{prop}, {default})"
        raise ValueError(f"Dimension '{dim.name}': kge requires 'alias' or 'candidateprop'")

    def _build_score_expression(self, weight_exprs: list[str]) -> str:
        if not weight_exprs:
            return "0.0"
        return " + ".join(weight_exprs)
