"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [personas]
tags: [types, pydantic, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Pydantic type definitions for the persona composition subsystem.

Defines TraitVector, FeatureVector, Persona, and PersonaOutput models
used across composition, selection, synthesis, and suppression.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

from __future__ import annotations

from typing import TypedDict

from pydantic import BaseModel, Field


class TraitVector(BaseModel):
    """
    Persona trait vector — encodes how strongly a persona aligns with each cognitive dimension.

    All values in [0, 1]. The paper proves: v(p+q) ~ w_p*v(p) + w_q*v(q),
    meaning trait vectors compose through weighted vector arithmetic.
    """

    analytical_depth: float = Field(default=0.0, ge=0.0, le=1.0)
    creativity: float = Field(default=0.0, ge=0.0, le=1.0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    empathy: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_expertise: float = Field(default=0.0, ge=0.0, le=1.0)
    skepticism: float = Field(default=0.0, ge=0.0, le=1.0)

    # Primitive-aligned dimensions (Tier 3)
    verification_need: float = Field(default=0.0, ge=0.0, le=1.0)
    comparison_need: float = Field(default=0.0, ge=0.0, le=1.0)
    generation_need: float = Field(default=0.0, ge=0.0, le=1.0)
    quantitative_need: float = Field(default=0.0, ge=0.0, le=1.0)

    # Safety dimensions (Tier 3)
    safety_sensitivity: float = Field(default=0.0, ge=0.0, le=1.0)
    manipulation_resistance: float = Field(default=0.0, ge=0.0, le=1.0)
    escalation_risk: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_dict(self) -> dict[str, float]:
        """Return all dimensions as a flat dictionary."""
        return self.model_dump()

    def dimensions(self) -> list[str]:
        """Return list of all dimension names."""
        return list(self.model_fields.keys())


class FeatureVector(BaseModel):
    """
    Query feature vector — classifier output encoding the cognitive demands of a query.

    All values in [0, 1]. Used to compute dot-product scores against persona TraitVectors.
    """

    analytical_depth: float = Field(default=0.0, ge=0.0, le=1.0)
    creativity: float = Field(default=0.0, ge=0.0, le=1.0)
    precision: float = Field(default=0.0, ge=0.0, le=1.0)
    empathy: float = Field(default=0.0, ge=0.0, le=1.0)
    domain_expertise: float = Field(default=0.0, ge=0.0, le=1.0)
    skepticism: float = Field(default=0.0, ge=0.0, le=1.0)

    # Primitive-aligned dimensions (Tier 3)
    verification_need: float = Field(default=0.0, ge=0.0, le=1.0)
    comparison_need: float = Field(default=0.0, ge=0.0, le=1.0)
    generation_need: float = Field(default=0.0, ge=0.0, le=1.0)
    quantitative_need: float = Field(default=0.0, ge=0.0, le=1.0)

    # Safety dimensions (Tier 3)
    safety_sensitivity: float = Field(default=0.0, ge=0.0, le=1.0)
    manipulation_resistance: float = Field(default=0.0, ge=0.0, le=1.0)
    escalation_risk: float = Field(default=0.0, ge=0.0, le=1.0)

    def to_dict(self) -> dict[str, float]:
        """Return all dimensions as a flat dictionary."""
        return self.model_dump()


class Persona(BaseModel):
    """
    Persona definition — a named cognitive agent with trait vector, system prompt, and constraints.

    The system_prompt drives LLM behavior. The trait_vector determines activation scoring.
    forbidden_behaviors list behaviors to suppress via constraint injection.
    """

    id: str
    name: str
    description: str = ""
    system_prompt: str = ""
    trait_vector: TraitVector = Field(default_factory=TraitVector)
    forbidden_behaviors: list[str] = Field(default_factory=list)
    is_composite: bool = False
    source_persona_ids: list[str] = Field(default_factory=list)


class PersonaOutput(BaseModel):
    """Output from a single persona execution, before synthesis."""

    persona_id: str
    persona_name: str
    content: str
    score: float = Field(default=0.0, ge=0.0)
    trait_vector: TraitVector = Field(default_factory=TraitVector)


class ScoredPersona(TypedDict):
    """A persona paired with its activation score."""

    persona: Persona
    score: float


class WeightedPersona(TypedDict):
    """A persona paired with a blending weight."""

    persona: Persona
    weight: float


class WeightedOutput(TypedDict):
    """A persona output paired with its synthesis weight."""

    output: PersonaOutput
    weight: float
