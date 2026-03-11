"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [packet, chassis-bridge]
owner: engine-team
status: active
--- /L9_META ---
"""
# # L9 Chassis ↔ PacketEnvelope v3.0.0 Bridge
# Inflates minimal client JSON → full constellation PacketEnvelope.
# Deflates engine response → wire-safe outbound envelope.

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from engine.packet.packet_envelope import (
    Action,
    HopEntry,
    PacketAddress,
    PacketEnvelope,
    PacketGovernance,
    PacketType,
    TenantContext,
    create_packet,
)


def inflate_ingress(
    *,
    action: str,
    payload: dict[str, Any],
    tenant: str,
    trace_id: str,
    source_node: str = "chassis",
    intent: str | None = None,
    classification: str = "internal",
    on_behalf_of: str | None = None,
    user_id: str | None = None,
    org_id: str | None = None,
) -> PacketEnvelope:
    """
    Called by the chassis when a client POST /v1/execute arrives.
    Minimal input → full PacketEnvelope ready for engine consumption.
    """
    return create_packet(
        packet_type=PacketType.REQUEST,
        action=Action(action),
        source_node=source_node,
        actor_tenant=tenant,
        payload=payload,
        trace_id=trace_id,
        on_behalf_of=on_behalf_of,
        originator=tenant,
        org_id=org_id,
        user_id=user_id,
        classification=classification,
        intent=intent,
    )


def deflate_egress(
    *,
    request: PacketEnvelope,
    engine_data: dict[str, Any],
    status: str = "success",
    processing_ms: float,
    engine_version: str = "0.0.0",
    responding_node: str,
) -> PacketEnvelope:
    """
    Called by the chassis after engine returns.
    Creates a response PacketEnvelope derived from the request.
    """
    now = datetime.now(UTC)

    return request.derive(
        packet_type=PacketType.RESPONSE,
        payload={
            "status": status,
            "data": engine_data,
            "meta": {
                "trace_id": request.observability.trace_id,
                "execution_ms": processing_ms,
                "version": engine_version,
                "timestamp": now.isoformat(),
            },
        },
        address=PacketAddress(
            source_node=responding_node,
            destination_node=request.address.reply_to or request.address.source_node,
        ),
        derivation_type="response",
        extra_hop=HopEntry(
            node_id=responding_node,
            action=request.action.value,
            entered_at=request.observability.created_at,
            exited_at=now,
            status=status,
        ),
    )


def delegate_to_node(
    *,
    source_packet: PacketEnvelope,
    from_node: str,
    to_node: str,
    delegated_action: Action,
    scope: tuple[str, ...],
    payload_override: dict[str, Any] | None = None,
) -> PacketEnvelope:
    """
    Called when one constellation node delegates work to another.
    Creates a DELEGATION packet with proper tenant context + auth chain.
    """
    from engine.packet.packet_envelope import DelegationLink

    now = datetime.now(UTC)

    return source_packet.derive(
        packet_type=PacketType.DELEGATION,
        action=delegated_action,
        payload=payload_override or source_packet.payload,
        address=PacketAddress(
            source_node=from_node,
            destination_node=to_node,
            reply_to=from_node,
        ),
        tenant=TenantContext(
            actor=source_packet.tenant.actor,
            on_behalf_of=source_packet.tenant.actor,
            originator=source_packet.tenant.originator or source_packet.tenant.actor,
            org_id=source_packet.tenant.org_id,
            user_id=source_packet.tenant.user_id,
        ),
        derivation_type="delegation",
        extra_hop=HopEntry(
            node_id=from_node,
            action="delegate",
            entered_at=now,
            status="delegated",
        ),
        extra_delegation=DelegationLink(
            delegator=from_node,
            delegatee=to_node,
            scope=scope,
            granted_at=now,
        ),
        governance=PacketGovernance(
            intent=f"Delegated {delegated_action.value} to {to_node}",
            compliance_tags=source_packet.governance.compliance_tags,
            audit_required=True,
        ),
    )
