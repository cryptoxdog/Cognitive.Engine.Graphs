"""
--- L9_META ---
l9_schema: 1
origin: gap-fix
engine: graph
layer: [graph]
tags: [return-channel, enrich, graph, inference]
owner: engine-team
status: active
--- /L9_META ---

engine/graph_return_channel.py

GAP-2 FIX: GRAPH → ENRICH return channel.
Carries inference results from graph engine back to enrichment pipeline.
Enforces PacketEnvelope contract and confidence threshold on every submit.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
import uuid
from typing import Any

from engine.contract_enforcement import (
    ContractViolationError,
    _content_hash,
    _envelope_hash,
)

logger = logging.getLogger(__name__)

_CONFIDENCE_THRESHOLD = 0.50  # submissions below this are silently dropped


# ── Data model ─────────────────────────────────────────────────────────────────

@dataclasses.dataclass(frozen=True)
class InferenceTarget:
    entity_id: str
    field_name: str
    inferred_value: Any
    source_confidence: float
    rule_id: str
    tenant_id: str


# ── Envelope shape ─────────────────────────────────────────────────────────────

@dataclasses.dataclass
class GraphInferenceEnvelope:
    packet_id: str
    tenant_id: str
    inference_outputs: list[dict[str, Any]]
    content_hash: str
    envelope_hash: str


def build_graph_inference_result_envelope(
    tenant_id: str,
    inference_outputs: list[dict[str, Any]],
) -> GraphInferenceEnvelope:
    payload = inference_outputs
    ch = _content_hash(payload)
    skeleton: dict[str, Any] = {
        "packet_id": f"gir_{uuid.uuid4().hex}",
        "tenant_id": tenant_id,
        "inference_outputs": payload,
        "content_hash": ch,
    }
    eh = _envelope_hash(skeleton)
    return GraphInferenceEnvelope(
        packet_id=skeleton["packet_id"],
        tenant_id=tenant_id,
        inference_outputs=payload,
        content_hash=ch,
        envelope_hash=eh,
    )


def _verify_envelope(env: GraphInferenceEnvelope) -> None:
    """Raise ContractViolationError if hashes are invalid."""
    expected_ch = _content_hash(env.inference_outputs)
    if env.content_hash != expected_ch:
        msg = "GraphInferenceEnvelope content_hash mismatch — packet tampered"
        raise ContractViolationError(msg)
    skeleton: dict[str, Any] = {
        "packet_id": env.packet_id,
        "tenant_id": env.tenant_id,
        "inference_outputs": env.inference_outputs,
        "content_hash": env.content_hash,
    }
    expected_eh = _envelope_hash(skeleton)
    if env.envelope_hash != expected_eh:
        msg = "GraphInferenceEnvelope envelope_hash mismatch — packet tampered"
        raise ContractViolationError(msg)


# ── Channel ────────────────────────────────────────────────────────────────────

class GraphToEnrichReturnChannel:
    """
    Singleton async channel.
    Graph engine submits; enrichment pipeline drains.
    """

    _instance: GraphToEnrichReturnChannel | None = None

    def __init__(self) -> None:
        self._queue: asyncio.Queue[InferenceTarget] = asyncio.Queue()

    @classmethod
    def get_instance(cls) -> GraphToEnrichReturnChannel:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    async def submit(self, envelope: GraphInferenceEnvelope) -> int:
        """
        Validate envelope, filter low-confidence outputs, enqueue targets.
        Returns count of targets enqueued.
        """
        _verify_envelope(envelope)

        count = 0
        for output in envelope.inference_outputs:
            confidence = float(output.get("confidence", 0.0))
            if confidence < _CONFIDENCE_THRESHOLD:
                logger.debug(
                    "graph_return_channel: dropping low-confidence output "
                    "entity=%s field=%s confidence=%.2f",
                    output.get("entity_id"),
                    output.get("field"),
                    confidence,
                )
                continue
            target = InferenceTarget(
                entity_id=str(output["entity_id"]),
                field_name=str(output["field"]),
                inferred_value=output.get("value"),
                source_confidence=confidence,
                rule_id=str(output.get("rule", "unknown")),
                tenant_id=envelope.tenant_id,
            )
            await self._queue.put(target)
            count += 1

        logger.debug(
            "graph_return_channel: enqueued %d targets for tenant=%s",
            count,
            envelope.tenant_id,
        )
        return count

    async def drain(
        self,
        tenant_id: str,
        timeout: float = 0.1,
    ) -> list[InferenceTarget]:
        """
        Non-blocking drain for a specific tenant.
        Returns all queued targets matching tenant_id within timeout.
        """
        results: list[InferenceTarget] = []
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                target = await asyncio.wait_for(self._queue.get(), timeout=remaining)
                if target.tenant_id == tenant_id:
                    results.append(target)
                else:
                    # Put back non-matching items
                    await self._queue.put(target)
                    break
            except asyncio.TimeoutError:
                break
        return results
