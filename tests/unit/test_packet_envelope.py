# tests/test_packet_envelope.py
"""
Tests for engine.packet — PacketEnvelope v3.0.0 + chassis_contract bridge.

Relocated from engine/packet/test_packet_envelope.py (misplaced).
Fixed imports: uses fully qualified engine.packet.* paths.

Covers:
- Immutability (frozen model, extra=forbid)
- Content hash integrity + determinism
- Derivation (lineage, generation, root_id, hash recompute)
- Delegation chain (single + stacked)
- Serialization roundtrip (to_wire / from_wire)
- Chassis bridge (inflate_ingress, deflate_egress, delegate_to_node)
- Tenant context (originator defaults, delegation preservation)
- Factory (create_packet) edge cases
- PacketType and Action enum coverage
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from engine.packet.chassis_contract import deflate_egress, delegate_to_node, inflate_ingress
from engine.packet.packet_envelope import (
    Action,
    PacketAddress,
    PacketEnvelope,
    PacketType,
    TenantContext,
    _compute_hash,
    create_packet,
)

# ── Fixtures ──────────────────────────────────────────────


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


@pytest.fixture
def minimal_packet():
    return create_packet(
        packet_type=PacketType.REQUEST,
        action=Action.QUERY,
        source_node="test-node",
        actor_tenant="test-tenant",
        payload={"q": "hello"},
        trace_id="t-001",
    )


# ── Immutability ──────────────────────────────────────────


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

    def test_security_frozen(self, base_packet):
        with pytest.raises(Exception):
            base_packet.security.content_hash = "tampered"

    def test_observability_frozen(self, base_packet):
        with pytest.raises(Exception):
            base_packet.observability.trace_id = "replaced"

    def test_lineage_frozen(self, base_packet):
        with pytest.raises(Exception):
            base_packet.lineage.generation = 999


# ── Integrity ─────────────────────────────────────────────


class TestIntegrity:
    def test_hash_matches(self, base_packet):
        assert base_packet.verify_integrity()

    def test_hash_deterministic(self, base_packet):
        h1 = _compute_hash(
            base_packet.packet_type,
            base_packet.action,
            base_packet.payload,
            base_packet.tenant,
            base_packet.address,
        )
        h2 = _compute_hash(
            base_packet.packet_type,
            base_packet.action,
            base_packet.payload,
            base_packet.tenant,
            base_packet.address,
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

    def test_different_action_different_hash(self):
        p1 = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="x",
            actor_tenant="t",
            payload={"k": "v"},
            trace_id="t",
        )
        p2 = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.SYNC,
            source_node="x",
            actor_tenant="t",
            payload={"k": "v"},
            trace_id="t",
        )
        assert p1.security.content_hash != p2.security.content_hash

    def test_hash_is_sha256_hex(self, base_packet):
        h = base_packet.security.content_hash
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# ── Derivation ────────────────────────────────────────────


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

    def test_derive_preserves_classification(self, base_packet):
        child = base_packet.derive(payload={"x": 1})
        assert child.security.classification == base_packet.security.classification

    def test_derive_preserves_correlation_id(self, base_packet):
        child = base_packet.derive(payload={"x": 1})
        assert child.observability.correlation_id == base_packet.observability.correlation_id

    def test_derive_sets_derivation_type(self, base_packet):
        child = base_packet.derive(payload={"x": 1}, derivation_type="fan_out")
        assert child.lineage.derivation_type == "fan_out"

    def test_derive_can_override_tags(self, base_packet):
        child = base_packet.derive(payload={"x": 1}, tags=("enriched", "v2"))
        assert child.tags == ("enriched", "v2")


# ── Delegation ────────────────────────────────────────────


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

    def test_delegation_sets_audit_required(self, base_packet):
        delegated = delegate_to_node(
            source_packet=base_packet,
            from_node="a",
            to_node="b",
            delegated_action=Action.ENRICH,
            scope=("enrich",),
        )
        assert delegated.governance.audit_required is True


# ── Serialization ─────────────────────────────────────────


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

    def test_roundtrip_preserves_lineage(self, base_packet):
        child = base_packet.derive(payload={"x": 1})
        wire = child.to_wire()
        restored = PacketEnvelope.from_wire(wire)
        assert restored.lineage.generation == 1
        assert str(base_packet.packet_id) in [str(pid) for pid in restored.lineage.parent_ids]

    def test_roundtrip_preserves_delegation_chain(self, base_packet):
        delegated = delegate_to_node(
            source_packet=base_packet,
            from_node="a",
            to_node="b",
            delegated_action=Action.ENRICH,
            scope=("enrich",),
        )
        wire = delegated.to_wire()
        restored = PacketEnvelope.from_wire(wire)
        assert len(restored.delegation_chain) == 1

    def test_roundtrip_preserves_pii_fields(self, base_packet):
        wire = base_packet.to_wire()
        restored = PacketEnvelope.from_wire(wire)
        assert "contact_email" in restored.security.pii_fields


# ── Chassis Bridge ────────────────────────────────────────


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

    def test_inflate_with_delegation(self):
        pkt = inflate_ingress(
            action="enrich",
            payload={"data": "x"},
            tenant="child_tenant",
            trace_id="tr-2",
            on_behalf_of="parent_tenant",
        )
        assert pkt.tenant.on_behalf_of == "parent_tenant"

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

    def test_deflate_includes_execution_meta(self, base_packet):
        resp = deflate_egress(
            request=base_packet,
            engine_data={},
            processing_ms=55.3,
            engine_version="2.1.0",
            responding_node="engine-a",
        )
        meta = resp.payload["meta"]
        assert meta["execution_ms"] == 55.3
        assert meta["version"] == "2.1.0"


# ── Tenant Context ────────────────────────────────────────


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

    def test_org_and_user_passthrough(self):
        pkt = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="x",
            actor_tenant="t1",
            payload={},
            trace_id="t",
            org_id="org-123",
            user_id="user-456",
        )
        assert pkt.tenant.org_id == "org-123"
        assert pkt.tenant.user_id == "user-456"


# ── Factory Edge Cases ────────────────────────────────────


class TestFactory:
    def test_create_packet_minimal(self):
        pkt = create_packet(
            packet_type=PacketType.EVENT,
            action=Action.HEALTH,
            source_node="monitor",
            actor_tenant="system",
            payload={},
            trace_id="health-1",
        )
        assert pkt.packet_type == PacketType.EVENT
        assert pkt.action == Action.HEALTH
        assert pkt.verify_integrity()
        assert pkt.governance.intent is None

    def test_create_packet_with_ttl(self):
        ttl = datetime(2026, 12, 31, tzinfo=UTC)
        pkt = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="x",
            actor_tenant="t",
            payload={},
            trace_id="t",
            ttl=ttl,
        )
        assert pkt.ttl == ttl

    def test_create_packet_with_tags(self):
        pkt = create_packet(
            packet_type=PacketType.REQUEST,
            action=Action.MATCH,
            source_node="x",
            actor_tenant="t",
            payload={},
            trace_id="t",
            tags=("priority", "hdpe"),
        )
        assert pkt.tags == ("priority", "hdpe")

    def test_schema_version(self, base_packet):
        assert base_packet.schema_version == "3.0.0"


# ── Enum Coverage ─────────────────────────────────────────


class TestEnums:
    def test_all_packet_types_valid(self):
        for pt in PacketType:
            assert isinstance(pt.value, str)

    def test_all_actions_valid(self):
        for a in Action:
            assert isinstance(a.value, str)

    def test_packet_type_from_string(self):
        assert PacketType("request") == PacketType.REQUEST
        assert PacketType("delegation") == PacketType.DELEGATION

    def test_action_from_string(self):
        assert Action("match") == Action.MATCH
        assert Action("enrich") == Action.ENRICH
