"""
--- L9_META ---
l9_schema: 1
origin: phase2-implementation
engine: graph
layer: [compliance]
tags: [validation, enrichment, gate-response, spec]
owner: engine-team
status: active
--- /L9_META ---

engine/compliance/validator.py

Domain Validation Layer.

Enforces spec.yaml constraints before execution:
  - Required fields present
  - Value ranges respected
  - Enum values valid
  - Type constraints satisfied

Fail fast — reject invalid payloads at ingress.
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger("validator")

_VALID_ENTITY_TYPES: frozenset[str] = frozenset(
    {"Material", "Facility", "Buyer", "Supplier"}
)


def validate_enrichment_request(payload: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate enrichment request payload.

    Required Fields:
        - entity_id:   str
        - entity_type: str (enum: Material, Facility, Buyer, Supplier)

    Optional Fields:
        - convergence_depth: int (1-5, default 1)
        - enable_pareto:     bool (default True)

    Args:
        payload: Request payload dict

    Returns:
        (is_valid, error_message)

    Examples:
        >>> validate_enrichment_request({"entity_id": "E001", "entity_type": "Material"})
        (True, None)
        >>> validate_enrichment_request({"entity_id": "E001"})
        (False, "Missing required field: entity_type")
        >>> validate_enrichment_request({"entity_id": "E001", "entity_type": "InvalidType"})
        (False, "Invalid entity_type: InvalidType. Must be one of: Buyer, Facility, Material, Supplier")
    """
    for field in ("entity_id", "entity_type"):
        if field not in payload:
            return False, f"Missing required field: {field}"

    entity_type = payload["entity_type"]
    if entity_type not in _VALID_ENTITY_TYPES:
        return (
            False,
            f"Invalid entity_type: {entity_type}. "
            f"Must be one of: {', '.join(sorted(_VALID_ENTITY_TYPES))}",
        )

    if "convergence_depth" in payload:
        depth = payload["convergence_depth"]
        if not isinstance(depth, int) or not (1 <= depth <= 5):
            return False, "convergence_depth must be an integer between 1 and 5"

    if "enable_pareto" in payload:
        if not isinstance(payload["enable_pareto"], bool):
            return False, "enable_pareto must be a boolean"

    logger.info(
        "validation_passed",
        entity_id=payload["entity_id"],
        entity_type=entity_type,
    )
    return True, None


def validate_gate_response(response: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate GATE response envelope.

    Required Fields:
        - header.packet_id
        - header.status
        - hop_trace (list)

    Args:
        response: GATE response PacketEnvelope

    Returns:
        (is_valid, error_message)

    Examples:
        >>> response = {
        ...     "header": {"packet_id": "pkt_123", "status": "COMPLETED"},
        ...     "hop_trace": []
        ... }
        >>> validate_gate_response(response)
        (True, None)
    """
    if "header" not in response:
        return False, "Missing 'header' field in GATE response"

    header = response["header"]

    if "packet_id" not in header:
        return False, "Missing 'packet_id' in response header"

    if "status" not in header:
        return False, "Missing 'status' in response header"

    if "hop_trace" not in response:
        return False, "Missing 'hop_trace' field in GATE response"

    if not isinstance(response["hop_trace"], list):
        return False, "'hop_trace' must be a list"

    logger.info(
        "gate_response_validated",
        packet_id=header["packet_id"],
        status=header["status"],
        hop_count=len(response["hop_trace"]),
    )
    return True, None
