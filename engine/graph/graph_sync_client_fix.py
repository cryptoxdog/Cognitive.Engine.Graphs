"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [graph]
tags: [graph, graph-sync-client-fix]
owner: engine-team
status: active
--- /L9_META ---



GAP-1 FIX: Replace the hand-built dict in GraphSyncClient with a canonical
PacketEnvelope.  Eliminates the silent bypass of content_hash, envelope_hash,
PacketLineage, and TenantContext.

Usage: Drop this over GraphSyncClient in graph/sync/client.py and update
the import at the call site.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol

from engine.contract_enforcement import (
    ContractViolationError,
    build_graph_sync_packet,
    enforce_packet_envelope,
)

logger = logging.getLogger(__name__)

BatchRow = dict[str, Any]
Batch = list[BatchRow]


class WriteTransaction(Protocol):
    async def run(self, query: str, /, **parameters: Any) -> Any: ...


class GraphWriteDriver(Protocol):
    async def execute_write(self, fn: Callable[..., Any], /, **kwargs: Any) -> Any: ...


class GraphSyncClient:
    """
    Production-hardened replacement for the original GraphSyncClient.

    All outbound payloads are canonical PacketEnvelopes with:
      - content_hash (SHA-256 of sorted content JSON)
      - envelope_hash (SHA-256 of packet_id + content_hash + timestamp)
      - PacketLineage (origin_service, correlation_id, hop_count)
      - TenantContext (tenant_id, tenant_tier)

    Any attempt to send a malformed or tampered envelope raises
    ContractViolationError — hard fail, no silent degradation.
    """

    def __init__(self, neo4j_driver: GraphWriteDriver, tenant_id: str, tenant_tier: str = "unknown") -> None:
        self._driver = neo4j_driver
        self._tenant_id = tenant_id
        self._tenant_tier = tenant_tier

    def _build_envelope(
        self,
        entity_type: str,
        batch: Batch,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Build and validate a PacketEnvelope before sending."""
        tenant_context = {
            "tenant_id": self._tenant_id,
            "tenant_tier": self._tenant_tier,
        }
        lineage = {
            "origin_service": "graph_sync_client",
            "hop_count": 0,
        }
        if correlation_id is not None:
            lineage["correlation_id"] = correlation_id

        packet = build_graph_sync_packet(
            tenant_id=self._tenant_id,
            entity_type=entity_type,
            batch=batch,
            tenant_context=tenant_context,
            lineage=lineage,
        )
        # Enforce immediately — hard fail on violation
        return enforce_packet_envelope(packet, expected_type="graph_sync")

    async def sync_entities(
        self,
        entity_type: str,
        batch: Batch,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Sync a batch of enriched entities to Neo4j via a validated envelope.
        Raises ContractViolationError if the envelope fails validation.
        """
        if not batch:
            return {"status": "ok", "synced": 0}

        envelope = self._build_envelope(entity_type, batch, correlation_id)

        try:
            await self._driver.execute_write(
                _write_batch_tx,
                entity_type=entity_type,
                batch=envelope["content"]["batch"],
                tenant_id=self._tenant_id,
                packet_id=envelope["packet_id"],
            )
            logger.info(
                "GraphSyncClient: synced %d %s entities tenant=%s packet_id=%s",
                len(batch),
                entity_type,
                self._tenant_id,
                envelope["packet_id"],
            )
            return {"status": "ok", "synced": len(batch), "packet_id": envelope["packet_id"]}

        except ContractViolationError:
            raise
        except Exception:
            logger.exception("GraphSyncClient: write failed for packet_id=%s", envelope.get("packet_id"))
            raise


async def _write_batch_tx(
    tx: WriteTransaction,
    *,
    entity_type: str,
    batch: Batch,
    tenant_id: str,
    packet_id: str,
) -> None:
    """Neo4j write transaction — MERGE on entity_id, set all properties."""
    cypher = """
    UNWIND $batch AS row
    MERGE (n {entity_id: row.entity_id, tenant: $tenant})
    SET n += row.properties
    SET n.last_sync_packet = $packet_id
    SET n:Entity
    """
    await tx.run(cypher, batch=batch, tenant=tenant_id, packet_id=packet_id)
