"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [scoring, weights, dual-dimensions]
owner: engine-team
status: active
--- /L9_META ---

Pool-aware weight redistribution and EMA feedback for dual dimension classes.
Engineered dimensions use slow EMA; learned (PRIMITIVE) dimensions use fast EMA.
"""

from __future__ import annotations

import logging

from engine.config.schema import ComputationType, ScoringDimensionSpec
from engine.config.settings import settings

logger = logging.getLogger(__name__)


def _is_learned(dim: ScoringDimensionSpec) -> bool:
    """Return True if dimension uses a learned (PRIMITIVE) computation type."""
    return dim.computation == ComputationType.PRIMITIVE


def redistribute_weights(
    dimensions: list[ScoringDimensionSpec],
    weights: dict[str, float],
    *,
    engineered_budget: float | None = None,
    learned_budget: float | None = None,
) -> dict[str, float]:
    """Redistribute weights so each pool sums to its budget.

    Within each pool (engineered / learned), individual dimension weights
    are proportionally rescaled so the pool total equals the budget.

    When learned_budget is 0.0, all PRIMITIVE dimensions get weight 0.0
    and engineered dimensions rescale to fill engineered_budget.
    """
    eng_budget = engineered_budget if engineered_budget is not None else settings.engineered_weight_budget
    lrn_budget = learned_budget if learned_budget is not None else settings.learned_weight_budget

    engineered = [d for d in dimensions if not _is_learned(d)]
    learned = [d for d in dimensions if _is_learned(d)]

    result: dict[str, float] = {}

    # Engineered pool
    eng_total = sum(weights.get(d.weightkey, d.defaultweight) for d in engineered)
    for dim in engineered:
        raw = weights.get(dim.weightkey, dim.defaultweight)
        result[dim.weightkey] = (raw / eng_total * eng_budget) if eng_total > 0.0 else 0.0

    # Learned pool
    if lrn_budget > 0.0:
        lrn_total = sum(weights.get(d.weightkey, d.defaultweight) for d in learned)
        for dim in learned:
            raw = weights.get(dim.weightkey, dim.defaultweight)
            result[dim.weightkey] = (raw / lrn_total * lrn_budget) if lrn_total > 0.0 else 0.0
    else:
        for dim in learned:
            result[dim.weightkey] = 0.0

    return result


def update_weights_from_outcomes(
    dimensions: list[ScoringDimensionSpec],
    current_weights: dict[str, float],
    observed_performance: dict[str, float],
    *,
    engineered_ema_alpha: float | None = None,
    learned_ema_alpha: float | None = None,
) -> dict[str, float]:
    """Apply EMA update to weights based on observed outcome performance.

    Engineered dimensions use a slow alpha (conservative); learned dimensions
    use a fast alpha (aggressive). This means learned primitives that don't
    predict outcomes get downweighted quickly while engineered dims stay stable.

    Formula: new_weight = (1 - alpha) * old_weight + alpha * observed
    """
    eng_alpha = engineered_ema_alpha if engineered_ema_alpha is not None else settings.engineered_ema_alpha
    lrn_alpha = learned_ema_alpha if learned_ema_alpha is not None else settings.learned_ema_alpha

    updated: dict[str, float] = {}

    for dim in dimensions:
        key = dim.weightkey
        old_w = current_weights.get(key, dim.defaultweight)
        observed = observed_performance.get(key)

        if observed is None:
            updated[key] = old_w
            continue

        alpha = lrn_alpha if _is_learned(dim) else eng_alpha
        new_w = (1.0 - alpha) * old_w + alpha * observed
        updated[key] = max(0.0, new_w)

        if abs(new_w - old_w) > 0.01:
            pool = "learned" if _is_learned(dim) else "engineered"
            logger.debug(
                "EMA update [%s] %s: %.4f -> %.4f (alpha=%.3f, observed=%.4f)",
                pool, key, old_w, new_w, alpha, observed,
            )

    return updated
