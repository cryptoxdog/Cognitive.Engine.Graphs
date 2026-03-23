"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [personas]
tags: [composition, algebra, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Algebraic trait vector composition engine.

Implements vector arithmetic operations on persona trait vectors following the
compositional geometry of reasoning:

  v(p + q) ~ w_p * v(p) + w_q * v(q)

Operations: add, subtract, scale. All results clamped to [0, 1].

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

from __future__ import annotations

import logging
from typing import Literal, assert_never

from engine.personas.constants import persona_settings
from engine.personas.types import FeatureVector, Persona, ScoredPersona, TraitVector, WeightedPersona

logger = logging.getLogger(__name__)


def _clamp(value: float) -> float:
    """Clamp a value to the configured [min, max] trait range."""
    return max(persona_settings.trait_clamp_min, min(persona_settings.trait_clamp_max, value))


def compose_trait_vectors(
    base: TraitVector,
    modifier: TraitVector,
    operation: Literal["add", "subtract", "scale"],
    weight: float = 1.0,
) -> TraitVector:
    """
    Algebraic trait vector composition.

    Args:
        base: Base trait vector.
        modifier: Modifier trait vector (ignored for 'scale' — only base is used).
        operation: 'add' (base + weight*modifier), 'subtract' (base - weight*modifier),
                   or 'scale' (base * weight).
        weight: Scalar weight applied to modifier (add/subtract) or base (scale).

    Returns:
        New TraitVector with all dimensions clamped to [0, 1].
    """
    base_d = base.to_dict()
    modifier_d = modifier.to_dict()
    result: dict[str, float] = {}

    for dim in base.dimensions():
        b = base_d[dim]
        m = modifier_d[dim]

        if operation == "add":
            result[dim] = _clamp(b + weight * m)
        elif operation == "subtract":
            result[dim] = _clamp(b - weight * m)
        elif operation == "scale":
            result[dim] = _clamp(b * weight)
        else:
            assert_never(operation)

    return TraitVector(**result)


def blend_personas(personas: list[WeightedPersona]) -> TraitVector:
    """
    Normalized weighted sum of persona trait vectors.

    Formula: SUM(w_i * v_i) / SUM(w_i) for each dimension.
    All output dimensions clamped to [0, 1].

    Args:
        personas: List of WeightedPersona dicts with 'persona' and 'weight' keys.

    Returns:
        Blended TraitVector.

    Raises:
        ValueError: If personas list is empty or all weights are zero.
    """
    if not personas:
        msg = "Cannot blend empty personas list."
        raise ValueError(msg)

    total_weight = sum(p["weight"] for p in personas)
    if total_weight == 0.0:
        msg = "Cannot blend personas with all-zero weights."
        raise ValueError(msg)

    dim_names = TraitVector().dimensions()
    result: dict[str, float] = {}

    for dim in dim_names:
        weighted_sum = 0.0
        for entry in personas:
            persona = entry["persona"]
            w = entry["weight"]
            weighted_sum += w * getattr(persona.trait_vector, dim)
        result[dim] = _clamp(weighted_sum / total_weight)

    return TraitVector(**result)


def _extract_relevant_instructions(persona: Persona, feature_vector: FeatureVector) -> str:
    """
    Extract the most relevant parts of a persona's system prompt based on
    how well the persona's traits align with the query's feature vector.

    Instead of concatenating entire prompts, select the persona's prompt only
    if the persona's trait alignment score exceeds half the maximum possible.
    """
    if not persona.system_prompt:
        return ""

    # Compute alignment: dot product of trait_vector with feature_vector
    tv = persona.trait_vector.to_dict()
    fv = feature_vector.to_dict()
    alignment = sum(tv[dim] * fv[dim] for dim in tv)
    max_alignment = sum(fv[dim] for dim in fv)

    # Include full prompt if alignment is meaningful (>50% of maximum)
    if max_alignment > 0.0 and alignment >= max_alignment * 0.5:
        return persona.system_prompt
    # Include abbreviated version for lower alignment
    lines = persona.system_prompt.strip().splitlines()
    if lines:
        return lines[0]
    return ""


def create_composite_persona(
    feature_vector: FeatureVector,
    top_personas: list[ScoredPersona],
) -> Persona:
    """
    Create a dynamic hybrid persona from top-scoring personas.

    Takes the top-k (configurable, default 3) scoring personas, weights by their
    activation scores, blends trait vectors, and constructs a hybrid system prompt
    that prioritizes the most relevant instructions.

    Args:
        feature_vector: The query's FeatureVector (used to select relevant instructions).
        top_personas: List of ScoredPersona dicts ordered by score descending.

    Returns:
        New composite Persona (temporary, not persisted).
    """
    k = persona_settings.composite_top_k
    selected = top_personas[:k]

    if not selected:
        msg = "Cannot create composite persona from empty list."
        raise ValueError(msg)

    # Use scores as weights for blending
    blend_input: list[WeightedPersona] = [
        {"persona": p["persona"], "weight": p["score"]} for p in selected
    ]
    blended_vector = blend_personas(blend_input)

    # Build hybrid system prompt from relevant parts
    prompt_parts: list[str] = []
    source_ids: list[str] = []
    source_names: list[str] = []

    for entry in selected:
        persona = entry["persona"]
        relevant = _extract_relevant_instructions(persona, feature_vector)
        if relevant:
            prompt_parts.append(f"[{persona.name}]: {relevant}")
        source_ids.append(persona.id)
        source_names.append(persona.name)

    composite_prompt = (
        "You are a composite cognitive agent synthesizing perspectives from: "
        + ", ".join(source_names)
        + ".\n\n"
        + "Integrate the following cognitive orientations:\n"
        + "\n\n".join(prompt_parts)
        + "\n\nSynthesize insights from all perspectives. "
        "Prioritize the most relevant viewpoint for each aspect of the query."
    )

    # Merge forbidden behaviors from all source personas
    all_forbidden: list[str] = []
    for entry in selected:
        persona = entry["persona"]
        for behavior in persona.forbidden_behaviors:
            if behavior not in all_forbidden:
                all_forbidden.append(behavior)

    composite_id = "composite_" + "_".join(source_ids[:k])
    logger.info(
        "Created composite persona '%s' from sources=%s weights=%s",
        composite_id,
        source_ids,
        [p["score"] for p in selected],
    )

    return Persona(
        id=composite_id,
        name=f"Composite({', '.join(source_names)})",
        description=f"Dynamic composite of {', '.join(source_names)}",
        system_prompt=composite_prompt,
        trait_vector=blended_vector,
        forbidden_behaviors=all_forbidden,
        is_composite=True,
        source_persona_ids=source_ids,
    )
