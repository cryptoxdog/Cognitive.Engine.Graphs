# L9 PacketEnvelope v3.0.0 — Test Suite
# Covers: immutability, integrity, derivation, delegation, RLS contract, serialization

import json

import pytest
from chassis_contract import deflate_egress, delegate_to_node, inflate_ingress
from packet_envelope import (
    Action,
    PacketAddress,
    PacketEnvelope,
    PacketType,
    TenantContext,
    _compute_hash,
    create_packet,
)

# ── Fixtures ──


@pytest.fixture
def base_packet():
    return create_packet(
        packet_type=PacketType.REQUEST,
        action=Action.MATCH,
        source_node="plasticos-engine",
        actor_tenant="acme_recycling",
        payload={"polymer": "HDPE", "min_volume_kg": 5000},
        trace_id="abc123-trace",
        destination_node="match-engine",
        originator="acme_recycling",
        classification="confidential",
        pii_fields=("contact_email",),
        compliance_tags=("SOC2",),
        intent="Find matching HDPE suppliers",
    )


# ── Immutability ──


class TestImmutability:
    def test_frozen_payload(self, base_packet):
        with pytest.raises(Exception):
            base_packet.payload = {"hacked": True}

    def test_frozen_tenant(self, base_packet):
        with pytest.raises(Exception):
            base_packet.tenant = TenantContext(actor="evil")

    def test_frozen_tags(self, base_packet):
        with pytest.raises(Exception):
            base_packet.tags = ("injected",)

    def test_extra_field_rejected(self):
        with pytest.raises(Exception):
            PacketAddress(source_node="x", evil_field="y")

    def test_sub_object_frozen(self, base_packet):
        with pytest.raises(Exception):
            base_packet.address.source_node = "hijacked"


# ── Integrity ──


class TestIntegrity:
    def test_hash_matches(self, base_packet):
        assert base_packet.verify_integrity()

    def test_hash_deterministic(self, base_packet):
        h1 = _compute_hash(
            base_packet.packet_type, base_packet.action, base_packet.payload, base_packet.tenant, base_packet.address
        )
        h2 = _compute_hash(
            base_packet.packet_type, base_packet.action, base_packet.payload, base_packet.tenant, base_packet.address
        )
        assert h1 == h2

    def test_different_payload_different_hash(self, base_packet):
        other = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="plasticos-engine",
            actor_tenant="acme_recycling",
            payload={"polymer": "PP", "min_volume_kg": 999},
            trace_id="other-trace",
        )
        assert base_packet.security.content_hash != other.security.content_hash

    def test_different_tenant_different_hash(self):
        p1 = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="x",
            actor_tenant="tenant_a",
            payload={"k": "v"},
            trace_id="t",
        )
        p2 = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="x",
            actor_tenant="tenant_b",
            payload={"k": "v"},
            trace_id="t",
        )
        assert p1.security.content_hash != p2.security.content_hash


# ── Derivation ──


class TestDerivation:
    def test_derive_creates_new_id(self, base_packet):
        child = base_packet.derive(payload={"enriched": True})
        assert child.packet_id != base_packet.packet_id

    def test_derive_sets_parent(self, base_packet):
        child = base_packet.derive(payload={"enriched": True})
        assert base_packet.packet_id in child.lineage.parent_ids

    def test_derive_increments_generation(self, base_packet):
        child = base_packet.derive(payload={"x": 1})
        grandchild = child.derive(payload={"x": 2})
        assert child.lineage.generation == 1
        assert grandchild.lineage.generation == 2

    def test_derive_preserves_root(self, base_packet):
        child = base_packet.derive(payload={"x": 1})
        grandchild = child.derive(payload={"x": 2})
        assert grandchild.lineage.root_id == base_packet.packet_id

    def test_derive_preserves_trace(self, base_packet):
        child = base_packet.derive(payload={"x": 1})
        assert child.observability.trace_id == base_packet.observability.trace_id

    def test_derive_recomputes_hash(self, base_packet):
        child = base_packet.derive(payload={"different": True})
        assert child.security.content_hash != base_packet.security.content_hash
        assert child.verify_integrity()


# ── Delegation ──


