"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [feedback]
tags: [feedback, drift-detection, chi-squared]
owner: engine-team
status: active
--- /L9_META ---

Match quality drift detector using chi-squared divergence.

Reference: Lippl et al. (2026) "Algorithmic Primitives and Compositional
Geometry of Reasoning in Language Models", Eq. 1-2.
The symmetric chi-squared distance between fingerprint frequency vectors measures
how much the matching behavior has shifted.
"""

from __future__ import annotations

from typing import Any

import structlog

from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver
from engine.utils.security import sanitize_label

logger = structlog.get_logger(__name__)


class DriftDetector:
    """
    Detects drift in match outcome distributions using chi-squared divergence.

    Compares the fingerprint distribution of recent outcomes (configurable
    window) against the historical baseline. Triggers alert when divergence
    exceeds threshold.
    """

    def __init__(self, graph_driver: GraphDriver, domain_spec: DomainSpec) -> None:
        self._driver = graph_driver
        self._spec = domain_spec
        self._db = domain_spec.domain.id

    @staticmethod
    def chi_squared_divergence(
        recent: dict[str, float],
        baseline: dict[str, float],
    ) -> float:
        """
        Symmetric chi-squared distance: chi(f,g) = sum (f_i - g_i)^2 / (f_i + g_i).

        Returns 0.0 when distributions are identical.
        Higher values indicate greater drift.
        """
        all_keys = set(recent) | set(baseline)
        divergence = 0.0
        for key in all_keys:
            f_i = recent.get(key, 0.0)
            g_i = baseline.get(key, 0.0)
            denom = f_i + g_i
            if denom > 0:
                divergence += (f_i - g_i) ** 2 / denom
        return divergence

    async def _query_dimension_frequency(
        self,
        outcome_label: str,
        window_days: int,
        recent: bool,
    ) -> dict[str, float]:
        """Query dimension frequency distribution for recent or baseline outcomes."""
        comparator = ">" if recent else "<="
        cypher = f"""
        MATCH (o:{outcome_label})
        WHERE o.tenant = $tenant
          AND o.created_at {comparator} datetime() - duration({{days: $window_days}})
        UNWIND o.active_dimensions AS dim
        WITH dim, count(*) AS cnt
        WITH collect({{dim: dim, cnt: cnt}}) AS dims, sum(cnt) AS total
        UNWIND dims AS d
        RETURN d.dim AS dimension, toFloat(d.cnt) / total AS frequency
        """
        results = await self._driver.execute_query(
            cypher,
            parameters={"tenant": self._db, "window_days": window_days},
            database=self._db,
        )
        return {r["dimension"]: r["frequency"] for r in results if r.get("dimension")}

    async def compute_drift(
        self,
        window_days: int = 30,
    ) -> dict[str, Any]:
        """
        Query recent vs historical outcome fingerprints, compute divergence.

        Returns metadata with divergence score and per-dimension breakdown.
        """
        outcome_label = sanitize_label(self._spec.feedbackloop.outcome_node_label)

        recent = await self._query_dimension_frequency(outcome_label, window_days, recent=True)
        baseline = await self._query_dimension_frequency(outcome_label, window_days, recent=False)

        if not recent and not baseline:
            return {
                "divergence": 0.0,
                "recent_dimensions": 0,
                "baseline_dimensions": 0,
                "status": "insufficient_data",
            }

        divergence = self.chi_squared_divergence(recent, baseline)

        # Per-dimension deltas
        all_dims = set(recent) | set(baseline)
        dimension_deltas = {dim: round(recent.get(dim, 0.0) - baseline.get(dim, 0.0), 6) for dim in all_dims}

        return {
            "divergence": round(divergence, 6),
            "recent_dimensions": len(recent),
            "baseline_dimensions": len(baseline),
            "dimension_deltas": dimension_deltas,
            "status": "computed",
        }

    async def check_and_alert(
        self,
        threshold: float = 0.15,
        window_days: int = 30,
    ) -> dict[str, Any]:
        """
        Run drift check. If divergence > threshold, log a warning.

        Returns drift metadata for inclusion in feedback loop response.
        """
        drift_data = await self.compute_drift(window_days=window_days)

        if drift_data["status"] == "insufficient_data":
            logger.info("drift_check_skipped", reason="insufficient_data", domain=self._db)
            return drift_data

        divergence = drift_data["divergence"]
        drift_data["threshold"] = threshold
        drift_data["alert"] = divergence > threshold

        if divergence > threshold:
            logger.warning(
                "drift_detected",
                divergence=divergence,
                threshold=threshold,
                window_days=window_days,
                domain=self._db,
            )
        else:
            logger.info(
                "drift_within_bounds",
                divergence=divergence,
                threshold=threshold,
                domain=self._db,
            )

        return drift_data
