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
_DANGEROUS_CYPHER_KEYWORDS = frozenset(
    [
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
    ]
)


def _validate_custom_expression(expression: str, dim_name: str) -> str:
    """
    Validate CUSTOMCYPHER expression for dangerous patterns.
    Raises ValueError if expression contains potentially dangerous Cypher keywords.
    """
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
            ComputationType.VARIANTDISCOVERY: self._compile_variantdiscovery,
            ComputationType.ENSEMBLECONFIDENCE: self._compile_ensembleconfidence,
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
        """Soft community match using lift-weighted Jaccard similarity.

        Replaces binary CASE WHEN with continuous overlap score.
        Requires candidate nodes to carry community_ids (list) and lift property.
        """
        bias = dim.bias or 1.5
        cand_prop = sanitize_label(dim.candidateprop or "community_ids")
        query_prop = sanitize_label(dim.queryprop or "community_ids")
        return (
            f"CASE "
            f"  WHEN candidate.{cand_prop} IS NULL OR $query.{query_prop} IS NULL THEN 0.5 "
            f"  WHEN apoc.coll.intersection(candidate.{cand_prop}, $query.{query_prop}) = [] THEN 0.0 "
            f"  ELSE toFloat(size(apoc.coll.intersection(candidate.{cand_prop}, $query.{query_prop}))) "
            f"       / toFloat(size(apoc.coll.union(candidate.{cand_prop}, $query.{query_prop}))) "
            f"       * coalesce(candidate.community_lift, {bias}) "
            f"END"
        )

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
        """Log-ratio distance preferred over linear for multi-order-of-magnitude pricing.

        Formula: 1 - |log(candidate_p / target_p)| / tau
        Handles SaaS $10/mo to $10k/mo ranges appropriately.
        """
        cand_prop = sanitize_label(dim.candidateprop or "price_per_unit")
        query_prop = sanitize_label(dim.queryprop or "target_price")
        tau = dim.maxvalue or 2.0  # tolerance: 2.0 = ~7.4x ratio scores 0
        default = float(dim.defaultwhennull)
        return (
            f"CASE "
            f"  WHEN $query.{query_prop} IS NULL OR $query.{query_prop} <= 0 THEN {default} "
            f"  WHEN candidate.{cand_prop} IS NULL OR candidate.{cand_prop} <= 0 THEN {default} "
            f"  ELSE toFloat(1.0 - abs(log(candidate.{cand_prop} / $query.{query_prop})) / {tau}) "
            f"END"
        )

    def _compile_temporalproximity(self, dim: ScoringDimensionSpec) -> str:
        """Multi-signal temporal scoring.

        score = w1 * recency_decay + w2 * touch_frequency + w3 * acceleration_flag

        Reads last_activity_date, touch_count_30d, and is_accelerating from node.
        """
        date_prop = sanitize_label(dim.candidateprop or "last_activity_date")
        decay_days = dim.maxvalue or 90.0
        default = float(dim.defaultwhennull)
        # Weights for 3 signals
        w1, w2, w3 = 0.6, 0.25, 0.15
        return (
            f"CASE WHEN candidate.{date_prop} IS NULL THEN {default} "
            f"ELSE ("
            f"  {w1} * exp(-1.0 * duration.inDays(candidate.{date_prop}, datetime()).days / {decay_days})"
            f"  + {w2} * toFloat(coalesce(candidate.touch_count_30d, 0)) / 30.0"
            f"  + {w3} * toFloat(coalesce(candidate.is_accelerating, 0))"
            f") END"
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

    def _compile_variantdiscovery(self, dim: ScoringDimensionSpec) -> str:
        """Variant discovery score from BeamSearchEngine.

        Reads pre-computed variant_discovery_score from candidate node.
        This score represents novel scoring dimensions discovered autonomously
        through beam search over CompoundE3D geometric space.

        The score is written to Neo4j by BeamSearchEngine.search() and
        consumed here during match scoring.

        Ref: engine/kge/beam_search.py, Deep Research Directive §8
        """
        default = float(dim.defaultwhennull)
        prop = sanitize_label(dim.candidateprop or "variant_discovery_score")
        if dim.alias:
            alias = sanitize_label(dim.alias)
            return f"coalesce({alias}.{prop}, {default})"
        return f"coalesce(candidate.{prop}, {default})"

    def _compile_ensembleconfidence(self, dim: ScoringDimensionSpec) -> str:
        """Ensemble confidence from multi-variant fusion.

        Reads pre-computed ensemble_confidence from candidate node.
        This score indicates inference robustness from WDS, Borda count,
        or Mixture-of-Experts ensemble fusion.

        Higher confidence = more agreement across KGE variants.
        Lower confidence = divergent predictions (higher uncertainty).

        The score is written to Neo4j by EnsembleController.predict() and
        consumed here during match scoring.

        Ref: engine/kge/ensemble.py, Deep Research Directive §9
        """
        default = float(dim.defaultwhennull)
        prop = sanitize_label(dim.candidateprop or "ensemble_confidence")
        if dim.alias:
            alias = sanitize_label(dim.alias)
            return f"coalesce({alias}.{prop}, {default})"
        return f"coalesce(candidate.{prop}, {default})"

    def _build_score_expression(self, weight_exprs: list[str]) -> str:
        if not weight_exprs:
            return "0.0"
        return " + ".join(weight_exprs)