class TestDelegation:
    def test_delegate_creates_delegation_link(self, base_packet):
        delegated = delegate_to_node(
            source_packet=base_packet,
            from_node="orchestrator",
            to_node="enrichment-api",
            delegated_action=Action.ENRICH,
            scope=("enrich",),
        )
        assert len(delegated.delegation_chain) == 1
        link = delegated.delegation_chain[0]
        assert link.delegator == "orchestrator"
        assert link.delegatee == "enrichment-api"
        assert link.scope == ("enrich",)

    def test_delegate_sets_on_behalf_of(self, base_packet):
        delegated = delegate_to_node(
            source_packet=base_packet,
            from_node="orchestrator",
            to_node="enrichment-api",
            delegated_action=Action.ENRICH,
            scope=("enrich",),
        )
        assert delegated.tenant.on_behalf_of == "acme_recycling"

    def test_delegate_adds_hop(self, base_packet):
        delegated = delegate_to_node(
            source_packet=base_packet,
            from_node="orchestrator",
            to_node="enrichment-api",
            delegated_action=Action.ENRICH,
            scope=("enrich",),
        )
        assert len(delegated.hop_trace) == 1
        assert delegated.hop_trace[0].node_id == "orchestrator"
        assert delegated.hop_trace[0].status == "delegated"

    def test_stacked_delegation(self, base_packet):
        d1 = delegate_to_node(
            source_packet=base_packet,
            from_node="agent",
            to_node="plasticos",
            delegated_action=Action.MATCH,
            scope=("match",),
        )
        d2 = delegate_to_node(
            source_packet=d1,
            from_node="plasticos",
            to_node="enrichment",
            delegated_action=Action.ENRICH,
            scope=("enrich",),
        )
        assert len(d2.delegation_chain) == 2
        assert len(d2.hop_trace) == 2
        assert d2.lineage.generation == 2
        assert d2.lineage.root_id == base_packet.packet_id


# ── Serialization ──


class TestSerialization:
    def test_roundtrip(self, base_packet):
        wire = base_packet.to_wire()
        restored = PacketEnvelope.from_wire(wire)
        assert restored.packet_id == base_packet.packet_id
        assert restored.payload == base_packet.payload
        assert restored.verify_integrity()

    def test_wire_is_json_serializable(self, base_packet):
        wire = base_packet.to_wire()
        s = json.dumps(wire)
        assert isinstance(s, str)


# ── Chassis Bridge ──


class TestChassisBridge:
    def test_inflate(self):
        pkt = inflate_ingress(
            action="match",
            payload={"q": "test"},
            tenant="acme",
            trace_id="tr-1",
        )
        assert pkt.packet_type == PacketType.REQUEST
        assert pkt.action == Action.MATCH
        assert pkt.tenant.actor == "acme"
        assert pkt.verify_integrity()

    def test_deflate(self, base_packet):
        resp = deflate_egress(
            request=base_packet,
            engine_data={"matches": [1, 2, 3]},
            processing_ms=42.5,
            engine_version="1.0.0",
            responding_node="match-engine",
        )
        assert resp.packet_type == PacketType.RESPONSE
        assert resp.payload["status"] == "success"
        assert base_packet.packet_id in resp.lineage.parent_ids
        assert resp.verify_integrity()

    def test_deflate_adds_hop(self, base_packet):
        resp = deflate_egress(
            request=base_packet,
            engine_data={},
            processing_ms=10.0,
            engine_version="1.0.0",
            responding_node="match-engine",
        )
        assert len(resp.hop_trace) == 1
        assert resp.hop_trace[0].node_id == "match-engine"


# ── Tenant Context ──


class TestTenantContext:
    def test_originator_defaults_to_actor(self):
        pkt = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.QUERY,
            source_node="x",
            actor_tenant="t1",
            payload={},
            trace_id="t",
        )
        assert pkt.tenant.originator == "t1"

    def test_multi_tenant_delegation_preserves_originator(self, base_packet):
        d = delegate_to_node(
            source_packet=base_packet,
            from_node="agent",
            to_node="other-engine",
            delegated_action=Action.ENRICH,
            scope=("enrich",),
        )
        assert d.tenant.originator == "acme_recycling"
        assert d.tenant.on_behalf_of == "acme_recycling"
