"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [scoring, feedback, outcome, wave2]
owner: engine-team
status: active
--- /L9_META ---

Outcome feedback loop for weight tuning proposals.

Reads outcome data (positive/negative/neutral) from Neo4j, computes
per-dimension discriminability, and proposes weight adjustments. Does NOT
auto-apply — returns proposals for human-in-the-loop approval.

seL4 analog: the feedback mechanism closes the refinement loop — the
abstract target (calibration spec) constrains where the concrete weights
are allowed to move.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Maximum weight nudge per feedback cycle
WEIGHT_NUDGE = 0.02
# Minimum outcomes required for meaningful analysis
MIN_OUTCOMES = 10


class OutcomeFeedback:
    """Compute weight adjustment proposals from outcome feedback data.

    This class processes outcome records and produces per-dimension
    discriminability analysis and weight adjustment proposals. The
    proposals are advisory — they must be explicitly applied via the
    apply_weight_proposal admin subaction.
    """

    def __init__(self, outcomes: list[dict[str, Any]]) -> None:
        self.outcomes = outcomes

    def compute_feedback(self) -> dict[str, Any]:
        """Analyze outcomes and propose weight adjustments.

        Returns dict with:
            - sample_count: number of outcomes analyzed
            - sufficient_data: whether we have enough outcomes
            - dimension_analysis: per-dimension discriminability
            - proposed_weights: dict of dimension -> proposed weight delta
        """
        if len(self.outcomes) < MIN_OUTCOMES:
            return {
                "sample_count": len(self.outcomes),
                "sufficient_data": False,
                "dimension_analysis": {},
                "proposed_weights": {},
                "message": f"Insufficient outcomes ({len(self.outcomes)} < {MIN_OUTCOMES}). Collect more data.",
            }

        # Partition scores by outcome type
        positive_dims: dict[str, list[float]] = defaultdict(list)
        negative_dims: dict[str, list[float]] = defaultdict(list)

        for outcome in self.outcomes:
            if not isinstance(outcome, dict):
                continue  # type: ignore[unreachable]
            outcome_type = outcome.get("outcome")
            dim_scores = outcome.get("dimension_scores", {})
            if not isinstance(dim_scores, dict):
                continue

            for dim, score in dim_scores.items():
                if not isinstance(score, (int, float)):
                    continue
                if outcome_type == "positive":
                    positive_dims[dim].append(float(score))
                elif outcome_type == "negative":
                    negative_dims[dim].append(float(score))

        all_dims = set(positive_dims.keys()) | set(negative_dims.keys())
        dimension_analysis: dict[str, dict[str, Any]] = {}
        proposed_weights: dict[str, float] = {}

        for dim in sorted(all_dims):
            pos_scores = positive_dims.get(dim, [])
            neg_scores = negative_dims.get(dim, [])
            pos_mean = statistics.mean(pos_scores) if pos_scores else 0.0
            neg_mean = statistics.mean(neg_scores) if neg_scores else 0.0
            discriminability = pos_mean - neg_mean

            # Nudge proportional to discriminability, capped at WEIGHT_NUDGE
            nudge = max(-WEIGHT_NUDGE, min(WEIGHT_NUDGE, WEIGHT_NUDGE * discriminability))
            proposed_weights[dim] = round(nudge, 6)

            dimension_analysis[dim] = {
                "positive_mean": round(pos_mean, 6),
                "negative_mean": round(neg_mean, 6),
                "discriminability": round(discriminability, 6),
                "positive_count": len(pos_scores),
                "negative_count": len(neg_scores),
                "proposed_nudge": round(nudge, 6),
            }

        return {
            "sample_count": len(self.outcomes),
            "sufficient_data": True,
            "dimension_analysis": dimension_analysis,
            "proposed_weights": proposed_weights,
        }

    @staticmethod
    def apply_weights(
        current_weights: dict[str, float],
        proposed_deltas: dict[str, float],
    ) -> dict[str, float]:
        """Apply proposed weight deltas to current weights.

        Clamps each resulting weight to [0.0, 1.0].

        Args:
            current_weights: Current weight set (dimension -> weight).
            proposed_deltas: Proposed nudges (dimension -> delta).

        Returns:
            New weight dict with deltas applied and clamped.
        """
        result: dict[str, float] = {}
        for dim, current in current_weights.items():
            delta = proposed_deltas.get(dim, 0.0)
            result[dim] = round(max(0.0, min(1.0, current + delta)), 6)
        return result
