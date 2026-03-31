"""
--- L9_META ---
l9_schema: 1
origin: gap-fix
engine: graph
layer: [packet]
tags: [contract, enforcement, packet_envelope, hash]
owner: engine-team
status: active
--- /L9_META ---

engine/contract_enforcement.py

GAP-1 + GAP-10 FIX: Strict PacketEnvelope shape and hash enforcement.

Provides:
  - enforce_packet_envelope(packet, expected_type) — raises ContractViolationError on any violation
  - build_graph_sync_packet(...)  — canonical factory
  - build_schema_proposal_packet(...) — canonical factory
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any


class ContractViolationError(ValueError):
    """Raised when a packet fails contract enforcement."""


# ── Canonical JSON hash ────────────────────────────────────────────────────────

def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _content_hash(payload: Any) -> str:
    return _sha256(_canonical_json(payload))


def _envelope_hash(packet: dict[str, Any]) -> str:
    """Hash entire packet minus the envelope_hash field itself."""
    copy = {k: v for k, v in packet.items() if k != "envelope_hash"}
    return _sha256(_canonical_json(copy))


# ── Enforcement ────────────────────────────────────────────────────────────────

_REQUIRED_FIELDS = {"packet_id", "packet_type", "tenant_id", "payload",
                    "content_hash", "envelope_hash", "created_at"}

_VALID_TYPES = {
    "graph_sync", "enrich_request", "schema_proposal",
    "graph_inference_result", "community_export",
    "request", "response", "event", "command",
}


def enforce_packet_envelope(
    packet: dict[str, Any],
    expected_type: str,
) -> dict[str, Any]:
    """
    Validate packet shape, type, and cryptographic integrity.
    Returns the packet unchanged on success.
    Raises ContractViolationError on any failure.
    """
    if not isinstance(packet, dict):
        msg = f"packet must be a dict, got {type(packet).__name__}"
        raise ContractViolationError(msg)

    missing = _REQUIRED_FIELDS - packet.keys()
    if missing:
        msg = f"packet missing required fields: {sorted(missing)}"
        raise ContractViolationError(msg)

    ptype = packet.get("packet_type")
    if ptype != expected_type:
        msg = f"packet_type mismatch: expected={expected_type!r} got={ptype!r}"
        raise ContractViolationError(msg)

    if ptype not in _VALID_TYPES:
        msg = f"packet_type {ptype!r} is not a registered canonical type"
        raise ContractViolationError(msg)

    # Content hash integrity
    expected_content = _content_hash(packet["payload"])
    if packet["content_hash"] != expected_content:
        msg = f"content_hash mismatch: expected={expected_content[:16]}… got={str(packet['content_hash'])[:16]}…"
        raise ContractViolationError(msg)

    # Envelope hash integrity
    expected_env = _envelope_hash(packet)
    if packet["envelope_hash"] != expected_env:
        msg = f"envelope_hash mismatch: expected={expected_env[:16]}…"
        raise ContractViolationError(msg)

    return packet


# ── Canonical factories ────────────────────────────────────────────────────────

def _base_packet(packet_type: str, tenant_id: str, payload: Any) -> dict[str, Any]:
    pkt: dict[str, Any] = {
        "packet_id": f"pkt_{uuid.uuid4().hex}",
        "packet_type": packet_type,
        "tenant_id": tenant_id,
        "payload": payload,
        "content_hash": _content_hash(payload),
        "envelope_hash": "",  # filled below
        "created_at": time.time(),
    }
    pkt["envelope_hash"] = _envelope_hash(pkt)
    return pkt


def build_graph_sync_packet(
    tenant_id: str,
    entity_type: str,
    batch: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {"entity_type": entity_type, "batch": batch}
    return _base_packet("graph_sync", tenant_id, payload)


def build_schema_proposal_packet(
    tenant_id: str,
    proposed_fields: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {"proposed_fields": proposed_fields}
    pkt = _base_packet("schema_proposal", tenant_id, payload)
    pkt["packet_id"] = f"sp_{uuid.uuid4().hex}"
    # Recompute envelope_hash after packet_id change
    pkt["envelope_hash"] = _envelope_hash(pkt)
    return pkt


def build_graph_inference_result_packet(
    tenant_id: str,
    inference_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    payload = {"inference_outputs": inference_outputs}
    return _base_packet("graph_inference_result", tenant_id, payload)
