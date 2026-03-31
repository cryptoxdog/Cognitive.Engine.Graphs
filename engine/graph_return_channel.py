"""
GAP-2 FIX: GRAPH → ENRICH bidirectional return channel.

Receives GRAPH inference outputs and converts them into deterministic
EnrichmentTarget records that are injected back into the convergence loop
as new Pass N+1 enrichment targets.

Architecture:
  GRAPH.ConvergenceLoop
      └─► GraphInferenceResultEnvelope (PacketEnvelope type=graph_inference_result)
              └─► GraphToEnrichReturnChannel.submit()
                      └─► EnrichmentTargetQueue (async)
                              └─► convergence_controller.run_convergence_loop()
                                      └─► Pass N+1 re-enrichment
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EnrichmentTarget:
    """A re-enrichment directive produced by a GRAPH inference output."""

    entity_id: str
    tenant_id: str
    field_name: str
    # Inference-supplied seed value (may be None — forces discovery)
    seed_value: Any
    # Confidence of the graph inference that produced this target
    source_confidence: float
    # Trace back to the originating PacketEnvelope
    origin_packet_id: str
    origin_inference_rule: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "tenant_id": self.tenant_id,
            "field_name": self.field_name,
            "seed_value": self.seed_value,
            "source_confidence": self.source_confidence,
            "origin_packet_id": self.origin_packet_id,
            "origin_inference_rule": self.origin_inference_rule,
            "created_at": self.created_at,
        }


@dataclass
class GraphInferenceResultEnvelope:
    """
    Minimal representation of a PacketEnvelope[type=graph_inference_result].
    Validated before injection; raises ContractViolationError on any violation.
    """

    packet_id: str
    tenant_id: str
    # List of {entity_id, field, value, confidence, rule} dicts
    inference_outputs: list[dict[str, Any]]
    content_hash: str
    envelope_hash: str

    # Minimum accepted confidence for a GRAPH output to generate a target
    CONFIDENCE_FLOOR: float = 0.55

    def validate(self) -> None:
        """Hard-fail if the envelope does not meet contract requirements."""
        from engine.contract_enforcement import ContractViolationError  # Gap-1 fix

        if not self.packet_id:
            raise ContractViolationError("GraphInferenceResultEnvelope.packet_id is empty")
        if not self.tenant_id:
            raise ContractViolationError("GraphInferenceResultEnvelope.tenant_id is empty")
        if not self.content_hash:
            raise ContractViolationError("GraphInferenceResultEnvelope.content_hash is missing")
        if not self.envelope_hash:
            raise ContractViolationError("GraphInferenceResultEnvelope.envelope_hash is missing")
        # Verify content hash
        payload_bytes = json.dumps(self.inference_outputs, sort_keys=True).encode()
        expected = hashlib.sha256(payload_bytes).hexdigest()
        if expected != self.content_hash:
            raise ContractViolationError(
                f"content_hash mismatch: expected={expected!r} got={self.content_hash!r}",
            )
        if not isinstance(self.inference_outputs, list):
            raise ContractViolationError("inference_outputs must be a list")

    def to_targets(self) -> list[EnrichmentTarget]:
        """Convert validated outputs to EnrichmentTarget records."""
        targets: list[EnrichmentTarget] = []
        for output in self.inference_outputs:
            confidence = float(output.get("confidence", 0.0))
            if confidence < self.CONFIDENCE_FLOOR:
                logger.debug(
                    "Skipping low-confidence inference output (%.3f < %.3f) for entity=%s field=%s",
                    confidence,
                    self.CONFIDENCE_FLOOR,
                    output.get("entity_id"),
                    output.get("field"),
                )
                continue
            targets.append(
                EnrichmentTarget(
                    entity_id=str(output["entity_id"]),
                    tenant_id=self.tenant_id,
                    field_name=str(output["field"]),
                    seed_value=output.get("value"),
                    source_confidence=confidence,
                    origin_packet_id=self.packet_id,
                    origin_inference_rule=str(output.get("rule", "unknown")),
                )
            )
        return targets


# ---------------------------------------------------------------------------
# Return channel — singleton per process
# ---------------------------------------------------------------------------

class GraphToEnrichReturnChannel:
    """
    Async queue that bridges GRAPH inference outputs back to ENRICH.

    Usage (GRAPH side):
        channel = GraphToEnrichReturnChannel.get_instance()
        await channel.submit(envelope)

    Usage (ENRICH convergence_controller side):
        targets = await channel.drain(tenant_id="acme", timeout=0.5)
    """

    _instance: "GraphToEnrichReturnChannel | None" = None

    def __init__(self, maxsize: int = 10_000) -> None:
        # Per-tenant queues: tenant_id → asyncio.Queue[EnrichmentTarget]
        self._queues: dict[str, asyncio.Queue[EnrichmentTarget]] = {}
        self._maxsize = maxsize
        self._submitted: int = 0
        self._drained: int = 0
        self._rejected: int = 0

    @classmethod
    def get_instance(cls) -> "GraphToEnrichReturnChannel":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Test helper — reset the singleton."""
        cls._instance = None

    def _queue_for(self, tenant_id: str) -> asyncio.Queue[EnrichmentTarget]:
        if tenant_id not in self._queues:
            self._queues[tenant_id] = asyncio.Queue(maxsize=self._maxsize)
        return self._queues[tenant_id]

    async def submit(self, envelope: GraphInferenceResultEnvelope) -> int:
        """
        Validate the envelope, convert outputs to targets, enqueue them.
        Returns the number of targets enqueued.
        Hard-raises ContractViolationError if the envelope is invalid (Gap-1).
        """
        envelope.validate()  # raises on violation — no silent bypass
        targets = envelope.to_targets()
        q = self._queue_for(envelope.tenant_id)
        count = 0
        for target in targets:
            try:
                q.put_nowait(target)
                count += 1
            except asyncio.QueueFull:
                self._rejected += 1
                logger.warning(
                    "EnrichmentTargetQueue full for tenant=%s — dropping target entity=%s field=%s",
                    envelope.tenant_id,
                    target.entity_id,
                    target.field_name,
                )
        self._submitted += count
        logger.info(
            "GraphToEnrichReturnChannel: submitted %d targets for tenant=%s (packet=%s)",
            count,
            envelope.tenant_id,
            envelope.packet_id,
        )
        return count

    async def drain(
        self,
        tenant_id: str,
        *,
        timeout: float = 0.1,
        max_targets: int = 500,
    ) -> list[EnrichmentTarget]:
        """
        Non-blocking drain: collect up to max_targets from the tenant queue.
        Returns immediately if the queue is empty after `timeout` seconds.
        Called by convergence_controller at the start of each new pass.
        """
        q = self._queue_for(tenant_id)
        targets: list[EnrichmentTarget] = []
        deadline = time.monotonic() + timeout
        while len(targets) < max_targets:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                target = await asyncio.wait_for(q.get(), timeout=remaining)
                targets.append(target)
                q.task_done()
            except asyncio.TimeoutError:
                break
        self._drained += len(targets)
        if targets:
            logger.info(
                "GraphToEnrichReturnChannel: drained %d targets for tenant=%s",
                len(targets),
                tenant_id,
            )
        return targets

    def stats(self) -> dict[str, int]:
        return {
            "submitted": self._submitted,
            "drained": self._drained,
            "rejected": self._rejected,
            "queue_sizes": {t: q.qsize() for t, q in self._queues.items()},
        }


# ---------------------------------------------------------------------------
# Integration helper: build a valid envelope from raw GRAPH output
# ---------------------------------------------------------------------------

def build_graph_inference_result_envelope(
    *,
    tenant_id: str,
    inference_outputs: list[dict[str, Any]],
) -> GraphInferenceResultEnvelope:
    """
    Factory used by GRAPH ConvergenceLoop to produce a properly hashed envelope.
    Call this instead of constructing GraphInferenceResultEnvelope directly.
    """
    payload_bytes = json.dumps(inference_outputs, sort_keys=True).encode()
    content_hash = hashlib.sha256(payload_bytes).hexdigest()
    packet_id = f"gir_{uuid.uuid4().hex}"
    envelope_payload = {
        "packet_id": packet_id,
        "tenant_id": tenant_id,
        "content_hash": content_hash,
    }
    envelope_hash = hashlib.sha256(
        json.dumps(envelope_payload, sort_keys=True).encode()
    ).hexdigest()
    return GraphInferenceResultEnvelope(
        packet_id=packet_id,
        tenant_id=tenant_id,
        inference_outputs=inference_outputs,
        content_hash=content_hash,
        envelope_hash=envelope_hash,
    )
