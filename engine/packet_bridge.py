"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [integration]
tags: [gate, packet, transport, sdk]
owner: engine-team
status: active
--- /L9_META ---

engine/packet_bridge.py — PacketEnvelope construction helpers for GRAPH

All outbound packets MUST be built via this module.
Direct TransportPacket instantiation in handler code is forbidden.

Provides:
    build_request_packet  — construct an outbound PacketEnvelope
    build_response_packet — construct a reply preserving inbound lineage
    extract_payload       — safely extract decoded payload dict

L9 contracts enforced:
    - trace_id propagation       (missing_trace_id)
    - tenant isolation           (tenant_isolation_violation)
    - lineage preservation       (packet_protocol_violation)
    - immutability               (derive() used, never direct mutation)
"""

from __future__ import annotations

import logging
from typing import Any

from constellation_node_sdk import TransportPacket, create_transport_packet

logger = logging.getLogger(__name__)

_GRAPH_NODE = "graph"
_GATE_NODE = "gate"


def build_request_packet(
    *,
    action: str,
    payload: dict[str, Any],
    tenant: str,
    trace_id: str,
    destination_node: str = _GATE_NODE,
    reply_to: str = _GRAPH_NODE,
    packet_type: str = "request",
    intent: str = "graph-engine-request",
    priority: int = 2,
    idempotency_key: str | None = None,
    timeout_ms: int = 30_000,
    correlation_id: str | None = None,
) -> TransportPacket:
    """Build a fully-compliant outbound TransportPacket from GRAPH to Gate.

    trace_id is required and must be propagated from the inbound request.
    Raises ValueError on blank trace_id, tenant, or action.
    """
    if not trace_id or not trace_id.strip():
        msg = "trace_id must be provided for all outbound packets"
        raise ValueError(msg)
    if not tenant or not tenant.strip():
        msg = "tenant must be provided for all outbound packets"
        raise ValueError(msg)
    if not action or not action.strip():
        msg = "action must be provided"
        raise ValueError(msg)

    return create_transport_packet(
        action=action,
        payload=payload,
        tenant=tenant,
        destination_node=destination_node,
        source_node=_GRAPH_NODE,
        reply_to=reply_to,
        priority=priority,
        timeout_ms=timeout_ms,
        idempotency_key=idempotency_key,
        trace_id=trace_id.strip(),
        correlation_id=correlation_id,
    )


def build_response_packet(
    *,
    inbound: TransportPacket,
    payload: dict[str, Any],
    action: str | None = None,
    intent: str = "graph-engine-response",
) -> TransportPacket:
    """Build a response packet preserving full lineage from the inbound packet.

    Uses inbound.derive() to guarantee immutability, hash refresh,
    and lineage chain increment — never builds from scratch.
    """
    return inbound.derive(
        action=action or inbound.header.action,
        payload=payload,
        source_node=_GRAPH_NODE,
        destination_node=(inbound.address.reply_to if inbound.address is not None else _GATE_NODE),
        reply_to=_GRAPH_NODE,
        packet_type="response",
    )


def extract_payload(packet: TransportPacket) -> dict[str, Any]:
    """Extract and return the decoded payload dict from a TransportPacket.

    Returns empty dict if payload is absent. Never raises.
    """
    raw = packet.payload
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        logger.warning(
            "extract_payload: expected dict payload, got %s for packet_id=%s",
            type(raw).__name__,
            packet.header.packet_id,
        )
        return {}
    return raw
