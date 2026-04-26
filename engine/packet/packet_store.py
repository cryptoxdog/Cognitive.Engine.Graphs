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
PacketStore — async persistence layer for TransportPacket audit trail
plus outcome_jsonb feedback-loop linkage (migration 0001_outcome_jsonb).
Writes immutable request/response pairs to the packet_store PostgreSQL
schema defined in engine/packet/packet_store.sql.

Uses constellation_node_sdk.TransportPacket as the canonical wire format.

New in this version:
  PacketStore.record_outcome(...)
    -- Writes outcome_jsonb to an existing packet_store row, linking a
       TransactionOutcome node (Neo4j) back to the TransportPacket that
       triggered the match. Called from handle_outcomes() when both
       PACKET_STORE_ENABLED=true and settings.outcome_persistence_enabled=True.
    -- Non-fatal: degrades gracefully on any DB error (log warning, return False).

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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from constellation_node_sdk import TransportPacket

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
# NEW: Outcome feedback-loop linkage
_UPDATE_OUTCOME_SQL = """
    UPDATE packet_store
    SET outcome_jsonb = $1
    WHERE packet_id = $2::uuid
      AND actor_tenant = $3
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
            import asyncpg
        except ImportError as exc:
            raise RuntimeError(
                "asyncpg is required for PacketStore persistence. Install with: pip install asyncpg"
            ) from exc

        dsn = os.environ.get("PACKET_STORE_DSN")
        if not dsn:
            raise RuntimeError(
                "PACKET_STORE_DSN environment variable is required. Set it to your PostgreSQL connection string."
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
            min_size,
            max_size,
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


def _extract_packet_row(packet: TransportPacket) -> tuple[Any, ...]:
    """Extract a flat tuple of values from a TransportPacket for INSERT."""
    hdr = packet.header
    addr = packet.address
    sec = packet.security
    gov = packet.governance
    lin = packet.lineage
    ten = packet.tenant

    parent_ids = [str(lin.parent_id)] if lin.parent_id else []

    return (
        # identity
        str(hdr.packet_id),
        hdr.packet_type,
        hdr.action,
        hdr.schema_version,
        # routing
        addr.source_node,
        addr.destination_node,
        addr.reply_to,
        # tenant
        ten.actor,
        ten.on_behalf_of,
        ten.originator or ten.actor,
        ten.org_id,
        getattr(ten, "user_id", None),
        # payload (full packet as JSONB)
        json.dumps(json.loads(packet.model_dump_json()), default=str),
        # security
        sec.payload_hash,
        "sha256",
        sec.signature,
        sec.signing_key_id,
        sec.classification,
        sec.encryption_status,
        # observability
        hdr.trace_id,
        None,  # span_id (not in TransportHeader)
        hdr.correlation_id,
        hdr.created_at,
        datetime.now(UTC),  # ingested_at
        # lineage
        parent_ids,
        str(lin.root_id),
        lin.generation,
        None,  # derivation_type (not in TransportLineage)
        # governance
        gov.intent,
        list(gov.compliance_tags),
        gov.retention_days,
        getattr(gov, "redaction_applied", False),
        getattr(gov, "audit_required", False),
        getattr(gov, "data_subject_id", None),
        # labels + expiry
        [],
        hdr.expires_at,
    )


# ── PacketStore ──────────────────────────────────────────────


class PacketStore:
    """Async persistence layer for TransportPacket request/response pairs.

    When PACKET_STORE_ENABLED=true and PACKET_STORE_DSN is set, persists
    packets to the PostgreSQL schema defined in packet_store.sql.
    Otherwise operates in stub mode (debug log only).
    """

    async def persist(
        self,
        request: TransportPacket,
        response: TransportPacket,
    ) -> None:
        """Persist an immutable request/response TransportPacket pair.

        Writes both packets to packet_store, their lineage to lineage_graph,
        hop entries to hop_trace, and delegation links to delegation_chain.
        All writes are wrapped in a single transaction.
        """
        if not _PACKET_STORE_ENABLED:
            logger.debug(
                "PacketStore is disabled. Set PACKET_STORE_ENABLED=true to enable. packet_id=%s",
                request.header.packet_id,
            )
            return

        pool = await _pool_manager.get_pool()

        async with pool.acquire() as conn, conn.transaction():
            # Insert both packets
            for packet in (request, response):
                row = _extract_packet_row(packet)
                await conn.execute(_INSERT_PACKET_SQL, *row)

                # Insert hop trace entries
                for seq, hop in enumerate(packet.hop_trace):
                    await conn.execute(
                        _INSERT_HOP_SQL,
                        str(packet.header.packet_id),
                        hop.node,
                        hop.action,
                        hop.timestamp,
                        None,  # exited_at (TransportHop uses duration_ms)
                        hop.status,
                        hop.hop_hash,
                        seq,
                    )

                # Insert delegation chain entries
                for seq, deleg in enumerate(packet.delegation_chain):
                    await conn.execute(
                        _INSERT_DELEGATION_SQL,
                        str(packet.header.packet_id),
                        deleg.delegator,
                        deleg.delegatee,
                        list(deleg.scope),
                        deleg.granted_at,
                        deleg.expires_at,
                        deleg.proof,
                        seq,
                    )

                # Insert lineage graph edges
                parent_ids = [packet.lineage.parent_id] if packet.lineage.parent_id else []
                for parent_id in parent_ids:
                    await conn.execute(
                        _INSERT_LINEAGE_SQL,
                        str(parent_id),
                        str(packet.header.packet_id),
                        packet.lineage.generation,
                        None,  # derivation_type (not in TransportLineage)
                        datetime.now(UTC),
                    )

        logger.info(
            "PacketStore persisted pair: request=%s response=%s",
            request.header.packet_id,
            response.header.packet_id,
        )

    async def record_outcome(
        self,
        *,
        match_packet_id: str,
        tenant: str,
        outcome_id: str,
        outcome: str,
        match_id: str,
        candidate_id: str,
        value: float | None,
        feedback_metadata: dict[str, Any] | None,
    ) -> bool:
        """Write outcome_jsonb to the packet_store row for a match packet.

        Links the TransactionOutcome node written to Neo4j back to the
        TransportPacket row that triggered the match, completing the
        feedback loop substrate. This is the write half of the loop;
        SignalWeightCalculator is the read half.

        Args:
            match_packet_id: packet_id (UUID str) of the original match TransportPacket.
                             Provided by caller via payload.match_packet_id.
            tenant:          actor_tenant for RLS scoping. Always in the WHERE clause.
            outcome_id:      TransactionOutcome.outcome_id (Neo4j node id).
            outcome:         "success" | "failure" | "partial".
            match_id:        payload.match_id from the outcomes request.
            candidate_id:    payload.candidate_id from the outcomes request.
            value:           optional numeric outcome value (may be None).
            feedback_metadata: ConvergenceLoop metadata dict (may be None).

        Returns:
            True  -- UPDATE modified exactly one row (outcome recorded).
            False -- store disabled, packet not found, tenant mismatch, or DB error.

        Contracts:
            Non-fatal: exceptions logged as warnings, never re-raised.
            Tenant-scoped: actor_tenant always in SQL WHERE clause (Contract 3).
            Idempotent: repeated calls overwrite outcome_jsonb (UPDATE, not INSERT).
            Feature-gated: only called when settings.outcome_persistence_enabled=True
                           (callers enforce this; method itself does not re-check).
        """
        if not _PACKET_STORE_ENABLED:
            logger.debug(
                "PacketStore disabled -- outcome not persisted: outcome_id=%s match_packet_id=%s",
                outcome_id,
                match_packet_id,
            )
            return False

        outcome_payload: dict[str, Any] = {
            "outcome_id": outcome_id,
            "outcome": outcome,
            "match_id": match_id,
            "candidate_id": candidate_id,
            "value": value,
            "recorded_at": datetime.now(UTC).isoformat(),
            "feedback": feedback_metadata,
        }

        try:
            pool = await _pool_manager.get_pool()
            async with pool.acquire() as conn:
                result = await conn.execute(
                    _UPDATE_OUTCOME_SQL,
                    json.dumps(outcome_payload),
                    match_packet_id,
                    tenant,
                )
            rows_affected = int(result.split()[-1]) if result else 0
            if rows_affected == 1:
                logger.info(
                    "PacketStore.record_outcome: outcome_jsonb written packet_id=%s outcome=%s outcome_id=%s tenant=%s",
                    match_packet_id,
                    outcome,
                    outcome_id,
                    tenant,
                )
                return True

            logger.warning(
                "PacketStore.record_outcome: no row updated "
                "(packet not found or tenant mismatch) "
                "packet_id=%s tenant=%s outcome_id=%s rows_affected=%d",
                match_packet_id,
                tenant,
                outcome_id,
                rows_affected,
            )
            return False

        except Exception as exc:
            logger.warning(
                "PacketStore.record_outcome failed (non-fatal): outcome_id=%s match_packet_id=%s tenant=%s error=%s",
                outcome_id,
                match_packet_id,
                tenant,
                exc,
            )
            return False

    async def close(self) -> None:
        """Close the underlying connection pool."""
        await _pool_manager.close()


# Module-level singleton — inject into execute_action via dependency
_packet_store = PacketStore()


def get_packet_store() -> PacketStore:
    """Return the module-level PacketStore singleton."""
    return _packet_store
