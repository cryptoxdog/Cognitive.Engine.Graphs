"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [scoring, assembler, cypher]
owner: engine-team
status: active
--- /L9_META ---

Scoring assembler: dimensions -> WITH clause.
Compiles scoring dimensions into Cypher WITH clause with weighted aggregation.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from engine.config.schema import ComputationType, DomainSpec, ScoringDimensionSpec
from engine.graph.driver import GraphDriver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)

# Dangerous Cypher keywords that must be blocked in CUSTOMCYPHER expressions
_DANGEROUS_CYPHER_KEYWORDS = (
    "detach",  # must be before "delete" so DETACH DELETE reports detach
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
    "optional",
    "union",
    "apoc",
    "gds",
    "dbms",
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

    def __init__(
        self,
        domain_spec: DomainSpec,
        graph_driver: GraphDriver | None = None,
    ) -> None:
        self.domain_spec = domain_spec
        self.scoring_spec = domain_spec.scoring
        self._last_active_dims: list[str] = []
        self._graph_driver = graph_driver
        self._learned_weights: dict[str, float] | None = None

    async def load_learned_weights(self) -> dict[str, float]:
        """Query DimensionWeight nodes from Neo4j for convergence loop.

        Returns a mapping of dimension_name -> learned weight adjustment factor.
        Falls back to empty dict if feedback loop is disabled or no weights exist.
        """
        if not self._graph_driver:
            return {}

        fl_spec = self.domain_spec.feedbackloop
        if not fl_spec.enabled or not fl_spec.signal_weights.enabled:
            return {}

        domain_id = self.domain_spec.domain.id
        dim_names = [dim.name for dim in self.scoring_spec.dimensions]
        if not dim_names:
            return {}

        cypher = """
        MATCH (dw:DimensionWeight)
        WHERE dw.dimension_name IN $names AND dw.domain_id = $domain_id
        RETURN dw.dimension_name AS name, dw.weight AS weight
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"names": dim_names, "domain_id": domain_id},
            database=domain_id,
        )
        self._learned_weights = {r["name"]: r["weight"] for r in results if r.get("name") and r.get("weight")}
        logger.info(
            "Loaded %d learned dimension weights for domain %s",
            len(self._learned_weights),
            domain_id,
        )
        return self._learned_weights

    def assemble_scoring_clause(
        self,
        match_direction: str,
        weights: dict[str, float],
        pareto_candidates: list[Any] | None = None,
    ) -> tuple[str, dict[str, Any] | None]:
        """Assemble WITH clause for scoring.

        Args:
            match_direction: Direction for dimension filtering.
            weights: Weight overrides keyed by weightkey.
            pareto_candidates: Optional list of ParetoCandidate for pre-filtering.

        Returns:
            Tuple of (cypher_clause, pareto_metadata).
            pareto_metadata is None if Pareto disabled or not applicable,
            otherwise contains front_size, total_candidates, non_dominated_ids.
        """
        from engine.config.settings import settings

        pareto_metadata: dict[str, Any] | None = None

        # Pareto pre-filter (lazy import to avoid circular deps)
        if settings.pareto_enabled and pareto_candidates is not None and len(pareto_candidates) > 1:
            from engine.scoring.pareto import compute_pareto_front

            front = compute_pareto_front(pareto_candidates)
            logger.info(
                "Pareto pre-filter: %d/%d candidates non-dominated",
                front.front_size,
                len(pareto_candidates),
            )
            pareto_metadata = {
                "front_size": front.front_size,
                "total_candidates": len(pareto_candidates),
                "non_dominated_ids": [c.candidate_id for c in front.non_dominated],
                "dimension_names": front.dimension_names,
            }

        dimension_exprs: list[str] = []
        weight_exprs: list[str] = []
        active_dim_names: list[str] = []

        learned = self._learned_weights or {}

        for dim in self.scoring_spec.dimensions:
            if dim.matchdirections and match_direction not in dim.matchdirections:
                continue
            expr = self._compile_dimension(dim)
            # W1-02: clamp each dimension expression to [0.0, 1.0] when enabled
            if settings.score_clamp_enabled:
                expr = self._clamp_expression(expr)
            dimension_exprs.append(f"{expr} AS {dim.name}")
            weight = weights.get(dim.weightkey, dim.defaultweight)
            # Convergence loop: multiply spec weight by learned adjustment factor
            if dim.name in learned:
                weight = weight * learned[dim.name]
            weight_exprs.append(f"({weight} * {dim.name})")
            active_dim_names.append(dim.name)

        self._last_active_dims = list(active_dim_names)
        all_exprs = ", ".join(dimension_exprs)
        score_expr = self._build_score_expression(weight_exprs)

        if all_exprs:
            dim_names_passthrough = ", ".join(active_dim_names)
            clause = f"WITH candidate, {all_exprs}\nWITH candidate, {dim_names_passthrough}, {score_expr} AS score"
        else:
            clause = f"WITH candidate, {score_expr} AS score"

        return clause, pareto_metadata

    @property
    def last_active_dimension_names(self) -> list[str]:
        """Return dimension names from the most recent assemble_scoring_clause call."""
        return list(self._last_active_dims)

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
            ComputationType.PREFERENCEATTENTION: self._compile_preference_attention,
            ComputationType.COMMUNITYBRIDGE: self._compile_community_bridge,
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
        query_lat_param = sanitize_label(dim.queryprop or lat_prop)
        return (
            f"1.0 / (1.0 + point.distance("
            f"point({{latitude: candidate.{lat_prop}, longitude: candidate.lon}}),"
            f" point({{latitude: ${query_lat_param}, longitude: $lon}})"
            f") / {k})"
        )

    def _compile_lognormalized(self, dim: ScoringDimensionSpec) -> str:
        max_val = dim.maxvalue or 1000.0
        prop = sanitize_label(dim.candidateprop or "value")
        return f"log(1 + coalesce(candidate.{prop}, 0)) / log(1 + {max_val})"

    def _compile_communitymatch(self, dim: ScoringDimensionSpec) -> str:
        """Community match scoring using simple equality check.

        Returns bias score if communities match, reduced score otherwise.
        Does not require APOC - uses native Cypher only.
        """
        bias = dim.bias or 1.5
        cand_prop = sanitize_label(dim.candidateprop or "community_id")
        query_prop = sanitize_label(dim.queryprop or "community_id")
        return (
            f"CASE "
            f"  WHEN candidate.{cand_prop} IS NULL OR ${query_prop} IS NULL THEN 0.5 "
            f"  WHEN candidate.{cand_prop} = ${query_prop} THEN {bias} "
            f"  ELSE 0.2 "
            f"END"
        )

    def _compile_inverselinear(self, dim: ScoringDimensionSpec) -> str:
        min_val = dim.minvalue or 0.0
        max_val = dim.maxvalue or 100.0
        prop = sanitize_label(dim.candidateprop or "value")
        return f"1.0 - (coalesce(candidate.{prop}, {max_val}) - {min_val}) / ({max_val} - {min_val})"

    def _compile_candidateproperty(self, dim: ScoringDimensionSpec) -> str:
        """C-06 FIX: defaultwhennull emitted as validated numeric literal."""
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
        prop = sanitize_label(dim.candidateprop or "value")
        return f"coalesce(candidate.{prop}, {default})"

    def _compile_weightedrate(self, dim: ScoringDimensionSpec) -> str:
        rate_prop = sanitize_label(dim.candidateprop or "rate")
        confidence_prop = sanitize_label(dim.queryprop or "confidence")
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
        return f"coalesce(candidate.{rate_prop}, {default}) * coalesce(candidate.{confidence_prop}, 1.0)"

    def _compile_pricealignment(self, dim: ScoringDimensionSpec) -> str:
        """Log-ratio distance preferred over linear for multi-order-of-magnitude pricing.

        Formula: 1 - |log(candidate_p / target_p)| / tau
        Handles SaaS $10/mo to $10k/mo ranges appropriately.
        """
        cand_prop = sanitize_label(dim.candidateprop or "price_per_unit")
        query_prop = sanitize_label(dim.queryprop or "target_price")
        tau = dim.maxvalue or 2.0  # tolerance: 2.0 = ~7.4x ratio scores 0
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
        return (
            f"CASE "
            f"  WHEN ${query_prop} IS NULL OR ${query_prop} <= 0 THEN {default} "
            f"  WHEN candidate.{cand_prop} IS NULL OR candidate.{cand_prop} <= 0 THEN {default} "
            f"  ELSE toFloat(1.0 - abs(log(candidate.{cand_prop} / ${query_prop})) / {tau}) "
            f"END"
        )

    def _compile_temporalproximity(self, dim: ScoringDimensionSpec) -> str:
        """Multi-signal temporal scoring.

        score = w1 * recency_decay + w2 * touch_frequency + w3 * acceleration_flag

        Reads last_activity_date, touch_count_30d, and is_accelerating from node.
        """
        date_prop = sanitize_label(dim.candidateprop or "last_activity_date")
        decay_days = dim.maxvalue or 90.0
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
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
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
        return f"coalesce({alias}.{prop}, {default})"

    def _compile_kge(self, dim: ScoringDimensionSpec) -> str:
        """KGE embedding similarity score (CompoundE3D)."""
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
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
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
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
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
        prop = sanitize_label(dim.candidateprop or "ensemble_confidence")
        if dim.alias:
            alias = sanitize_label(dim.alias)
            return f"coalesce({alias}.{prop}, {default})"
        return f"coalesce(candidate.{prop}, {default})"

    def _compile_preference_attention(self, dim: ScoringDimensionSpec) -> str:
        """Preference-attention scoring inspired by HGKR knowledge-perceiving filter.

        Traverses from query_entity through configurable outcome relationship,
        finds successful outcomes, samples top-K by recency, computes
        community-overlap between candidate and each outcome, and returns
        normalized weighted score.

        Properties from domain spec YAML (via dim.metadata or defaults):
        - outcome_relation (default: "RESULTED_IN")
        - outcome_node (default: "TransactionOutcome")
        - success_property (default: "outcome_type")
        - success_value (default: "closed_won")

        Ref: Liu et al., Scientific Reports (2023) 13:6987, §3.2 preference attention.
        """
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except
        sample_k = self.scoring_spec.preference_sample_size if hasattr(self.scoring_spec, "preference_sample_size") else 28

        # Configurable properties with safe defaults
        metadata = dim.metadata if hasattr(dim, "metadata") and dim.metadata else {}
        outcome_rel = sanitize_label(metadata.get("outcome_relation", "RESULTED_IN"))
        outcome_node = sanitize_label(metadata.get("outcome_node", "TransactionOutcome"))
        success_prop = sanitize_label(metadata.get("success_property", "outcome_type"))
        success_value = sanitize_label(metadata.get("success_value", "closed_won"))

        cand_community_prop = sanitize_label(dim.candidateprop or "community_id")

        return (
            f"CASE "
            f"  WHEN size([(qe)-[:{outcome_rel}]->(o:{outcome_node}) "
            f"    WHERE o.{success_prop} = '{success_value}' | o]) = 0 THEN {default} "
            f"  ELSE toFloat("
            f"    size([(qe)-[:{outcome_rel}]->(o:{outcome_node}) "
            f"      WHERE o.{success_prop} = '{success_value}' "
            f"      AND o.community_id = candidate.{cand_community_prop} | o][0..{sample_k}])"
            f"  ) / toFloat("
            f"    size([(qe)-[:{outcome_rel}]->(o:{outcome_node}) "
            f"      WHERE o.{success_prop} = '{success_value}' | o][0..{sample_k}])"
            f"  ) "
            f"END"
        )

    def _compile_community_bridge(self, dim: ScoringDimensionSpec) -> str:
        """Multi-community bridge scoring for cross-graph overlap.

        Reads multiple community_id properties (from different per-relation
        Louvain runs), counts how many match between candidate and query_entity,
        and returns score = matching / total community properties.

        NULL-safe: NULL community values treated as non-match.

        Properties from domain spec YAML (via dim.metadata or defaults):
        - community_properties: list[str] (e.g., ["community_id_supply", "community_id_geo"])

        Ref: Liu et al., Scientific Reports (2023) 13:6987, §3.3 cross-graph propagation.
        """
        default = float(dim.defaultwhennull)  # nosemgrep: float-requires-try-except

        # Extract community properties from metadata or use sensible defaults
        metadata = dim.metadata if hasattr(dim, "metadata") and dim.metadata else {}
        community_props = metadata.get("community_properties", [])
        if not community_props:
            # Fall back to candidateprop if set, else default single community_id
            if dim.candidateprop:
                community_props = [dim.candidateprop]
            else:
                community_props = ["community_id"]

        # Build CASE expressions for each community property
        match_cases = []
        for prop in community_props:
            safe_prop = sanitize_label(prop)
            match_cases.append(
                f"CASE "
                f"WHEN candidate.{safe_prop} IS NOT NULL "
                f"AND $query_{safe_prop} IS NOT NULL "
                f"AND candidate.{safe_prop} = $query_{safe_prop} "
                f"THEN 1 ELSE 0 END"
            )

        total = len(community_props)
        if total == 0:
            return str(default)

        sum_expr = " + ".join(match_cases)
        return f"CASE WHEN {total} = 0 THEN {default} ELSE toFloat({sum_expr}) / {total}.0 END"

    @staticmethod
    def _clamp_expression(expr: str) -> str:
        """W1-02: Wrap a Cypher expression in a CASE-based clamp to [0.0, 1.0].

        Prevents unbounded scores from propagating through the scoring pipeline.
        Mirrors seL4's invariant enforcement on all capability-transfer outputs.
        """
        return f"CASE WHEN ({expr}) < 0.0 THEN 0.0 WHEN ({expr}) > 1.0 THEN 1.0 ELSE ({expr}) END"

    def _build_score_expression(self, weight_exprs: list[str]) -> str:
        if not weight_exprs:
            return "0.0"
        return " + ".join(weight_exprs)
