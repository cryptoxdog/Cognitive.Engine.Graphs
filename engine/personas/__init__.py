"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [personas]
tags: [personas, composition, tier-3]
owner: engine-team
status: active
--- /L9_META ---

Algebraic persona composition subsystem.

Implements persona trait vector algebra, composite persona creation,
primitive-aware synthesis, and forbidden behavior suppression.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)
"""

from engine.personas.composer import blend_personas, compose_trait_vectors, create_composite_persona
from engine.personas.types import (
    FeatureVector,
    Persona,
    PersonaOutput,
    ScoredPersona,
    TraitVector,
    WeightedOutput,
    WeightedPersona,
)

__all__ = [
    "FeatureVector",
    "Persona",
    "PersonaOutput",
    "ScoredPersona",
    "TraitVector",
    "WeightedOutput",
    "WeightedPersona",
    "blend_personas",
    "compose_trait_vectors",
    "create_composite_persona",
]
