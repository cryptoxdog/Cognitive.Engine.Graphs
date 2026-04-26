"""Unit tests — TransportPacket bridge: hash determinism, derive semantics."""

from __future__ import annotations


def test_transport_packet_content_hash_is_deterministic() -> None:
    from l9_core.models import TransportPacket

    fixed_id = "test-deterministic-id"
    p1 = TransportPacket(packet_id=fixed_id, action="match", payload={"x": 1})
    p2 = TransportPacket(packet_id=fixed_id, action="match", payload={"x": 1})
    assert p1.content_hash == p2.content_hash
    assert len(p1.content_hash) == 64


def test_transport_packet_hash_changes_with_payload() -> None:
    from l9_core.models import TransportPacket

    p1 = TransportPacket.create(action="match", payload={"x": 1})
    p2 = TransportPacket.create(action="match", payload={"x": 2})
    assert p1.content_hash != p2.content_hash


def test_packet_bridge_inflate_ingress() -> None:
    from engine.packet.bridge import PacketBridge

    bridge = PacketBridge()
    packet = bridge.inflate_ingress(
        tenant_id="tenant-a",
        actor="engine",
        packet_type="graph_sync",
        payload={"entity_type": "Facility", "batch": []},
    )
    assert packet.action == "graph_sync"
    assert packet.content_hash
    assert packet.transport_authority == "TransportPacket"


def test_packet_bridge_derive_preserves_action() -> None:
    from engine.packet.bridge import PacketBridge

    bridge = PacketBridge()
    root = bridge.inflate_ingress(
        tenant_id="tenant-a",
        actor="engine",
        packet_type="graph_sync",
        payload={"entity_type": "Facility"},
    )
    derived = bridge.outcome_packet(packet=root, outcome={"result": "ok"})
    assert derived.action == "outcome_event"
    assert derived.packet_id != root.packet_id
