"""
TransportPacket invariant contract tests against the JSON schema.

Sources:
  constellation_node_sdk.TransportPacket — canonical wire format
  engine/packet/chassis_contract.py — inflate_ingress, deflate_egress
  contracts/contract_06.yaml — every packet persisted
  contracts/contract_07.yaml — TransportPacket immutability (frozen=True)
  contracts/contract_08.yaml — payload_hash = SHA-256
"""

import pytest

try:
    from jsonschema import ValidationError, validate
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)

from tests.contracts._constants import KNOWN_ACTIONS


def test_packet_schema_exists(packet_envelope_schema):
    assert packet_envelope_schema.get("type") == "object"


def test_packet_schema_has_dollar_schema(packet_envelope_schema):
    assert "$schema" in packet_envelope_schema


def test_packet_schema_has_title(packet_envelope_schema):
    title = packet_envelope_schema.get("title", "")
    assert "TransportPacket" in title


def test_packet_schema_has_examples(packet_envelope_schema):
    assert packet_envelope_schema.get("examples")


def test_packet_schema_has_header_section(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    assert "header" in props, "Schema must have a 'header' section"


def test_packet_schema_required_sections(packet_envelope_schema):
    required = set(packet_envelope_schema.get("required", []))
    for section in ("header", "address", "tenant", "payload", "security", "lineage"):
        assert section in required, f"Schema.required must include '{section}'"


def test_packet_schema_header_has_packet_id(packet_envelope_schema):
    header = packet_envelope_schema.get("properties", {}).get("header", {})
    header_props = header.get("properties", {})
    pid = header_props.get("packet_id", {})
    assert pid.get("format") == "uuid"


def test_packet_schema_has_payload_hash(packet_envelope_schema):
    security = packet_envelope_schema.get("properties", {}).get("security", {})
    sec_props = security.get("properties", {})
    assert "payload_hash" in sec_props, "Security must include payload_hash"


def test_packet_schema_payload_hash_is_string(packet_envelope_schema):
    security = packet_envelope_schema.get("properties", {}).get("security", {})
    sec_props = security.get("properties", {})
    ph = sec_props.get("payload_hash", {})
    assert ph.get("type") == "string"


def test_packet_schema_header_packet_type_enum(packet_envelope_schema):
    header = packet_envelope_schema.get("properties", {}).get("header", {})
    header_props = header.get("properties", {})
    pt = header_props.get("packet_type", {})
    enum_vals = set(pt.get("enum", []))
    assert {"request", "response"} <= enum_vals


def test_packet_schema_header_action_enum_covers_all(packet_envelope_schema):
    header = packet_envelope_schema.get("properties", {}).get("header", {})
    header_props = header.get("properties", {})
    action = header_props.get("action", {})
    enum_vals = set(action.get("enum", []))
    missing = KNOWN_ACTIONS - enum_vals
    assert not missing, f"header.action enum missing: {missing}"


def test_packet_schema_has_tenant_section(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    assert "tenant" in props


def test_packet_schema_tenant_has_actor(packet_envelope_schema):
    tenant = packet_envelope_schema.get("properties", {}).get("tenant", {})
    tenant_props = tenant.get("properties", {})
    assert "actor" in tenant_props, "Tenant section must include 'actor'"


def test_packet_schema_has_lineage(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    assert "lineage" in props, "Schema must have lineage section"


def test_valid_transport_packet_validates(packet_envelope_schema):
    instance = {
        "header": {
            "packet_id": "550e8400-e29b-41d4-a716-446655440000",
            "packet_type": "request",
            "action": "match",
            "trace_id": "test-001",
            "created_at": "2026-04-26T12:00:00Z",
        },
        "address": {
            "source_node": "client",
            "destination_node": "gate",
            "reply_to": "client",
        },
        "tenant": {"actor": "plasticos", "originator": "plasticos"},
        "payload": {"query": {"material_type": "HDPE"}},
        "security": {
            "payload_hash": "a3f5c8d2e1b4f607c8d9e0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8001a00",
            "transport_hash": "b4c5d6e7f80011a3f5c8d2e1b4f607c8d9e0a1b2c3d4e5f6a7b8c9d0e1f2a300",
        },
        "lineage": {
            "root_id": "550e8400-e29b-41d4-a716-446655440000",
            "generation": 0,
        },
    }
    validate(instance=instance, schema=packet_envelope_schema)


def test_missing_security_fails(packet_envelope_schema):
    instance = {
        "header": {
            "packet_id": "550e8400-e29b-41d4-a716-446655440000",
            "packet_type": "request",
            "action": "match",
        },
        "address": {
            "source_node": "client",
            "destination_node": "gate",
            "reply_to": "client",
        },
        "tenant": {"actor": "plasticos"},
        "payload": {},
        "lineage": {
            "root_id": "550e8400-e29b-41d4-a716-446655440000",
            "generation": 0,
        },
    }
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=packet_envelope_schema)


def test_invalid_packet_type_fails(packet_envelope_schema):
    instance = {
        "header": {
            "packet_id": "550e8400-e29b-41d4-a716-446655440000",
            "packet_type": "INVALID_TYPE",
            "action": "match",
        },
        "address": {
            "source_node": "client",
            "destination_node": "gate",
            "reply_to": "client",
        },
        "tenant": {"actor": "plasticos"},
        "payload": {},
        "security": {
            "payload_hash": "a3f5c8d2e1b4f607c8d9e0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8001a00",
            "transport_hash": "b4c5d6e7f80011a3f5c8d2e1b4f607c8d9e0a1b2c3d4e5f6a7b8c9d0e1f2a300",
        },
        "lineage": {
            "root_id": "550e8400-e29b-41d4-a716-446655440000",
            "generation": 0,
        },
    }
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=packet_envelope_schema)
