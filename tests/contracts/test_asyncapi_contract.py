"""
AsyncAPI contract tests.

Sources:
  engine/packet/packet_envelope.py:PacketType
  engine/packet/chassis_contract.py:inflate_ingress, deflate_egress
  chassis/actions.py:execute_action() — request -> persist lifecycle
"""

from tests.contracts._constants import KNOWN_ACTIONS


def test_asyncapi_version(asyncapi_spec):
    assert asyncapi_spec.get("asyncapi") == "3.0.0"


def test_asyncapi_has_info(asyncapi_spec):
    assert "info" in asyncapi_spec
    assert asyncapi_spec["info"].get("title")
    assert asyncapi_spec["info"].get("version")


def test_asyncapi_has_channels(asyncapi_spec):
    assert "channels" in asyncapi_spec
    assert len(asyncapi_spec["channels"]) > 0


def test_ingress_channel_defined(asyncapi_spec):
    assert "chassis.request.ingress" in asyncapi_spec["channels"]


def test_egress_channel_defined(asyncapi_spec):
    assert "chassis.response.egress" in asyncapi_spec["channels"]


def test_audit_persist_channel_defined(asyncapi_spec):
    assert "engine.audit.persist" in asyncapi_spec["channels"]


def test_ingress_channel_has_message(asyncapi_spec):
    ch = asyncapi_spec["channels"]["chassis.request.ingress"]
    assert ch.get("messages")


def test_ingress_message_action_enum_coverage(asyncapi_spec):
    ch = asyncapi_spec["channels"]["chassis.request.ingress"]
    msg = next(iter(ch["messages"].values()))
    payload = msg.get("payload", {})
    action_prop = payload.get("properties", {}).get("action", {})
    enum_vals = set(action_prop.get("enum", []))
    missing = KNOWN_ACTIONS - enum_vals
    assert not missing, f"asyncapi.yaml ingress message.action enum missing: {missing}"


def test_asyncapi_no_external_broker_note(asyncapi_spec):
    info_desc = asyncapi_spec.get("info", {}).get("description", "")
    assert (
        "broker" in info_desc.lower()
        or "synchronous" in info_desc.lower()
        or "no external" in info_desc.lower()
        or "not use" in info_desc.lower()
    )
