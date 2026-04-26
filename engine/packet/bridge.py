from __future__ import annotations

from typing import Any

from l9_core.models import TransportPacket


class PacketBridge:
    def inflate_ingress(
        self, *, tenant_id: str, actor: str, packet_type: str, payload: dict[str, Any]
    ) -> TransportPacket:
        enriched = {**payload, "tenant_id": tenant_id, "actor": actor}
        return TransportPacket.create(action=packet_type, payload=enriched)

    def attach_entity_semantics(
        self,
        *,
        packet: TransportPacket,
        entity_type: str,
        canonical_entity_type: str,
    ) -> TransportPacket:
        enriched = {**packet.payload, "entity_type": entity_type, "canonical_entity_type": canonical_entity_type}
        return packet.derive(action=packet.action, payload=enriched)

    def decision_packet(self, *, packet: TransportPacket, decision: dict[str, Any]) -> TransportPacket:
        return packet.derive(action="routing_decision", payload=decision)

    def outcome_packet(self, *, packet: TransportPacket, outcome: dict[str, Any]) -> TransportPacket:
        return packet.derive(action="outcome_event", payload=outcome)
