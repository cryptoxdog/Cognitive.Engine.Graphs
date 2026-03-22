"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [causal]
tags: [causal, taxonomy, edges]
owner: engine-team
status: active
--- /L9_META ---

Causal edge type taxonomy and validation.
Defines the 10 causal edge types and validates edge properties.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class CausalEdgeType(StrEnum):
    """
    10 causal edge types that distinguish asymmetric influence
    from symmetric association.

    These are domain-agnostic -- any domain spec can declare them
    in its causal.causal_edges section.
    """

    CAUSED_BY = "CAUSED_BY"
    TRIGGERED = "TRIGGERED"
    DROVE = "DROVE"
    RESULTED_IN = "RESULTED_IN"
    ACCELERATED_BY = "ACCELERATED_BY"
    BLOCKED_BY = "BLOCKED_BY"
    ENABLED_BY = "ENABLED_BY"
    PREVENTED_BY = "PREVENTED_BY"
    INFLUENCED_BY = "INFLUENCED_BY"
    CONTRIBUTED_TO = "CONTRIBUTED_TO"


# Required properties for each causal edge type
_REQUIRED_BASE_PROPERTIES = frozenset({"confidence", "mechanism"})

# Edge types that require temporal validation (source.timestamp < target.timestamp)
_TEMPORAL_EDGE_TYPES = frozenset(
    {
        CausalEdgeType.CAUSED_BY,
        CausalEdgeType.TRIGGERED,
        CausalEdgeType.DROVE,
        CausalEdgeType.RESULTED_IN,
        CausalEdgeType.ACCELERATED_BY,
        CausalEdgeType.BLOCKED_BY,
        CausalEdgeType.ENABLED_BY,
        CausalEdgeType.PREVENTED_BY,
    }
)


class CausalEdgeValidator:
    """
    Validates that causal edges meet the three requirements:
    1. Temporal precedence: source.timestamp < target.timestamp
    2. Mechanism: edge properties encode the causal pathway
    3. Confidence: edge carries a confidence score (0.0-1.0)
    """

    @staticmethod
    def validate_edge_properties(
        edge_type: CausalEdgeType,
        properties: dict[str, Any],
    ) -> list[str]:
        """Returns list of validation errors (empty = valid)."""
        errors: list[str] = []

        # Check confidence
        confidence = properties.get("confidence")
        if confidence is None:
            errors.append(f"Missing required property: confidence for {edge_type}")
        elif not isinstance(confidence, (int, float)):
            errors.append("confidence must be a numeric value")
        elif confidence < 0.0 or confidence > 1.0:
            errors.append("confidence must be between 0.0 and 1.0")

        # Check mechanism
        mechanism = properties.get("mechanism")
        if mechanism is None:
            errors.append("Missing required property: mechanism")
        elif not isinstance(mechanism, str) or not mechanism.strip():
            errors.append("mechanism must be a non-empty string")

        return errors

    @staticmethod
    def validate_temporal_precedence(
        source_timestamp: Any,
        target_timestamp: Any,
        edge_type: CausalEdgeType,
    ) -> list[str]:
        """Validate temporal ordering for edge types that require it."""
        errors: list[str] = []

        if edge_type not in _TEMPORAL_EDGE_TYPES:
            return errors

        if source_timestamp is None or target_timestamp is None:
            errors.append(f"Temporal edge type {edge_type} requires timestamps on both source and target nodes")
            return errors

        if source_timestamp >= target_timestamp:
            errors.append(
                f"Temporal precedence violated: source timestamp ({source_timestamp}) "
                f"must precede target timestamp ({target_timestamp}) for edge type {edge_type}"
            )

        return errors

    @staticmethod
    def is_valid_edge_type(edge_type: str) -> bool:
        """Check if a string is a valid CausalEdgeType value."""
        try:
            CausalEdgeType(edge_type)
        except ValueError:
            return False
        return True
