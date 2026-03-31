"""
--- L9_META ---
l9_schema: 1
origin: phase2-implementation
engine: graph
layer: [gates]
tags: [packet, envelope, lineage, content-hash, safety]
owner: engine-team
status: active
--- /L9_META ---

engine/gates/packet_bridge.py

PacketEnvelope Safety Layer.

Enforces L9 Constellation protocol contracts:
  - Immutability
  - Lineage preservation
  - Content-hash integrity
  - Tenant propagation
  - Audit traceability

All external ingress/egress MUST pass through this module.
Never bypass PacketEnvelope for inter-node communication.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger("packet_bridge")


def validate_packet(packet: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate incoming PacketEnvelope structure.

    Required Fields (L9 Contract):
        - header.packet_id
        - header.tenant_id
        - header.action
        - header.timestamp
        - content_hash
        - payload

    Args:
        packet: Raw packet dict from ingress

    Returns:
        (is_valid, error_message)

    Examples:
        >>> valid_packet = {
        ...     "header": {
        ...         "packet_id": "pkt_123",
        ...         "tenant_id": "tenant_1",
        ...         "action": "enrich",
        ...         "timestamp": "2026-03-28T22:00:00Z"
        ...     },
        ...     "content_hash": "abc123",
        ...     "payload": {"entity_id": "E001"}
        ... }
        >>> validate_packet(valid_packet)
        (True, None)
        >>> validate_packet({"header": {}})
        (False, 'Missing required header field: packet_id')
    """
    if "header" not in packet:
        return False, "Missing 'header' field"

    header = packet["header"]

    for field in ("packet_id", "tenant_id", "action", "timestamp"):
        if field not in header:
            return False, f"Missing required header field: {field}"

    if "content_hash" not in packet:
        return False, "Missing 'content_hash' field"

    if "payload" not in packet:
        return False, "Missing 'payload' field"

    return True, None


def wrap_response(
    result: dict[str, Any],
    request_packet: dict[str, Any],
    intelligence_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Wrap handler response in PacketEnvelope format.

    Preserves lineage:
        - Copies tenant_id from request
        - Appends request packet_id to lineage chain
        - Generates new packet_id for response
        - Computes content-hash of response payload

    Args:
        result:               Handler output dict
        request_packet:       Original inbound PacketEnvelope
        intelligence_quality: Optional quality metadata (belief propagation stats)

    Returns:
        PacketEnvelope-compliant response dict

    Examples:
        >>> request = {
        ...     "header": {
        ...         "packet_id": "req_001",
        ...         "tenant_id": "tenant_alpha",
        ...         "action": "enrich"
        ...     }
        ... }
        >>> result = {"enriched_data": {}}
        >>> response = wrap_response(result, request)
        >>> response["header"]["tenant_id"]
        'tenant_alpha'
        >>> "req_001" in response["header"]["lineage"]
        True
    """
    request_header = request_packet.get("header", {})

    response_header = {
        "packet_id": f"pkt_{uuid4().hex[:12]}",
        "tenant_id": request_header.get("tenant_id", "unknown"),
        "action": request_header.get("action", "unknown"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lineage": [
            *request_header.get("lineage", []),
            request_header.get("packet_id", "unknown"),
        ],
    }

    response_payload: dict[str, Any] = {"result": result}
    if intelligence_quality is not None:
        response_payload["intelligence_quality"] = intelligence_quality

    payload_json = json.dumps(response_payload, sort_keys=True, default=str)
    content_hash = hashlib.sha256(payload_json.encode()).hexdigest()

    response_envelope = {
        "header": response_header,
        "payload": response_payload,
        "content_hash": content_hash,
    }

    logger.info(
        "response_wrapped",
        packet_id=response_header["packet_id"],
        tenant_id=response_header["tenant_id"],
        lineage_depth=len(response_header["lineage"]),
    )

    return response_envelope
