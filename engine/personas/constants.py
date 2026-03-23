"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [personas, config]
tags: [constants, tier-3, composition]
owner: engine-team
status: active
--- /L9_META ---

Configurable constants for the algebraic persona composition subsystem.

Reference: "Algorithmic Primitives and Compositional Geometry of Reasoning
in Language Models" (arXiv 2510.15987v1)

All thresholds are configurable via environment variables prefixed PERSONA_.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class PersonaSettings(BaseSettings):
    """Persona composition settings. All env vars prefixed PERSONA_."""

    model_config = SettingsConfigDict(
        env_prefix="PERSONA_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Selector thresholds ---
    low_confidence_threshold: float = 0.15
    """When top scorer < this, create composite persona from top-k."""

    secondary_activation_ratio: float = 0.75
    """Secondary personas activate if score >= this ratio of primary score."""

    max_personas: int = 3
    """Maximum number of personas to activate."""

    # --- Composition ---
    trait_clamp_min: float = 0.0
    """Minimum value for any trait vector dimension after composition."""

    trait_clamp_max: float = 1.0
    """Maximum value for any trait vector dimension after composition."""

    composite_top_k: int = 3
    """Number of top personas used to build a composite."""

    # --- Synthesis weighting ---
    min_persona_weight: float = 0.10
    """Minimum weight per persona in synthesis (avoids total exclusion)."""

    # --- Primitive dimensions ---
    primitive_dimensions: list[str] = [
        "verification_need",
        "comparison_need",
        "generation_need",
        "quantitative_need",
    ]

    # --- Safety dimensions ---
    safety_dimensions: list[str] = [
        "safety_sensitivity",
        "manipulation_resistance",
        "escalation_risk",
    ]


# Singleton — import this instance everywhere
persona_settings = PersonaSettings()
