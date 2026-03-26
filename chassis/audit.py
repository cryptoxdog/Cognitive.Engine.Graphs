"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api]
tags: [chassis, audit]
owner: platform-team
status: active
--- /L9_META ---

chassis/audit.py — Engine-Agnostic Audit Logger

Extracted from engine/compliance/audit.py. Zero engine imports.
Every L9 constellation node needs structured audit logging for:
    - SOC2 / HIPAA / GDPR compliance
    - PacketEnvelope governance integration
    - SIEM export (Datadog, Splunk, ELK)
    - PostgreSQL packet_audit_log persistence

The engine-specific ComplianceEngine still lives in engine/compliance/.
This chassis-level logger handles the transport and persistence concerns
that every node shares.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditAction(StrEnum):
    """Auditable action categories — extensible per engine."""

    ACCESS = "access"
    MUTATION = "mutation"
    QUERY = "query"
    DELEGATION = "delegation"
    SYNC = "sync"
    ENRICHMENT = "enrichment"
    PII_ACCESS = "pii_access"
    PII_ERASURE = "pii_erasure"
    ADMIN = "admin"
    HEALTH = "health"


class AuditSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AuditEntry(BaseModel):
    """Immutable audit log entry."""

    model_config = {"frozen": True}

    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action: AuditAction
    severity: AuditSeverity = AuditSeverity.INFO
    actor: str
    tenant: str
    trace_id: str | None = None
    resource: str | None = None
    resource_type: str | None = None
    detail: str | None = None
    payload_hash: str | None = None
    compliance_tags: list[str] = Field(default_factory=list)
    pii_fields_accessed: list[str] = Field(default_factory=list)
    data_subject_id: str | None = None
    outcome: str = "success"
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetentionPolicy(BaseModel):
    tag: str
    retention_days: int
    require_encryption: bool = False
    require_immutable_storage: bool = False


@dataclass
class AuditContext:
    """
    Groups compliance and resource metadata for ``AuditLogger.log()``.

    Consolidates the seven optional compliance/resource parameters so the
    ``log()`` method stays within the 13-parameter limit.
    """

    resource: str | None = None
    resource_type: str | None = None
    payload_hash: str | None = None
    compliance_tags: list[str] = dc_field(default_factory=list)
    pii_fields_accessed: list[str] = dc_field(default_factory=list)
    data_subject_id: str | None = None
    metadata: dict[str, Any] = dc_field(default_factory=dict)


DEFAULT_RETENTION: dict[str, RetentionPolicy] = {
    "SOC2": RetentionPolicy(tag="SOC2", retention_days=2555, require_immutable_storage=True),
    "GDPR": RetentionPolicy(tag="GDPR", retention_days=1825, require_encryption=True),
    "HIPAA": RetentionPolicy(tag="HIPAA", retention_days=2190, require_encryption=True, require_immutable_storage=True),
    "ECOA": RetentionPolicy(tag="ECOA", retention_days=730),
}


# ── Pluggable sink protocol ──────────────────────────────────────────


class AuditSink:
    """
    Abstract audit sink. Engines provide concrete implementations.
    E.g. PostgresSink, SIEMSink, CloudWatchSink.
    """

    async def write_batch(self, entries: list[AuditEntry]) -> int:
        """Persist a batch of audit entries. Returns count persisted."""
        raise NotImplementedError


class PostgresSink(AuditSink):
    """
    Concrete audit sink that writes to the packet_audit_log table.

    Uses an asyncpg connection pool for async batch inserts.
    Initialise with an asyncpg pool instance:

        pool = await asyncpg.create_pool(dsn=...)
        sink = PostgresSink(pool)
        audit_logger.add_sink(sink)
    """

    _INSERT_SQL = """
        INSERT INTO packet_audit_log (
            audit_id, timestamp, action, severity, actor, tenant,
            trace_id, resource, resource_type, detail, payload_hash,
            compliance_tags, pii_fields_accessed, data_subject_id,
            outcome, metadata
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
    """

    def __init__(self, db_pool: Any) -> None:
        self._pool = db_pool

    async def write_batch(self, entries: list[AuditEntry]) -> int:
        """Persist a batch of audit entries to packet_audit_log.

        Uses executemany for O(1) round trips. Returns count persisted.
        """
        if not entries:
            return 0

        import json as _json

        batch_data = [
            (
                e.audit_id,
                e.timestamp,
                e.action.value,
                e.severity.value,
                e.actor,
                e.tenant,
                e.trace_id,
                e.resource,
                e.resource_type,
                e.detail,
                e.payload_hash,
                e.compliance_tags,
                e.pii_fields_accessed,
                e.data_subject_id,
                e.outcome,
                _json.dumps(e.metadata, default=str),
            )
            for e in entries
        ]

        async with self._pool.acquire() as conn:
            await conn.executemany(self._INSERT_SQL, batch_data)

        persisted = len(entries)
        logger.info("PostgresSink persisted %d audit entries", persisted)
        return persisted


