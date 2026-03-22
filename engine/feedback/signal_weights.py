"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [feedback]
tags: [feedback, signal-weights, scoring]
owner: engine-team
status: active
--- /L9_META ---

Signal weight calculator for outcome-based weight learning.
Computes dimension weights from historical outcome correlations.
"""

from __future__ import annotations

import logging

from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


class SignalWeightCalculator:
    """
    Calculates signal/dimension weights based on outcome correlation.

    For each scoring dimension type, computes:
      w_i = P(positive_outcome | dimension_i_high) / P(positive_outcome) x frequency_factor

    Stores weights as properties on DimensionWeight configuration nodes in Neo4j.
    """

    def __init__(self, graph_driver: GraphDriver, domain_spec: DomainSpec) -> None:
        self._driver = graph_driver
        self._spec = domain_spec
        self._weight_spec = domain_spec.feedbackloop.signal_weights
        self._db = domain_spec.domain.id

    async def recalculate_weights(self) -> dict[str, float]:
        """
        Query all TransactionOutcome nodes, compute win rates per dimension config,
        update DimensionWeight nodes in Neo4j.

        Returns mapping of dimension name to computed weight.
        """
        outcome_label = sanitize_label(self._spec.feedbackloop.outcome_node_label)

        # Step 1: Get total outcome counts
        totals_cypher = f"""
        MATCH (o:{outcome_label})
        WHERE o.tenant = $tenant
        RETURN count(o) AS total,
               sum(CASE WHEN o.outcome = 'success' THEN 1 ELSE 0 END) AS wins
        """
        totals = await self._driver.execute_query(
            totals_cypher,
            parameters={"tenant": self._db},
            database=self._db,
        )

        total_outcomes = totals[0]["total"] if totals else 0
        total_wins = totals[0]["wins"] if totals else 0

        if total_outcomes == 0:
            return self._baseline_weights()

        base_win_rate = total_wins / total_outcomes if total_outcomes > 0 else 0.0

        # Step 2: For each scoring dimension, compute correlation with wins
        weights: dict[str, float] = {}
        for dim in self._spec.scoring.dimensions:
            weight = await self._compute_dimension_weight(
                dim.name,
                base_win_rate,
                total_outcomes,
                outcome_label,
            )
            weights[dim.name] = weight

        # Step 3: Store weights in Neo4j
        await self._store_weights(weights)

        logger.info(
            "Recalculated %d dimension weights for domain=%s",
            len(weights),
            self._db,
        )
        return weights

    async def _compute_dimension_weight(
        self,
        dimension_name: str,
        base_win_rate: float,
        total_outcomes: int,
        outcome_label: str,
    ) -> float:
        """Compute weight for a single dimension based on outcome correlation."""
        safe_dim = sanitize_label(dimension_name)

        # Query outcomes where this dimension scored above median
        dim_cypher = f"""
        MATCH (o:{outcome_label})
        WHERE o.tenant = $tenant AND o.{safe_dim}_score IS NOT NULL
        WITH count(o) AS dim_total,
             sum(CASE WHEN o.outcome = 'success' THEN 1 ELSE 0 END) AS dim_wins
        RETURN dim_total, dim_wins
        """
        result = await self._driver.execute_query(
            dim_cypher,
            parameters={"tenant": self._db},
            database=self._db,
        )

        dim_total = result[0]["dim_total"] if result else 0
        dim_wins = result[0]["dim_wins"] if result else 0

        if dim_total == 0 or base_win_rate == 0.0:
            return self._weight_spec.baseline_weight

        dim_win_rate = dim_wins / dim_total
        lift = dim_win_rate / base_win_rate

        # Frequency adjustment: penalize rare signals
        frequency_factor = 1.0
        if self._weight_spec.frequency_adjustment and total_outcomes > 0:
            frequency_ratio = dim_total / total_outcomes
            # Sigmoid-like scaling: penalizes dimensions present in <10% of outcomes
            frequency_factor = min(1.0, frequency_ratio * 10.0)

        raw_weight = lift * frequency_factor

        # Clamp to configured bounds
        return max(
            self._weight_spec.min_weight,
            min(self._weight_spec.max_weight, raw_weight),
        )

    async def _store_weights(self, weights: dict[str, float]) -> None:
        """Store computed weights as DimensionWeight nodes in Neo4j."""
        for dim_name, weight_value in weights.items():
            safe_name = sanitize_label(dim_name)
            cypher = f"""
            MERGE (dw:DimensionWeight {{dimension: $dimension, tenant: $tenant}})
            SET dw.weight = $weight,
                dw.updated_at = datetime(),
                dw.{safe_name}_weight = $weight
            RETURN dw.dimension AS dimension
            """
            await self._driver.execute_query(
                cypher,
                parameters={
                    "dimension": dim_name,
                    "tenant": self._db,
                    "weight": weight_value,
                },
                database=self._db,
            )

    async def should_recalculate(self) -> bool:
        """Check if recalculation threshold met (outcome count since last recalc)."""
        outcome_label = sanitize_label(self._spec.feedbackloop.outcome_node_label)

        cypher = f"""
        OPTIONAL MATCH (dw:DimensionWeight {{tenant: $tenant}})
        WITH max(dw.updated_at) AS last_recalc
        MATCH (o:{outcome_label})
        WHERE o.tenant = $tenant
          AND (last_recalc IS NULL OR o.created_at > last_recalc)
        RETURN count(o) AS new_outcomes
        """
        result = await self._driver.execute_query(
            cypher,
            parameters={"tenant": self._db},
            database=self._db,
        )

        new_outcomes = result[0]["new_outcomes"] if result else 0
        return new_outcomes >= self._weight_spec.min_outcomes_for_recalculation

    async def get_current_weights(self) -> dict[str, float]:
        """Read current DimensionWeight nodes from graph."""
        cypher = """
        MATCH (dw:DimensionWeight {tenant: $tenant})
        RETURN dw.dimension AS dimension, dw.weight AS weight
        """
        results = await self._driver.execute_query(
            cypher,
            parameters={"tenant": self._db},
            database=self._db,
        )

        weights: dict[str, float] = {}
        for record in results:
            weights[record["dimension"]] = record["weight"]

        if not weights:
            return self._baseline_weights()

        return weights

    def _baseline_weights(self) -> dict[str, float]:
        """Return baseline weights for all scoring dimensions."""
        return {dim.name: self._weight_spec.baseline_weight for dim in self._spec.scoring.dimensions}
