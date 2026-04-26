"""
PacketEnvelope invariant contract tests against the JSON schema.

Sources:
  engine/packet/packet_envelope.py — PacketEnvelope, PacketType, content_hash
  engine/packet/chassis_contract.py — inflate_ingress, deflate_egress
  contracts/contract_06.yaml — every packet persisted
  contracts/contract_07.yaml — PacketEnvelope immutability
  contracts/contract_08.yaml — content_hash = SHA-256
"""

import pytest

try:
    from jsonschema import ValidationError, validate
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)

from tests.contracts._constants import KNOWN_ACTIONS, PACKET_REQUIRED_FIELDS


def test_packet_schema_exists(packet_envelope_schema):
    assert packet_envelope_schema.get("type") == "object"


def test_packet_schema_has_dollar_schema(packet_envelope_schema):
    assert "$schema" in packet_envelope_schema


def test_packet_schema_has_title(packet_envelope_schema):
    assert packet_envelope_schema.get("title")


def test_packet_schema_has_examples(packet_envelope_schema):
    assert packet_envelope_schema.get("examples")


def test_packet_schema_additional_properties_false(packet_envelope_schema):
    assert packet_envelope_schema.get("additionalProperties") is False


def test_packet_schema_required_fields(packet_envelope_schema):
    required = set(packet_envelope_schema.get("required", []))
    for field in PACKET_REQUIRED_FIELDS["REQUEST"]:
        assert field in required, f"PacketEnvelope.required must include '{field}'"


def test_packet_schema_has_packet_id_uuid_format(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    pid = props.get("packet_id", {})
    assert pid.get("format") == "uuid"


def test_packet_schema_has_content_hash(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    assert "content_hash" in props


def test_packet_schema_content_hash_is_string(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    ch = props.get("content_hash", {})
    assert ch.get("type") == "string"


def test_packet_schema_packet_type_enum(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    pt = props.get("packet_type", {})
    enum_vals = set(pt.get("enum", []))
    assert {"REQUEST", "RESPONSE"} <= enum_vals


def test_packet_schema_action_enum_covers_all_actions(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    action = props.get("action", {})
    enum_vals = set(action.get("enum", []))
    missing = KNOWN_ACTIONS - enum_vals
    assert not missing, f"PacketEnvelope.action enum missing: {missing}"


def test_packet_schema_has_tenant_field(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    assert "tenant" in props


def test_packet_schema_has_trace_id_field(packet_envelope_schema):
    props = packet_envelope_schema.get("properties", {})
    assert "trace_id" in props


def test_valid_request_packet_validates(packet_envelope_schema):
    instance = {
        "packet_id": "550e8400-e29b-41d4-a716-446655440000",
        "packet_type": "REQUEST",
        "action": "match",
        "tenant": "plasticos",
        "payload": {"query": {"material_type": "HDPE"}},
        "content_hash": "a3f5c8d2e1b4f607c8d9e0a1b2c3d4e5",
        "trace_id": "test-001",
    }
    validate(instance=instance, schema=packet_envelope_schema)


def test_missing_content_hash_fails(packet_envelope_schema):
    instance = {
        "packet_id": "550e8400-e29b-41d4-a716-446655440000",
        "packet_type": "REQUEST",
        "action": "match",
        "tenant": "plasticos",
        "payload": {},
    }
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=packet_envelope_schema)


def test_invalid_packet_type_fails(packet_envelope_schema):
    instance = {
        "packet_id": "550e8400-e29b-41d4-a716-446655440000",
        "packet_type": "INVALID_TYPE",
        "action": "match",
        "tenant": "plasticos",
        "payload": {},
        "content_hash": "abc123def456ghij",
    }
    with pytest.raises(ValidationError):
        validate(instance=instance, schema=packet_envelope_schema)
