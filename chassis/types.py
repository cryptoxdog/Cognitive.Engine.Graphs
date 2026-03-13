"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api]
tags: [chassis, types, pydantic]
owner: platform-team
status: active
--- /L9_META ---

Shared types for the L9 Constellation Runtime v1.0.0."""

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass

SNAKE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


def _uid() -> str:
    return str(uuid.uuid4())


def _now_ms() -> float:
    return time.time() * 1000


@dataclass
class TraceEntry:
    node: str
    action: str
    status: str
    timestamp: str | None = None
    latency_ms: float | None = None

    def to_dict(self) -> dict:
        d: dict[str, str | float] = {"node": self.node, "action": self.action, "status": self.status}
        if self.timestamp is not None:
            d["timestamp"] = self.timestamp
        if self.latency_ms is not None:
            d["latency_ms"] = self.latency_ms
        return d


@dataclass
class PacketEnvelope:
    packet_id: str
    domain: str
    action: str
    payload: dict
    trace: list
    trace_id: str | None = None
    correlation_id: str | None = None
    metadata: dict | None = None
    tenant: dict | None = None
    permissions: list | None = None
    content_hash: str | None = None

    def compute_hash(self):
        raw = json.dumps({"domain": self.domain, "action": self.action, "payload": self.payload}, sort_keys=True)
        self.content_hash = hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        d = {
            "packet_id": self.packet_id,
            "domain": self.domain,
            "action": self.action,
            "payload": self.payload,
            "trace": [t.to_dict() if isinstance(t, TraceEntry) else t for t in self.trace],
        }
        for k in ("trace_id", "correlation_id", "metadata", "tenant", "permissions", "content_hash"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


def normalize_packet(request: dict) -> PacketEnvelope:
    pkt = PacketEnvelope(
        packet_id=request.get("packet_id", _uid()),
        domain=request["domain"],
        action=request["action"],
        payload=request.get("payload", {}),
        trace=list(request.get("trace", [])),
        trace_id=request.get("trace_id", _uid()),
        correlation_id=request.get("correlation_id"),
        metadata=request.get("metadata"),
        tenant=request.get("tenant"),
        permissions=request.get("permissions"),
    )
    pkt.compute_hash()
    return pkt


class TerminalResult:
    """Wraps a final result returned by a node handler."""

    def __init__(self, data: dict, status: str = "success"):
        self.data = data
        self.status = status


class ConstellationError(Exception):
    def __init__(self, message: str, status: str = "error"):
        super().__init__(message)
        self.status = status
