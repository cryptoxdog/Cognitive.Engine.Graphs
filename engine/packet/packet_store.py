"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [packet]
tags: [packet, audit, persistence]
owner: engine-team
status: active
--- /L9_META ---

engine/packet/packet_store.py
PacketStore — async persistence layer for PacketEnvelope audit trail.
Writes immutable request/response pairs to the packet_store PostgreSQL
schema defined in engine/packet/packet_store.sql.

Configuration via environment variables:
  - PACKET_STORE_ENABLED: "true" to enable persistence (default: "false")
  - PACKET_STORE_DSN: PostgreSQL connection string
    e.g. "postgresql://user:pass@host:5432/dbname"
  - PACKET_STORE_POOL_MIN: Minimum pool connections (default: 2)
  - PACKET_STORE_POOL_MAX: Maximum pool connections (default: 10)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from typing import Any

from engine.packet.packet_envelope import PacketEnvelope

logger = logging.getLogger(__name__)

_PACKET_STORE_ENABLED = os.environ.get("PACKET_STORE_ENABLED", "false").lower() == "true"

# ── SQL ──────────────────────────────────────────────────────

_INSERT_PACKET_SQL = """
    INSERT INTO packet_store (
        packet_id, packet_type, action, schema_version,
        source_node, destination_node, reply_to,
        actor_tenant, on_behalf_of, originator_tenant, org_id, user_id,
        envelope,
        content_hash, hash_algorithm, signature, signing_key_id,
        classification, encryption_status,
        trace_id, span_id, correlation_id, created_at, ingested_at,
        parent_ids, root_id, generation, derivation_type,
        intent, compliance_tags, retention_days, redaction_applied,
        audit_required, data_subject_id,
        tags, ttl
    ) VALUES (
        $1, $2, $3, $4,
        $5, $6, $7,
        $8, $9, $10, $11, $12,
        $13,
        $14, $15, $16, $17,
        $18, $19,
        $20, $21, $22, $23, $24,
        $25, $26, $27, $28,
        $29, $30, $31, $32,
        $33, $34,
        $35, $36
    )
    ON CONFLICT (content_hash, actor_tenant) DO NOTHING
"""

_INSERT_LINEAGE_SQL = """
    INSERT INTO lineage_graph (parent_id, child_id, generation, derivation_type, created_at)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (parent_id, child_id) DO NOTHING
"""

_INSERT_HOP_SQL = """
    INSERT INTO hop_trace (packet_id, node_id, action, entered_at, exited_at, status, signature, seq)
    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
"""

_INSERT_DELEGATION_SQL = """
    INSERT INTO delegation_chain (
        packet_id, delegator, delegatee, scope, granted_at, expires_at, proof_hash, seq
    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
"""


# ── Pool Management ──────────────────────────────────────────

