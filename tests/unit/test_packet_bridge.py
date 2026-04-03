"""Unit tests — PacketEnvelope bridge: hash determinism, payload sensitivity."""

from __future__ import annotations


def test_packet_envelope_content_hash_is_deterministic():
    from engine.chassis.tenant_context import TenantContext

    from engine.packet.packet_envelope import PacketEnvelope, PacketType

    tenant = TenantContext(tenant_id="test", actor="unit-test")
    p1 = PacketEnvelope(
        packet_type=PacketType.REQUEST,
        tenant=tenant,
        payload={"action": "match", "x": 1},
    )
    p2 = PacketEnvelope(
        packet_type=PacketType.REQUEST,
        tenant=tenant,
        payload={"action": "match", "x": 1},
    )
    assert p1.content_hash == p2.content_hash
    assert len(p1.content_hash) == 64  # SHA-256 hex


def test_packet_envelope_hash_changes_with_payload():
    from engine.chassis.tenant_context import TenantContext

    from engine.packet.packet_envelope import PacketEnvelope, PacketType

    tenant = TenantContext(tenant_id="test", actor="unit-test")
    p1 = PacketEnvelope(
        packet_type=PacketType.REQUEST,
        tenant=tenant,
        payload={"action": "match"},
    )
    p2 = PacketEnvelope(
        packet_type=PacketType.REQUEST,
        tenant=tenant,
        payload={"action": "sync"},
    )
    assert p1.content_hash != p2.content_hash


def test_packet_bridge_inflate_ingress():
    from engine.packet.bridge import PacketBridge

    bridge = PacketBridge()
    packet = bridge.inflate_ingress(
        tenant_id="tenant-a",
        actor="engine",
        packet_type="graph_sync",
        payload={"entity_type": "Facility", "batch": []},
    )
    assert packet.packet_type == "graph_sync"
    assert packet.content_hash
    assert packet.lineage.root_id


def test_packet_bridge_derive_preserves_lineage():
    from engine.packet.bridge import PacketBridge

    bridge = PacketBridge()
    root = bridge.inflate_ingress(
        tenant_id="tenant-a",
        actor="engine",
        packet_type="graph_sync",
        payload={"entity_type": "Facility"},
    )
    derived = root.derive("outcome_event", {"result": "ok"})
    assert derived.lineage.root_id == root.lineage.root_id
    assert derived.lineage.parent_id == root.packet_id
    assert derived.lineage.hop_count == 1
