"""
Tests for engine/packet_bridge.py.

Verifies:
- build_request_packet creates valid TransportPacket
- build_request_packet raises on missing trace_id
- extract_payload extracts payload from TransportPacket
"""

from __future__ import annotations

import pytest

pytest.importorskip("constellation_node_sdk", reason="constellation-node-sdk not installed")

from engine.packet_bridge import build_request_packet, extract_payload


def test_build_request_packet_valid():
    """build_request_packet creates a TransportPacket with correct fields."""
    packet = build_request_packet(
        action="graph-query",
        payload={"cypher": "MATCH (n) RETURN n LIMIT 1"},
        tenant="test-tenant",
        trace_id="trace-12345",
    )
    assert packet.header.action == "graph-query"
    assert packet.payload == {"cypher": "MATCH (n) RETURN n LIMIT 1"}
    assert packet.tenant.actor == "test-tenant"
    assert packet.header.trace_id == "trace-12345"


def test_build_request_packet_raises_on_empty_trace_id():
    """build_request_packet raises ValueError when trace_id is empty."""
    with pytest.raises(ValueError, match="trace_id must be provided"):
        build_request_packet(
            action="graph-query",
            payload={},
            tenant="test-tenant",
            trace_id="",
        )


def test_extract_payload_extracts_payload():
    """extract_payload extracts payload from a TransportPacket."""
    packet = build_request_packet(
        action="response",
        payload={"result": [1, 2, 3]},
        tenant="test-tenant",
        trace_id="trace-12345",
    )
    result = extract_payload(packet)
    assert result == {"result": [1, 2, 3]}
