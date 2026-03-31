"""
Integration tests — handler flow: validation + belief rescoring + packet wrapping.

No Neo4j required — uses in-process mocks.
"""
from __future__ import annotations

import pytest

from engine.compliance.validator import validate_enrichment_request, validate_gate_response
from engine.gates.packet_bridge import validate_packet, wrap_response
from engine.scoring.belief_propagation import rescore_candidates


class TestEnrichmentFlow:

    def test_valid_request_passes(self):
        payload = {"entity_id": "MAT_001", "entity_type": "Material", "convergence_depth": 2}
        is_valid, error = validate_enrichment_request(payload)
        assert is_valid
        assert error is None

    def test_invalid_entity_type_rejected(self):
        payload = {"entity_id": "MAT_001", "entity_type": "InvalidType"}
        is_valid, error = validate_enrichment_request(payload)
        assert not is_valid
        assert "InvalidType" in error

    def test_missing_entity_id_rejected(self):
        payload = {"entity_type": "Material"}
        is_valid, error = validate_enrichment_request(payload)
        assert not is_valid
        assert "entity_id" in error

    def test_invalid_convergence_depth_rejected(self):
        payload = {"entity_id": "E1", "entity_type": "Material", "convergence_depth": 99}
        is_valid, error = validate_enrichment_request(payload)
        assert not is_valid
        assert "convergence_depth" in error

    def test_rescoring_integration(self):
        candidates = [
            {"id": "A", "geo": 0.9, "temporal": 0.85, "confidence": 0.7},
            {"id": "B", "geo": 0.95, "temporal": 0.9, "confidence": 0.5},
        ]
        rescored = rescore_candidates(candidates, ["geo", "temporal"])
        assert "belief_score" in rescored[0]
        assert all(0.0 <= c["belief_score"] <= 1.0 for c in rescored)


class TestGateResponseValidation:

    def test_valid_response_passes(self):
        response = {
            "header": {"packet_id": "pkt_123", "status": "COMPLETED"},
            "hop_trace": [],
        }
        is_valid, error = validate_gate_response(response)
        assert is_valid
        assert error is None

    def test_missing_header_fails(self):
        is_valid, error = validate_gate_response({"hop_trace": []})
        assert not is_valid
        assert "header" in error

    def test_missing_hop_trace_fails(self):
        response = {"header": {"packet_id": "pkt_1", "status": "COMPLETED"}}
        is_valid, error = validate_gate_response(response)
        assert not is_valid
        assert "hop_trace" in error

    def test_invalid_hop_trace_type_fails(self):
        response = {
            "header": {"packet_id": "pkt_1", "status": "COMPLETED"},
            "hop_trace": "not_a_list",
        }
        is_valid, error = validate_gate_response(response)
        assert not is_valid


class TestPacketProtocol:

    def test_end_to_end_packet_flow(self):
        request_packet = {
            "header": {
                "packet_id": "req_123",
                "tenant_id": "tenant_alpha",
                "action": "enrich",
                "timestamp": "2026-03-28T22:00:00Z",
            },
            "content_hash": "abc123",
            "payload": {"entity_id": "MAT_001", "entity_type": "Material"},
        }

        is_valid, _ = validate_packet(request_packet)
        assert is_valid

        is_valid, _ = validate_enrichment_request(request_packet["payload"])
        assert is_valid

        handler_result = {
            "matches": [
                {"id": "M001", "belief_score": 0.85},
                {"id": "M002", "belief_score": 0.78},
            ]
        }
        iq = {"method": "entropy_penalized_composite", "dimensions_used": ["geo", "temporal"]}
        response = wrap_response(handler_result, request_packet, iq)

        assert response["header"]["tenant_id"] == "tenant_alpha"
        assert "req_123" in response["header"]["lineage"]
        assert len(response["content_hash"]) == 64
        assert response["payload"]["intelligence_quality"]["method"] == "entropy_penalized_composite"
