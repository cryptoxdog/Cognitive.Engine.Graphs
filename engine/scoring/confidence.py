"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [scoring]
tags: [scoring, confidence, dual-dimensions]
owner: engine-team
status: active
--- /L9_META ---

Confidence-based weight gating for dual dimension classes.
PRIMITIVE dimensions use a higher confidence threshold to limit influence
of uncertain learned scores. Engineered dimensions use the existing KGE threshold.
"""

from __future__ import annotations

import logging

from engine.config.schema import ComputationType, ScoringDimensionSpec
from engine.config.settings import settings

logger = logging.getLogger(__name__)


def _is_learned(dim: ScoringDimensionSpec) -> bool:
    """Return True if dimension uses a learned (PRIMITIVE) computation type."""
    return dim.computation == ComputationType.PRIMITIVE


def apply_confidence_weighting(
    dimensions: list[ScoringDimensionSpec],
    weights: dict[str, float],
    confidence_scores: dict[str, float],
    *,
    primitive_threshold: float | None = None,
    engineered_threshold: float | None = None,
) -> dict[str, float]:
    """Apply confidence-based gating to dimension weights.

    Dimensions whose confidence is below their threshold get their weight
    zeroed out. This prevents uncertain learned primitives from influencing
    final scores.

    Args:
        dimensions: All scoring dimension specs.
        weights: Current weight dict (weightkey -> weight).
        confidence_scores: Per-dimension confidence (weightkey -> 0.0..1.0).
        primitive_threshold: Override for PRIMITIVE confidence gate.
        engineered_threshold: Override for engineered confidence gate.

    Returns:
        Copy of weights with below-threshold dimensions zeroed.
    """
    prim_thresh = primitive_threshold if primitive_threshold is not None else settings.primitive_confidence_threshold
    eng_thresh = engineered_threshold if engineered_threshold is not None else settings.kge_confidence_threshold

    result: dict[str, float] = {}

    for dim in dimensions:
        key = dim.weightkey
        w = weights.get(key, dim.defaultweight)
        confidence = confidence_scores.get(key)

        if confidence is None:
            # No confidence score available — pass through unchanged
            result[key] = w
            continue

        threshold = prim_thresh if _is_learned(dim) else eng_thresh

        if confidence < threshold:
            result[key] = 0.0
            pool = "learned" if _is_learned(dim) else "engineered"
            logger.debug(
                "Confidence gate [%s] %s: conf=%.3f < threshold=%.3f → weight zeroed",
                pool, key, confidence, threshold,
            )
        else:
            result[key] = w

    return result
