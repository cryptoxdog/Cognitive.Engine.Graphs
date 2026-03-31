"""
Unit tests — PacketEnvelope gates/packet_bridge.

Coverage:
  - Packet validation (all required fields)
  - Response wrapping (lineage, tenant propagation, content hash)
  - Intelligence quality metadata passthrough
"""
from __future__ import annotations

import pytest

from engine.gates.packet_bridge import validate_packet, wrap_response


_VALID_PACKET = {
    "header": {
        "packet_id": "pkt_123",
        "tenant_id": "tenant_1",
        "action": "enrich",
        "timestamp": "2026-03-28T22:00:00Z",
    },
    "content_hash": "abc123",
    "payload": {"entity_id": "E001"},
}


class TestValidatePacket:

    def test_valid_packet_passes(self):
        is_valid, error = validate_packet(_VALID_PACKET)
        assert is_valid
        assert error is None

    def test_missing_header(self):
        is_valid, error = validate_packet({"payload": {}})
        assert not is_valid
        assert "header" in error

    def test_missing_packet_id(self):
        packet = {
            "header": {"tenant_id": "t1", "action": "enrich", "timestamp": "2026"},
            "content_hash": "abc",
            "payload": {},
        }
        is_valid, error = validate_packet(packet)
        assert not is_valid
        assert "packet_id" in error

    def test_missing_tenant_id(self):
        packet = {
            "header": {"packet_id": "pkt_1", "action": "enrich", "timestamp": "2026"},
            "content_hash": "abc",
            "payload": {},
        }
        is_valid, error = validate_packet(packet)
        assert not is_valid
        assert "tenant_id" in error

    def test_missing_content_hash(self):
        packet = {
            "header": {
                "packet_id": "pkt_1", "tenant_id": "t1",
                "action": "enrich", "timestamp": "2026"
            },
            "payload": {},
        }
        is_valid, error = validate_packet(packet)
        assert not is_valid
        assert "content_hash" in error

    def test_missing_payload(self):
        packet = {
            "header": {
                "packet_id": "pkt_1", "tenant_id": "t1",
                "action": "enrich", "timestamp": "2026"
            },
            "content_hash": "abc",
        }
        is_valid, error = validate_packet(packet)
        assert not is_valid
        assert "payload" in error


class TestWrapResponse:

    def _make_request(self, lineage=None):
        h = {
            "packet_id": "req_001",
            "tenant_id": "tenant_alpha",
            "action": "enrich",
        }
        if lineage is not None:
            h["lineage"] = lineage
        return {"header": h}

    def test_tenant_id_preserved(self):
        response = wrap_response({"data": "v"}, self._make_request())
        assert response["header"]["tenant_id"] == "tenant_alpha"

    def test_lineage_appended(self):
        response = wrap_response({"data": "v"}, self._make_request(lineage=["pkt_000"]))
        assert response["header"]["lineage"] == ["pkt_000", "req_001"]

    def test_new_packet_id_generated(self):
        response = wrap_response({"data": "v"}, self._make_request())
        assert response["header"]["packet_id"] != "req_001"
        assert response["header"]["packet_id"].startswith("pkt_")

    def test_content_hash_computed(self):
        response = wrap_response({"data": "v"}, self._make_request())
        assert "content_hash" in response
        assert len(response["content_hash"]) == 64  # SHA-256 hex

    def test_content_hash_deterministic(self):
        result = {"data": "value"}
        req = self._make_request()
        r1 = wrap_response(result, req)
        r2 = wrap_response(result, req)
        # Same payload → same content hash (different packet_ids but same hash)
        assert r1["content_hash"] == r2["content_hash"]

    def test_intelligence_quality_included(self):
        iq = {"method": "belief_propagation", "entropy": 0.12}
        response = wrap_response({"data": "v"}, self._make_request(), iq)
        assert response["payload"]["intelligence_quality"]["method"] == "belief_propagation"

    def test_intelligence_quality_absent_when_not_provided(self):
        response = wrap_response({"data": "v"}, self._make_request())
        assert "intelligence_quality" not in response["payload"]

    def test_empty_lineage_starts_from_request_id(self):
        response = wrap_response({"data": "v"}, self._make_request())
        assert "req_001" in response["header"]["lineage"]