class LogSink(AuditSink):
    """
    Audit sink that writes entries to the Python logger.
    Useful for development, testing, and as a fallback when no DB is available.
    """

    def __init__(self, log_level: int = logging.INFO) -> None:
        self._log_level = log_level

    async def write_batch(self, entries: list[AuditEntry]) -> int:
        """Write audit entries to the Python logger."""
        for entry in entries:
            logger.log(
                self._log_level,
                "audit_event: action=%s actor=%s tenant=%s outcome=%s",
                entry.action.value,
                entry.actor,
                entry.tenant,
                entry.outcome,
            )
        return len(entries)


class AuditLogger:
    """
    Engine-agnostic structured audit logger.

    Buffers entries in memory and flushes to registered sinks.
    Thread-safe for mixed sync/async usage.
    """

    def __init__(
        self,
        retention_policies: dict[str, RetentionPolicy] | None = None,
        buffer_size: int = 100,
        sinks: list[AuditSink] | None = None,
    ):
        self._retention = retention_policies or DEFAULT_RETENTION
        self._buffer: list[AuditEntry] = []
        self._buffer_size = buffer_size
        self._sinks = sinks or []
        self._async_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
        self._log = logging.getLogger("l9.audit")

    def add_sink(self, sink: AuditSink) -> None:
        """Register an audit persistence sink."""
        self._sinks.append(sink)

    def log(
        self,
        action: AuditAction,
        actor: str,
        tenant: str,
        *,
        severity: AuditSeverity = AuditSeverity.INFO,
        trace_id: str | None = None,
        context: AuditContext | None = None,
        detail: str | None = None,
        outcome: str = "success",
    ) -> AuditEntry:
        """
        Create and buffer an audit entry.

        Parameters
        ----------
        action : AuditAction
        actor : str
        tenant : str
        severity : AuditSeverity
        trace_id : str | None
        context : AuditContext | None
            Consolidates resource, compliance, and PII metadata.
            Pass ``AuditContext(resource=..., compliance_tags=[...])`` as needed.
        detail : str | None
        outcome : str
        """
        ctx = context or AuditContext()
        entry = AuditEntry(
            action=action,
            severity=severity,
            actor=actor,
            tenant=tenant,
            trace_id=trace_id,
            resource=ctx.resource,
            resource_type=ctx.resource_type,
            detail=detail,
            payload_hash=ctx.payload_hash,
            compliance_tags=ctx.compliance_tags,
            pii_fields_accessed=ctx.pii_fields_accessed,
            data_subject_id=ctx.data_subject_id,
            outcome=outcome,
            metadata=ctx.metadata,
        )
        self._emit(entry)
        return entry

    async def flush(self) -> int:
        """Flush buffer to all registered sinks. Returns total persisted."""
        async with self._async_lock:
            entries = list(self._buffer)
            self._buffer.clear()

        if not entries:
            return 0

        total = 0
        for sink in self._sinks:
            try:
                total += await sink.write_batch(entries)
            except Exception:
                logger.exception("Audit sink %s failed, re-buffering", type(sink).__name__)
                async with self._async_lock:
                    self._buffer = entries + self._buffer
                raise
        return total

    def get_retention_days(self, compliance_tags: Sequence[str]) -> int:
        if not compliance_tags:
            return 365
        days = [self._retention[t].retention_days for t in compliance_tags if t in self._retention]
        return max(days) if days else 365

    @property
    def buffer_count(self) -> int:
        return len(self._buffer)

    def _emit(self, entry: AuditEntry) -> None:
        self._log.info("audit_event", extra={"audit": entry.model_dump(mode="json")})
        with self._sync_lock:
            self._buffer.append(entry)
