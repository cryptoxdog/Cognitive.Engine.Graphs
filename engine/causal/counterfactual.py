"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [causal]
tags: [causal, counterfactual, scenario-generation]
owner: engine-team
status: active
--- /L9_META ---

Counterfactual scenario generation for negative outcomes.
Follows retrieval-then-reasoning: extract causal neighborhood,
compare with positive outcomes, generate intervention hypotheses.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from engine.config.schema import CounterfactualSpec
from engine.graph.driver import GraphDriver

logger = logging.getLogger(__name__)

_INTERVENTION_ADD_DIMENSION = "add_scoring_dimension"
_INTERVENTION_CHANGE_WEIGHT = "change_weight"
_INTERVENTION_ADD_GATE = "add_gate"


class CounterfactualGenerator:
    """Generates CounterfactualScenario nodes for negative outcomes.

    Strategy (inspired by ReasoningLM's subgraph reasoning):
    1. RETRIEVE: Extract the outcome's match fingerprint
    2. COMPARE: Find historical positive outcomes with similar configurations
    3. GENERATE: For each key difference, create a CounterfactualScenario node
    4. SCORE: Assign confidence based on how many winners share the factor
    """

    def __init__(
        self,
        counterfactual_spec: CounterfactualSpec,
        graph_driver: GraphDriver,
        domain_id: str,
    ) -> None:
        self._spec = counterfactual_spec
        self._graph_driver = graph_driver
        self._db = domain_id

    async def generate_for_outcome(
        self,
        outcome_node_id: str,
    ) -> list[dict[str, Any]]:
        """Generate counterfactual scenarios for a negative outcome.

        Args:
            outcome_node_id: The outcome_id of the negative TransactionOutcome.

        Returns:
            List of created CounterfactualScenario dicts.
        """
        fingerprint = await self._get_outcome_fingerprint(outcome_node_id)
        if not fingerprint:
            logger.info("No fingerprint found for outcome %s", outcome_node_id)
            return []

        positive_fingerprints = await self._find_similar_positives(fingerprint)
        if not positive_fingerprints:
            logger.info("No similar positive outcomes for comparison")
            return []

        scenarios = self._diff_fingerprints(
            actual_fingerprint=fingerprint,
            positive_fingerprints=positive_fingerprints,
            outcome_node_id=outcome_node_id,
        )

        if scenarios:
            await self._store_scenarios(scenarios)
            logger.info(
                "Generated %d counterfactual scenarios for outcome %s",
                len(scenarios),
                outcome_node_id,
            )

        return scenarios

    async def _get_outcome_fingerprint(self, outcome_node_id: str) -> dict[str, Any] | None:
        """Retrieve the match fingerprint from a TransactionOutcome node."""
        cypher = """
        MATCH (o:TransactionOutcome {outcome_id: $outcome_id})
        RETURN o.active_dimensions AS active_dimensions,
               o.dimension_weights AS dimension_weights,
               o.gates_passed AS gates_passed,
               o.match_direction AS match_direction,
               o.candidate_count AS candidate_count,
               o.outcome AS outcome
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"outcome_id": outcome_node_id},
            database=self._db,
        )
        if not results:
            return None
        row = results[0]
        return {
            "active_dimensions": row.get("active_dimensions") or [],
            "dimension_weights": row.get("dimension_weights") or {},
            "gates_passed": row.get("gates_passed") or [],
            "match_direction": row.get("match_direction"),
            "candidate_count": row.get("candidate_count", 0),
            "outcome": row.get("outcome"),
        }

    async def _find_similar_positives(self, fingerprint: dict[str, Any]) -> list[dict[str, Any]]:
        """Find positive outcomes with overlapping dimensions."""
        pool_size = self._spec.comparison_pool_size
        match_direction = fingerprint.get("match_direction")

        cypher = """
        MATCH (o:TransactionOutcome)
        WHERE o.outcome = 'success'
              AND o.active_dimensions IS NOT NULL
              AND o.match_direction = $match_direction
        RETURN o.active_dimensions AS active_dimensions,
               o.dimension_weights AS dimension_weights,
               o.gates_passed AS gates_passed,
               o.outcome_id AS outcome_id
        ORDER BY o.created_at DESC
        LIMIT $pool_size
        """
        results = await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"match_direction": match_direction, "pool_size": pool_size},
            database=self._db,
        )
        return [
            {
                "active_dimensions": r.get("active_dimensions") or [],
                "dimension_weights": r.get("dimension_weights") or {},
                "gates_passed": r.get("gates_passed") or [],
                "outcome_id": r.get("outcome_id"),
            }
            for r in results
        ]

    def _diff_fingerprints(
        self,
        actual_fingerprint: dict[str, Any],
        positive_fingerprints: list[dict[str, Any]],
        outcome_node_id: str,
    ) -> list[dict[str, Any]]:
        """Identify key differences between losing and winning configs."""
        actual_dims = set(actual_fingerprint.get("active_dimensions") or [])
        max_scenarios = self._spec.max_scenarios_per_outcome
        min_confidence = self._spec.min_confidence
        total_positives = len(positive_fingerprints)

        if total_positives == 0:
            return []

        # Count how many positive outcomes have each dimension
        dim_counts: dict[str, int] = {}
        for pf in positive_fingerprints:
            for dim in pf.get("active_dimensions") or []:
                dim_counts[dim] = dim_counts.get(dim, 0) + 1

        scenarios: list[dict[str, Any]] = []

        # Dimensions present in positives but missing from actual
        missing_dims = {dim: count for dim, count in dim_counts.items() if dim not in actual_dims}
        for dim, count in sorted(missing_dims.items(), key=lambda x: -x[1]):
            confidence = count / total_positives
            if confidence < min_confidence:
                continue
            scenarios.append(
                {
                    "scenario_id": f"cf_{uuid.uuid4().hex[:12]}",
                    "actual_outcome": outcome_node_id,
                    "counterfactual_outcome": "success",
                    "intervention_type": _INTERVENTION_ADD_DIMENSION,
                    "confidence": round(confidence, 4),
                    "key_difference": dim,
                }
            )
            if len(scenarios) >= max_scenarios:
                break

        # Weight differences for shared dimensions
        if len(scenarios) < max_scenarios:
            actual_weights = actual_fingerprint.get("dimension_weights") or {}
            for pf in positive_fingerprints:
                pw = pf.get("dimension_weights") or {}
                for dim in actual_dims:
                    if dim in pw and dim in actual_weights:
                        actual_w = actual_weights[dim]
                        positive_w = pw[dim]
                        if isinstance(actual_w, (int, float)) and isinstance(positive_w, (int, float)):
                            if positive_w > actual_w * 1.5:
                                confidence = dim_counts.get(dim, 0) / total_positives
                                if confidence >= min_confidence:
                                    scenarios.append(
                                        {
                                            "scenario_id": f"cf_{uuid.uuid4().hex[:12]}",
                                            "actual_outcome": outcome_node_id,
                                            "counterfactual_outcome": "success",
                                            "intervention_type": _INTERVENTION_CHANGE_WEIGHT,
                                            "confidence": round(confidence, 4),
                                            "key_difference": f"{dim}_weight_increase",
                                        }
                                    )
                    if len(scenarios) >= max_scenarios:
                        break
                if len(scenarios) >= max_scenarios:
                    break

        return scenarios[:max_scenarios]

    async def _store_scenarios(self, scenarios: list[dict[str, Any]]) -> None:
        """Persist CounterfactualScenario nodes in Neo4j."""
        cypher = """
        UNWIND $scenarios AS s
        CREATE (cs:CounterfactualScenario {
            scenario_id: s.scenario_id,
            actual_outcome: s.actual_outcome,
            counterfactual_outcome: s.counterfactual_outcome,
            intervention_type: s.intervention_type,
            confidence: s.confidence,
            key_difference: s.key_difference,
            domain_id: $domain_id,
            created_at: datetime()
        })
        """
        await self._graph_driver.execute_query(
            cypher=cypher,
            parameters={"scenarios": scenarios, "domain_id": self._db},
            database=self._db,
        )
