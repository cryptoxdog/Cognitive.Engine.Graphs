"""Shared transport models for strict cutover.

TransportPacket is the canonical container.
PacketEnvelope exists only as a deprecated compatibility wrapper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
from uuid import uuid4


def _stable_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TransportPacket:
    packet_id: str
    action: str
    payload: dict[str, Any]
    runtime_authority: str = "Gate_SDK"
    routing_authority: str = "Gate"
    transport_authority: str = "TransportPacket"
    content_hash: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "content_hash",
            _stable_hash(
                {
                    "packet_id": self.packet_id,
                    "action": self.action,
                    "payload": self.payload,
                    "runtime_authority": self.runtime_authority,
                    "routing_authority": self.routing_authority,
                    "transport_authority": self.transport_authority,
                }
            ),
        )

    @classmethod
    def create(cls, action: str, payload: dict[str, Any]) -> TransportPacket:
        return cls(packet_id=str(uuid4()), action=action, payload=payload)

    def derive(self, action: str | None = None, payload: dict[str, Any] | None = None) -> TransportPacket:
        next_action = action if action is not None else self.action
        next_payload = payload if payload is not None else dict(self.payload)
        return TransportPacket.create(action=next_action, payload=next_payload)


@dataclass(frozen=True)
class PacketEnvelope:
    """Deprecated compatibility wrapper.

    This type must not be used as canonical runtime truth.
    """

    packet_type: str
    action: str
    payload: dict[str, Any]

    @classmethod
    def from_transport_packet(cls, packet: TransportPacket) -> PacketEnvelope:
        return cls(packet_type="compatibility_only", action=packet.action, payload=dict(packet.payload))

    def to_transport_packet(self) -> TransportPacket:
        return TransportPacket.create(action=self.action, payload=dict(self.payload))