class _PoolManager:
    """Lazy-initialised asyncpg connection pool."""

    def __init__(self) -> None:
        self._pool: Any = None

    async def get_pool(self) -> Any:
        """Return the asyncpg pool, creating it on first call."""
        if self._pool is not None:
            return self._pool

        try:
            import asyncpg  # noqa: F811
        except ImportError as exc:
            raise RuntimeError(
                "asyncpg is required for PacketStore persistence. "
                "Install with: pip install asyncpg"
            ) from exc

        dsn = os.environ.get("PACKET_STORE_DSN")
        if not dsn:
            raise RuntimeError(
                "PACKET_STORE_DSN environment variable is required. "
                "Set it to your PostgreSQL connection string."
            )

        min_size = int(os.environ.get("PACKET_STORE_POOL_MIN", "2"))
        max_size = int(os.environ.get("PACKET_STORE_POOL_MAX", "10"))

        self._pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=min_size,
            max_size=max_size,
            command_timeout=30,
        )
        logger.info(
            "PacketStore pool initialized: min=%d max=%d",
            min_size, max_size,
        )
        return self._pool

    async def close(self) -> None:
        """Gracefully close the pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PacketStore pool closed")


_pool_manager = _PoolManager()


# ── Extraction Helpers ───────────────────────────────────────

def _extract_packet_row(packet: PacketEnvelope) -> tuple[Any, ...]:
    """Extract a flat tuple of values from a PacketEnvelope for INSERT."""
    return (
        # identity
        str(packet.packet_id),
        packet.packet_type.value,
        packet.action.value,
        packet.schema_version,
        # routing
        packet.address.source_node,
        packet.address.destination_node,
        packet.address.reply_to,
        # tenant
        packet.tenant.actor,
        packet.tenant.on_behalf_of,
        packet.tenant.originator or packet.tenant.actor,
        packet.tenant.org_id,
        packet.tenant.user_id,
        # payload (full envelope as JSONB)
        json.dumps(packet.to_wire(), default=str),
        # security
        packet.security.content_hash,
        packet.security.hash_algorithm,
        packet.security.signature,
        packet.security.signing_key_id,
        packet.security.classification,
        packet.security.encryption_status,
        # observability
        packet.observability.trace_id,
        packet.observability.span_id,
        packet.observability.correlation_id,
        packet.observability.created_at,
        datetime.now(UTC),  # ingested_at
        # lineage
        [str(pid) for pid in packet.lineage.parent_ids],
        str(packet.lineage.root_id) if packet.lineage.root_id else None,
        packet.lineage.generation,
        packet.lineage.derivation_type,
        # governance
        packet.governance.intent,
        list(packet.governance.compliance_tags),
        packet.governance.retention_days,
        packet.governance.redaction_applied,
        packet.governance.audit_required,
        packet.governance.data_subject_id,
        # labels + expiry
        list(packet.tags),
        packet.ttl,
    )


# ── PacketStore ──────────────────────────────────────────────

class PacketStore:
    """Async persistence layer for PacketEnvelope request/response pairs.

    When PACKET_STORE_ENABLED=true and PACKET_STORE_DSN is set, persists
    packets to the PostgreSQL schema defined in packet_store.sql.
    Otherwise operates in stub mode (debug log only).
    """

    async def persist(
        self,
        request: PacketEnvelope,
        response: PacketEnvelope,
    ) -> None:
        """Persist an immutable request/response PacketEnvelope pair.

        Writes both packets to packet_store, their lineage to lineage_graph,
        hop entries to hop_trace, and delegation links to delegation_chain.
        All writes are wrapped in a single transaction.
        """
        if not _PACKET_STORE_ENABLED:
            logger.debug(
                "PacketStore is disabled. Set PACKET_STORE_ENABLED=true to enable. "
                "packet_id=%s",
                request.packet_id,
            )
            return

        pool = await _pool_manager.get_pool()

        async with pool.acquire() as conn:
            async with conn.transaction():
                # Insert both packets
                for packet in (request, response):
                    row = _extract_packet_row(packet)
                    await conn.execute(_INSERT_PACKET_SQL, *row)

                    # Insert hop trace entries
                    for seq, hop in enumerate(packet.hop_trace):
                        await conn.execute(
                            _INSERT_HOP_SQL,
                            str(packet.packet_id),
                            hop.node_id,
                            hop.action,
                            hop.entered_at,
                            hop.exited_at,
                            hop.status,
                            hop.signature,
                            seq,
                        )

                    # Insert delegation chain entries
                    for seq, deleg in enumerate(packet.delegation_chain):
                        await conn.execute(
                            _INSERT_DELEGATION_SQL,
                            str(packet.packet_id),
                            deleg.delegator,
                            deleg.delegatee,
                            list(deleg.scope),
                            deleg.granted_at,
                            deleg.expires_at,
                            deleg.proof_hash,
                            seq,
                        )

                    # Insert lineage graph edges
                    for parent_id in packet.lineage.parent_ids:
                        await conn.execute(
                            _INSERT_LINEAGE_SQL,
                            str(parent_id),
                            str(packet.packet_id),
                            packet.lineage.generation,
                            packet.lineage.derivation_type,
                            datetime.now(UTC),
                        )

        logger.info(
            "PacketStore persisted pair: request=%s response=%s",
            request.packet_id,
            response.packet_id,
        )

    async def close(self) -> None:
        """Close the underlying connection pool."""
        await _pool_manager.close()


# Module-level singleton — inject into execute_action via dependency
_packet_store = PacketStore()


def get_packet_store() -> PacketStore:
    """Return the module-level PacketStore singleton."""
    return _packet_store
