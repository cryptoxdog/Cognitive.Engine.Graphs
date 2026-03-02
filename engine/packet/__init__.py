"""


--- L9_META ---l9_schema: 1origin: engine-specificengine: graphlayer: [config]tags: [packet]owner: engine-teamstatus: active--- /L9_META ---engine/packet — PacketEnvelope immutable communication protocol."""from engine.packet.chassis_contract import deflate_egress, inflate_ingressfrom engine.packet.packet_envelope import PacketEnvelope__all__ = ["PacketEnvelope", "deflate_egress", "inflate_ingress"]
