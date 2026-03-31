"""
GAP-1 FIX: Strict PacketEnvelope contract enforcement.

Replaces all silent bypass paths with hard ContractViolationError failures.
Every inter-service data flow that previously sent a hand-built dict now
must pass through enforce_packet_envelope() before processing.

Usage:
    from engine.contract_enforcement import enforce_packet_envelope, ContractViolationError

    # In GraphSyncClient (was: sending bare dict)
    envelope = enforce_packet_envelope(raw_payload, expected_type="graph_sync")

    # In any handler boundary:
    enforce_packet_envelope(incoming, expected_type="enrich_request")
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error hierarchy
# ---------------------------------------------------------------------------

class ContractViolationError(RuntimeError):
    """Raised whenever an inter-service packet fails contract validation.

    This is an EXPLICIT HARD FAILURE — never caught and silently swallowed.
    Callers must fix the packet, not catch this error.
    """

    def __init__(self, reason: str, *, packet_id: str | None = None) -> None:
        self.reason = reason
        self.packet_id = packet_id
        msg = f"ContractViolation[{packet_id or 'unknown'}]: {reason}"
        super().__init__(msg)
        logger.error(msg)


# ---------------------------------------------------------------------------
# Allowed packet types — Gap-10 fix: schema_proposal added
# ---------------------------------------------------------------------------

_ALLOWED_PACKET_TYPES: frozenset[str] = frozenset(
    [
        "enrich_request",
        "enrich_result",
        "inference_result",
        "graph_sync",
        "graph_inference_result",   # Gap-2: new type for return channel
        "schema_proposal",          # Gap-10: was missing, caused ValidationError
        "community_export",         # Gap-6: community label export to ENRICH
        "health_check",
        "admin_command",
    ]
)


# ---------------------------------------------------------------------------
# Required fields per packet type
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS: dict[str, list[str]] = {
    "enrich_request": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "entity_id"],
    "enrich_result": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "entity_id", "enriched_fields"],
    "inference_result": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "inference_outputs"],
    "graph_sync": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "entity_type", "batch"],
    "graph_inference_result": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "inference_outputs"],
    "schema_proposal": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "proposed_fields"],
    "community_export": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "communities"],
    "health_check": ["packet_id", "tenant_id"],
    "admin_command": ["packet_id", "tenant_id", "content_hash", "envelope_hash", "subaction"],
}


# ---------------------------------------------------------------------------
# Core enforcement function
# ---------------------------------------------------------------------------

def enforce_packet_envelope(
    packet: Any,
    *,
    expected_type: str,
) -> dict[str, Any]:
    """
    Validate that `packet` is a well-formed PacketEnvelope of `expected_type`.

    Checks:
      1. packet is a dict (or Pydantic model with .model_dump())
      2. packet_type matches expected_type
      3. packet_type is in _ALLOWED_PACKET_TYPES
      4. All required fields for the type are present
      5. content_hash matches SHA-256 of the canonical content payload
      6. envelope_hash is present and non-empty

    Returns the validated dict.
    Raises ContractViolationError on ANY failure — no silent returns.
    """
    # Normalise to dict
    if hasattr(packet, "model_dump"):
        packet = packet.model_dump(mode="python")
    if not isinstance(packet, dict):
        raise ContractViolationError(
            f"Expected a dict or Pydantic model, got {type(packet).__name__}",
        )

    packet_id = packet.get("packet_id", "<no_id>")

    # Type check
    actual_type = packet.get("packet_type") or packet.get("type")
    if actual_type != expected_type:
        raise ContractViolationError(
            f"packet_type mismatch: expected={expected_type!r} got={actual_type!r}",
            packet_id=packet_id,
        )

    if expected_type not in _ALLOWED_PACKET_TYPES:
        raise ContractViolationError(
            f"packet_type={expected_type!r} is not in the allowed set",
            packet_id=packet_id,
        )

    # Required fields
    required = _REQUIRED_FIELDS.get(expected_type, [])
    for field_name in required:
        if field_name not in packet or packet[field_name] is None:
            raise ContractViolationError(
                f"Missing or null required field '{field_name}' for type={expected_type!r}",
                packet_id=packet_id,
            )

    # Content hash verification (when present)
    if "content_hash" in required:
        _verify_content_hash(packet, expected_type, packet_id)

    # Envelope hash must be non-empty
    if "envelope_hash" in required:
        if not packet.get("envelope_hash"):
            raise ContractViolationError(
                "envelope_hash is empty",
                packet_id=packet_id,
            )

    return packet


def _verify_content_hash(
    packet: dict[str, Any],
    packet_type: str,
    packet_id: str,
) -> None:
    """Recompute SHA-256 over the canonical content payload and compare."""
    # Content payload = everything except hash fields and metadata
    _HASH_EXCLUDED = {"content_hash", "envelope_hash", "packet_id", "packet_type",
                      "type", "created_at", "lineage", "tenant_context"}
    content_payload = {k: v for k, v in packet.items() if k not in _HASH_EXCLUDED}
    try:
        payload_bytes = json.dumps(content_payload, sort_keys=True, default=str).encode()
    except (TypeError, ValueError) as exc:
        raise ContractViolationError(
            f"Cannot serialize content payload for hash verification: {exc}",
            packet_id=packet_id,
        ) from exc

    expected_hash = hashlib.sha256(payload_bytes).hexdigest()
    actual_hash = packet.get("content_hash", "")
    if expected_hash != actual_hash:
        raise ContractViolationError(
            f"content_hash mismatch: expected={expected_hash!r} got={actual_hash!r}",
            packet_id=packet_id,
        )


# ---------------------------------------------------------------------------
# GraphSyncClient wrapper — Gap-1 targeted fix
# ---------------------------------------------------------------------------

def build_graph_sync_packet(
    *,
    tenant_id: str,
    entity_type: str,
    batch: list[dict[str, Any]],
    tenant_context: dict[str, Any] | None = None,
    lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a fully contract-compliant graph_sync PacketEnvelope.
    Previously GraphSyncClient sent a bare dict with no hashes.
    Use this factory everywhere instead.
    """
    import uuid, time

    content_payload: dict[str, Any] = {
        "entity_type": entity_type,
        "batch": batch,
    }
    if tenant_context:
        content_payload["tenant_context"] = tenant_context

    payload_bytes = json.dumps(content_payload, sort_keys=True, default=str).encode()
    content_hash = hashlib.sha256(payload_bytes).hexdigest()

    packet_id = f"gs_{uuid.uuid4().hex}"
    envelope_meta = {"packet_id": packet_id, "tenant_id": tenant_id, "content_hash": content_hash}
    envelope_hash = hashlib.sha256(
        json.dumps(envelope_meta, sort_keys=True).encode()
    ).hexdigest()

    packet = {
        "packet_id": packet_id,
        "packet_type": "graph_sync",
        "tenant_id": tenant_id,
        "entity_type": entity_type,
        "batch": batch,
        "content_hash": content_hash,
        "envelope_hash": envelope_hash,
        "created_at": time.time(),
    }
    if tenant_context:
        packet["tenant_context"] = tenant_context
    if lineage:
        packet["lineage"] = lineage

    # Self-validate before returning — hard fail if our own factory is broken
    enforce_packet_envelope(packet, expected_type="graph_sync")
    return packet


