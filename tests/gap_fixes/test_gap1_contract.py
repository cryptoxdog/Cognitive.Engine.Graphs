"""
Tests for GAP-1: contract_enforcement.py
"""

from __future__ import annotations

import pytest

from engine.contract_enforcement import (
    ContractViolationError,
    build_graph_sync_packet,
    build_schema_proposal_packet,
    enforce_packet_envelope,
)


def test_bare_dict_is_rejected() -> None:
    with pytest.raises(ContractViolationError):
        enforce_packet_envelope({"entity_type": "account", "batch": []}, expected_type="graph_sync")


def test_type_mismatch_raises() -> None:
    pkt = build_graph_sync_packet(tenant_id="t1", entity_type="account", batch=[{"id": "1"}])
    with pytest.raises(ContractViolationError, match="mismatch"):
        enforce_packet_envelope(pkt, expected_type="enrich_request")


def test_valid_graph_sync_passes() -> None:
    pkt = build_graph_sync_packet(tenant_id="t1", entity_type="account", batch=[{"id": "1"}])
    result = enforce_packet_envelope(pkt, expected_type="graph_sync")
    assert result["packet_type"] == "graph_sync"
    assert result["content_hash"]
    assert result["envelope_hash"]


def test_schema_proposal_allowed() -> None:
    pkt = build_schema_proposal_packet(
        tenant_id="t1",
        proposed_fields=[{"name": "facility_tier", "type": "string"}],
    )
    result = enforce_packet_envelope(pkt, expected_type="schema_proposal")
    assert result["packet_id"].startswith("sp_")


def test_tampered_content_hash_rejected() -> None:
    pkt = build_graph_sync_packet(tenant_id="t1", entity_type="account", batch=[{"id": "1"}])
    pkt["content_hash"] = "deadbeef"
    with pytest.raises(ContractViolationError, match="content_hash mismatch"):
        enforce_packet_envelope(pkt, expected_type="graph_sync")
