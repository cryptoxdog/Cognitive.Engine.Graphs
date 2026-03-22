"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [causal]
tags: [causal, attribution, multi-touch]
owner: engine-team
status: active
--- /L9_META ---

Multi-touch attribution calculator for outcome causation.
Traces backward through causal edges to identify and weight contributing factors.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)

# Valid attribution model names
VALID_MODELS = frozenset({"first_touch", "last_touch", "linear", "position_based"})


class AttributionCalculator:
    """
    Multi-touch attribution for outcome causation.

    Given an outcome (TransactionOutcome), traces backward through
    causal edges to identify and weight contributing factors.
    Supports: first_touch, last_touch, linear, position_based attribution models.
    """

    def __init__(self, graph_driver: GraphDriver, domain_spec: DomainSpec) -> None:
        self._driver = graph_driver
        self._spec = domain_spec
        self._db = domain_spec.domain.id

    async def compute_attribution(
        self,
        outcome_node_id: str,
        model: str = "linear",
        max_depth: int | None = None,
    ) -> dict[str, Any]:
        """
        Trace causal chain from outcome backward, assign attribution weights.
        Returns {touchpoint_id: weight} mapping and metadata.
        """
        if model not in VALID_MODELS:
            msg = f"Invalid attribution model: {model!r}. Must be one of {sorted(VALID_MODELS)}"
            raise ValueError(msg)

        depth = max_depth or self._spec.causal.chain_depth_limit
        outcome_label = sanitize_label(self._spec.feedbackloop.outcome_node_label)

        # Build edge pattern from causal spec
        edge_types = [sanitize_label(e.edge_type) for e in self._spec.causal.causal_edges]
        if edge_types:
            edge_pattern = "|".join(edge_types)
            rel_pattern = f"[:{edge_pattern}*1..{depth}]"
        else:
            rel_pattern = f"[*1..{depth}]"

        # Trace backward from outcome to find contributing touchpoints
        cypher = (
            f"MATCH (outcome:{outcome_label} {{outcome_id: $outcome_id}})\n"
            f"MATCH path = (touchpoint)-{rel_pattern}->(outcome)\n"
            f"RETURN touchpoint.entity_id AS touchpoint_id,\n"
            f"       length(path) AS distance,\n"
            f"       [r IN relationships(path) | r.confidence] AS confidences\n"
            f"ORDER BY distance ASC"
        )

        results = await self._driver.execute_query(
            cypher,
            parameters={"outcome_id": outcome_node_id},
            database=self._db,
        )

        if not results:
            return {"touchpoints": {}, "model": model, "chain_depth": 0}

        touchpoints = self._assign_weights(results, model)

        return {
            "touchpoints": touchpoints,
            "model": model,
            "chain_depth": max((r["distance"] for r in results), default=0),
            "total_touchpoints": len(touchpoints),
        }

    @staticmethod
    def _assign_weights(
        results: list[dict[str, Any]],
        model: str,
    ) -> dict[str, float]:
        """Assign attribution weights based on the selected model."""
        touchpoint_ids = [r["touchpoint_id"] for r in results if r["touchpoint_id"]]
        n = len(touchpoint_ids)

        if n == 0:
            return {}

        weights: dict[str, float] = {}

        if model == "first_touch":
            # All credit to the first touchpoint
            weights[touchpoint_ids[0]] = 1.0
            for tp_id in touchpoint_ids[1:]:
                weights[tp_id] = 0.0

        elif model == "last_touch":
            # All credit to the last touchpoint
            for tp_id in touchpoint_ids[:-1]:
                weights[tp_id] = 0.0
            weights[touchpoint_ids[-1]] = 1.0

        elif model == "linear":
            # Equal credit to all touchpoints
            equal_weight = 1.0 / n
            for tp_id in touchpoint_ids:
                weights[tp_id] = round(equal_weight, 6)

        elif model == "position_based":
            # 40% first, 40% last, 20% distributed among middle
            if n == 1:
                weights[touchpoint_ids[0]] = 1.0
            elif n == 2:
                weights[touchpoint_ids[0]] = 0.5
                weights[touchpoint_ids[1]] = 0.5
            else:
                weights[touchpoint_ids[0]] = 0.4
                weights[touchpoint_ids[-1]] = 0.4
                middle_weight = 0.2 / (n - 2)
                for tp_id in touchpoint_ids[1:-1]:
                    weights[tp_id] = round(middle_weight, 6)

        return weights
