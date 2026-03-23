"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [personas]
tags: [selector, scoring, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Persona selection via dot-product scoring of FeatureVector x TraitVector.

Selection pipeline:
1. Score all personas: dot(featureVector, traitVector)
2. If top score < LOW_CONFIDENCE_THRESHOLD -> create composite from top-k
3. Otherwise: select primary + secondaries above activation ratio

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

from __future__ import annotations

import logging

from engine.personas.composer import create_composite_persona
from engine.personas.constants import persona_settings
from engine.personas.types import FeatureVector, Persona, ScoredPersona

logger = logging.getLogger(__name__)


def _dot_product(feature_vector: FeatureVector, trait_vector_dict: dict[str, float]) -> float:
    """Compute dot product of feature vector against trait vector."""
    fv = feature_vector.to_dict()
    return sum(fv[dim] * trait_vector_dict.get(dim, 0.0) for dim in fv)


def score_personas(
    feature_vector: FeatureVector,
    personas: list[Persona],
) -> list[ScoredPersona]:
    """
    Score all personas against a feature vector using dot product.

    Args:
        feature_vector: The query's classified feature vector.
        personas: List of all available personas.

    Returns:
        List of ScoredPersona dicts sorted by score descending.
    """
    scored: list[ScoredPersona] = []
    for persona in personas:
        tv_dict = persona.trait_vector.to_dict()
        score = _dot_product(feature_vector, tv_dict)
        scored.append({"persona": persona, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def select_personas(
    feature_vector: FeatureVector,
    personas: list[Persona],
) -> list[Persona]:
    """
    Select active personas for a query.

    Selection logic:
    1. Score all personas via dot product.
    2. If top score < LOW_CONFIDENCE_THRESHOLD:
       - Create composite persona from top-k (fallback).
       - Return composite as sole active persona.
    3. Otherwise:
       - Return primary persona + any secondaries whose score >=
         secondary_activation_ratio * primary score (up to max_personas).

    Args:
        feature_vector: The query's classified feature vector.
        personas: List of all available personas.

    Returns:
        List of active personas (1 to max_personas).
    """
    if not personas:
        return []

    scored = score_personas(feature_vector, personas)
    top_score = scored[0]["score"]

    # Low-confidence fallback: create composite
    if top_score < persona_settings.low_confidence_threshold:
        logger.info(
            "Low confidence (top_score=%.4f < threshold=%.4f). Creating composite persona.",
            top_score,
            persona_settings.low_confidence_threshold,
        )
        composite = create_composite_persona(feature_vector, scored)
        return [composite]

    # Standard selection: primary + qualified secondaries
    primary = scored[0]["persona"]
    active: list[Persona] = [primary]
    threshold = top_score * persona_settings.secondary_activation_ratio

    for entry in scored[1:]:
        if len(active) >= persona_settings.max_personas:
            break
        if entry["score"] >= threshold:
            active.append(entry["persona"])

    logger.info(
        "Selected %d persona(s): primary=%s (score=%.4f), secondaries=%s",
        len(active),
        active[0].name,
        top_score,
        [p.name for p in active[1:]],
    )
    return active
