"""
redis_stream_adapter.py — GRAPH repo
Stream publish adapter for GRAPH → ENRICH bidirectional loop.

Publishes graph.inference.complete events after every materialization batch
so the EIE GraphInferenceConsumer can feed inferred triples back into
the convergence loop.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from engine.config.settings import Settings

logger = logging.getLogger(__name__)

GRAPH_INFERENCE_STREAM = "graph.inference.complete"
STREAM_MAXLEN = 50_000  # keep last 50k events, approximate trim


class RedisStreamAdapter:
    """Async Redis Streams adapter for GRAPH-side event publishing."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        redis_url = getattr(self._settings, "redis_url", "redis://localhost:6379/0")
        self._client = aioredis.from_url(
            redis_url, encoding="utf-8", decode_responses=True
        )
        logger.info("redis_stream_adapter_connected", extra={"url": redis_url})

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def publish_inference_event(
        self,
        entity_id: str,
        domain: str,
        run_id: str,
        inferred_triples: list[dict[str, Any]],
        materialization_pass: int = 1,
        graph_confidence: float = 0.0,
    ) -> str | None:
        """
        Publish a graph.inference.complete event to Redis Streams.

        Returns the stream message ID on success, None on failure
        (failures are non-fatal — ENRICH degrades gracefully without signals).
        """
        if self._client is None:
            logger.warning("redis_not_connected_skipping_publish")
            return None

        try:
            payload = json.dumps({
                "entity_id": entity_id,
                "domain": domain,
                "run_id": run_id,
                "inferred_triples": inferred_triples,
                "materialization_pass": materialization_pass,
                "graph_confidence": graph_confidence,
            })
            msg_id = await self._client.xadd(
                GRAPH_INFERENCE_STREAM,
                {"payload": payload},
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
        except RedisError as exc:
            logger.warning(
                "inference_event_publish_failed",
                extra={"entity_id": entity_id, "error": str(exc)},
            )
            return None
        else:
            logger.debug(
                "inference_event_published",
                extra={
                    "stream": GRAPH_INFERENCE_STREAM,
                    "entity_id": entity_id,
                    "triples": len(inferred_triples),
                    "msg_id": msg_id,
                },
            )
            return msg_id
