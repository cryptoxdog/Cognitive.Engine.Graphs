"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [packet]
owner: engine-team
status: active
--- /L9_META ---

engine/packet — PacketEnvelope immutable communication protocol.
"""
from engine.packet.packet_envelope import PacketEnvelope
from engine.packet.chassis_contract import inflate_ingress, deflate_egress

__all__ = ["PacketEnvelope", "inflate_ingress", "deflate_egress"]
