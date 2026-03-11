"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, chassis]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine/packet/chassis_contract.py.
Target Coverage: 85%+
"""

from __future__ import annotations

import pytest

from engine.packet.chassis_contract import (
    deflate_egress,
    delegate_to_node,
    inflate_ingress,
)
from engine.packet.packet_envelope import (
    Action,
    PacketEnvelope,
    PacketType,
)

# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestInflateIngress:
    """Test inflate_ingress function."""

    def test_creates_request_packet(self) -> None:
        """inflate_ingress creates a REQUEST PacketEnvelope."""
        packet = inflate_ingress(
            action="match",
            payload={"query": {"polymer": "HDPE"}},
            tenant="test-tenant",
            trace_id="tr_abc123",
        )
        assert isinstance(packet, PacketEnvelope)
        assert packet.packet_type == PacketType.REQUEST
        assert packet.action == Action("match")
        assert packet.tenant.actor == "test-tenant"
        assert packet.payload["query"]["polymer"] == "HDPE"

    def test_with_all_optional_params(self) -> None:
        """inflate_ingress accepts all optional parameters."""
        packet = inflate_ingress(
            action="sync",
            payload={"batch": []},
            tenant="t1",
            trace_id="tr_1",
            source_node="api-gateway",
            intent="batch_sync",
            classification="external",
            on_behalf_of="admin_user",
            user_id="u_123",
            org_id="org_456",
        )
        assert packet.address.source_node == "api-gateway"
        assert packet.governance.intent == "batch_sync"

    def test_default_source_node_is_chassis(self) -> None:
        """inflate_ingress defaults source_node to 'chassis'."""
        packet = inflate_ingress(
            action="health",
            payload={},
            tenant="t1",
            trace_id="tr_1",
        )
        assert packet.address.source_node == "chassis"

    def test_trace_id_preserved(self) -> None:
        """inflate_ingress sets trace_id in observability."""
        packet = inflate_ingress(
            action="match",
            payload={},
            tenant="t1",
            trace_id="my_trace",
        )
        assert packet.observability.trace_id == "my_trace"


@pytest.mark.unit
class TestDeflateEgress:
    """Test deflate_egress function."""

    def test_creates_response_from_request(self) -> None:
        """deflate_egress creates a RESPONSE derived from request."""
        request = inflate_ingress(
            action="match",
            payload={"q": "v"},
            tenant="t1",
            trace_id="tr_1",
        )
        response = deflate_egress(
            request=request,
            engine_data={"candidates": [{"id": "c1", "score": 0.95}]},
            status="success",
            processing_ms=42.5,
            responding_node="graph-engine-1",
        )
        assert response.packet_type == PacketType.RESPONSE
        assert response.payload["status"] == "success"
        assert response.payload["data"]["candidates"][0]["score"] == pytest.approx(0.95)
        assert response.payload["meta"]["execution_ms"] == pytest.approx(42.5)

    def test_preserves_trace_id(self) -> None:
        """deflate_egress preserves trace_id from request."""
        request = inflate_ingress(
            action="sync",
            payload={},
            tenant="t1",
            trace_id="tr_preserve",
        )
        response = deflate_egress(
            request=request,
            engine_data={},
            processing_ms=1.0,
            responding_node="node1",
        )
        assert response.payload["meta"]["trace_id"] == "tr_preserve"

    def test_includes_processing_ms(self) -> None:
        """deflate_egress includes processing_ms in meta."""
        request = inflate_ingress(
            action="admin",
            payload={},
            tenant="t1",
            trace_id="tr_1",
        )
        response = deflate_egress(
            request=request,
            engine_data={},
            processing_ms=123.456,
            responding_node="node1",
        )
        assert response.payload["meta"]["execution_ms"] == pytest.approx(123.456)


@pytest.mark.unit
class TestDelegateToNode:
    """Test delegate_to_node function."""

    def test_creates_delegation_packet(self) -> None:
        """delegate_to_node creates a DELEGATION packet."""
        source = inflate_ingress(
            action="match",
            payload={"key": "val"},
            tenant="t1",
            trace_id="tr_1",
        )
        delegation = delegate_to_node(
            source_packet=source,
            from_node="graph-engine",
            to_node="enrich-engine",
            delegated_action=Action("enrich"),
            scope=("entity_enrichment",),
        )
        assert delegation.packet_type == PacketType.DELEGATION
        assert delegation.action == Action("enrich")
        assert delegation.address.source_node == "graph-engine"
        assert delegation.address.destination_node == "enrich-engine"

    def test_copies_tenant_context(self) -> None:
        """delegate_to_node preserves tenant from source packet."""
        source = inflate_ingress(
            action="match",
            payload={},
            tenant="original_tenant",
            trace_id="tr_1",
        )
        delegation = delegate_to_node(
            source_packet=source,
            from_node="a",
            to_node="b",
            delegated_action=Action("sync"),
            scope=("data_sync",),
        )
        assert delegation.tenant.actor == "original_tenant"

    def test_sets_audit_required(self) -> None:
        """delegate_to_node sets audit_required=True in governance."""
        source = inflate_ingress(
            action="match",
            payload={},
            tenant="t1",
            trace_id="tr_1",
        )
        delegation = delegate_to_node(
            source_packet=source,
            from_node="a",
            to_node="b",
            delegated_action=Action("admin"),
            scope=("admin_ops",),
        )
        assert delegation.governance.audit_required is True

    def test_payload_override(self) -> None:
        """delegate_to_node uses payload_override when provided."""
        source = inflate_ingress(
            action="match",
            payload={"original": True},
            tenant="t1",
            trace_id="tr_1",
        )
        delegation = delegate_to_node(
            source_packet=source,
            from_node="a",
            to_node="b",
            delegated_action=Action("enrich"),
            scope=("enrich",),
            payload_override={"overridden": True},
        )
        assert delegation.payload == {"overridden": True}