def build_schema_proposal_packet(
    *,
    tenant_id: str,
    proposed_fields: list[dict[str, Any]],
    provenance: str = "schema_discovery",
) -> dict[str, Any]:
    """
    Gap-4 + Gap-10 fix: Build a valid schema_proposal PacketEnvelope.
    Previously SchemaProposal was computed but never emitted.
    """
    import uuid, time

    content_payload: dict[str, Any] = {
        "proposed_fields": proposed_fields,
        "provenance": provenance,
    }
    payload_bytes = json.dumps(content_payload, sort_keys=True, default=str).encode()
    content_hash = hashlib.sha256(payload_bytes).hexdigest()
    packet_id = f"sp_{uuid.uuid4().hex}"
    envelope_meta = {"packet_id": packet_id, "tenant_id": tenant_id, "content_hash": content_hash}
    envelope_hash = hashlib.sha256(
        json.dumps(envelope_meta, sort_keys=True).encode()
    ).hexdigest()

    packet = {
        "packet_id": packet_id,
        "packet_type": "schema_proposal",
        "tenant_id": tenant_id,
        "proposed_fields": proposed_fields,
        "provenance": provenance,
        "content_hash": content_hash,
        "envelope_hash": envelope_hash,
        "created_at": time.time(),
    }
    enforce_packet_envelope(packet, expected_type="schema_proposal")
    return packet
