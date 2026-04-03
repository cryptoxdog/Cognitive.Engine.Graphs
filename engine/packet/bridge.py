from __future__ import annotations

from typing import Any

from l9_core.models import PacketEnvelope, make_root_packet


class PacketBridge:
    def inflate_ingress(
        self, *, tenant_id: str, actor: str, packet_type: str, payload: dict[str, Any]
    ) -> PacketEnvelope:
        return make_root_packet(packet_type=packet_type, tenant_id=tenant_id, actor=actor, payload=payload)

    def attach_entity_semantics(
        self,
        *,
        packet: PacketEnvelope,
        entity_type: str,
        canonical_entity_type: str,
    ) -> PacketEnvelope:
        payload = dict(packet.payload)
        payload["entity_type"] = entity_type
        payload["canonical_entity_type"] = canonical_entity_type
        return packet.derive(packet_type=packet.packet_type, payload=payload)

    def decision_packet(self, *, packet: PacketEnvelope, decision: dict[str, Any]) -> PacketEnvelope:
        return packet.derive(packet_type="routing_decision", payload=decision)

    def outcome_packet(self, *, packet: PacketEnvelope, outcome: dict[str, Any]) -> PacketEnvelope:
        return packet.derive(packet_type="outcome_event", payload=outcome)
