"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [feedback]
tags: [feedback, convergence-loop, orchestrator]
owner: engine-team
status: active
--- /L9_META ---

Convergence loop orchestrator for the outcome feedback cycle.
Coordinates signal weight recalculation, pattern matching, score propagation,
and drift detection.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.config.schema import DomainSpec
from engine.feedback.drift_detector import DriftDetector
from engine.feedback.pattern_matcher import ConfigurationMatcher
from engine.feedback.score_propagator import ScorePropagator
from engine.feedback.signal_weights import SignalWeightCalculator
from engine.graph.driver import GraphDriver

logger = logging.getLogger(__name__)


class ConvergenceLoop:
    """
    Orchestrates the full feedback cycle:

    1. Outcome recorded (via handle_outcomes -- already exists)
    2. Pattern matching: find similar historical outcomes
    3. Signal weight update: recalculate if threshold met
    4. Score propagation: boost/penalize active candidate scores
    5. Drift detection: chi-squared divergence check

    This is called from handle_outcomes after the TransactionOutcome
    node is written to Neo4j.
    """

    def __init__(
        self,
        graph_driver: GraphDriver,
        domain_spec: DomainSpec,
    ) -> None:
        self._driver = graph_driver
        self._spec = domain_spec
        self._weight_calculator = SignalWeightCalculator(graph_driver, domain_spec)
        self._pattern_matcher = ConfigurationMatcher(graph_driver, domain_spec)
        self._score_propagator = ScorePropagator(graph_driver, domain_spec)
        self._drift_detector = DriftDetector(graph_driver, domain_spec)
        self._feedback_spec = domain_spec.feedbackloop

    async def on_outcome_recorded(
        self,
        outcome_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Called after handle_outcomes writes the TransactionOutcome node.
        Executes the convergence cycle.
        Returns feedback metadata for the response envelope.
        """
        if not self._feedback_spec.enabled:
            return {"feedback_loop": "disabled"}

        metadata: dict[str, Any] = {"feedback_loop": "enabled"}

        # Step 1: Propagate score adjustments
        propagation = await self._score_propagator.propagate_outcome(
            outcome_data,
            boost_factor=self._feedback_spec.propagation_boost_factor,
        )
        metadata["propagation"] = propagation

        # Step 2: Check if weight recalculation needed
        if await self._weight_calculator.should_recalculate():
            weights = await self._weight_calculator.recalculate_weights()
            metadata["weights_recalculated"] = True
            metadata["new_weights"] = weights
        else:
            metadata["weights_recalculated"] = False

        # Step 3: Drift detection (chi-squared divergence)
        drift_data = await self._drift_detector.check_and_alert(
            threshold=self._feedback_spec.drift_threshold,
            window_days=self._feedback_spec.drift_window_days,
        )
        metadata["drift"] = drift_data

        logger.info(
            "Feedback loop completed for domain=%s outcome=%s",
            self._spec.domain.id,
            outcome_data.get("outcome"),
        )
        return metadata
