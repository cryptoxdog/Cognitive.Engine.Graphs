"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [compliance, audit]
owner: engine-team
status: active
--- /L9_META ---

engine/compliance/audit.py
Structured audit logging for compliance (SOC2, HIPAA, GDPR).
Integrates with PacketEnvelope governance fields and external SIEM.

Exports: AuditLogger
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────


class AuditAction(str, Enum):
    """Auditable action categories."""

    ACCESS = "access"
    MUTATION = "mutation"
    QUERY = "query"
    DELEGATION = "delegation"
    SYNC = "sync"
    MATCH = "match"
    ENRICHMENT = "enrichment"
    PII_ACCESS = "pii_access"
    PII_ERASURE = "pii_erasure"
    ADMIN = "admin"


class AuditSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ── Models ─────────────────────────────────────────────────


class AuditEntry(BaseModel):
    """Immutable audit log entry."""

    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action: AuditAction
    severity: AuditSeverity = AuditSeverity.INFO
    actor: str  # who performed the action
    tenant: str  # org isolation key
    trace_id: str | None = None  # W3C trace context
    resource: str | None = None  # e.g., "Facility:42", "PacketEnvelope:abc"
    resource_type: str | None = None  # e.g., "Facility", "MaterialProfile"
    detail: str | None = None  # human-readable description
    payload_hash: str | None = None  # SHA-256 of related payload
    compliance_tags: list[str] = Field(default_factory=list)  # GDPR, SOC2, ECOA
    pii_fields_accessed: list[str] = Field(default_factory=list)
    data_subject_id: str | None = None  # GDPR right-to-delete tracking
    outcome: str = "success"  # success | failure | denied
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


class RetentionPolicy(BaseModel):
    """Per-compliance-tag retention rules."""

    tag: str
    retention_days: int
    require_encryption: bool = False
    require_immutable_storage: bool = False


# ── Default Retention ──────────────────────────────────────

DEFAULT_RETENTION: dict[str, RetentionPolicy] = {
    "SOC2": RetentionPolicy(tag="SOC2", retention_days=2555, require_immutable_storage=True),
    "GDPR": RetentionPolicy(tag="GDPR", retention_days=1825, require_encryption=True),
    "HIPAA": RetentionPolicy(tag="HIPAA", retention_days=2190, require_encryption=True, require_immutable_storage=True),
    "ECOA": RetentionPolicy(tag="ECOA", retention_days=730),
    "TILA": RetentionPolicy(tag="TILA", retention_days=730),
    "RESPA": RetentionPolicy(tag="RESPA", retention_days=1095),
}


# ── AuditLogger ────────────────────────────────────────────


class AuditLogger:
    """
    Structured audit logger for L9 compliance.

    Produces structured JSON log entries compatible with:
    - PacketEnvelope.security / .governance fields
    - External SIEM (Datadog, Splunk, ELK) via structlog JSON
    - PostgreSQL packet_audit_log (append-only, no UPDATE/DELETE)

    Usage:
        audit = AuditLogger(retention_policies=DEFAULT_RETENTION)
        audit.log_access(actor="mike", tenant="acme", resource="Facility:42")
        audit.log_mutation(actor="sync", tenant="acme", resource="MaterialProfile:7",
                           detail="Batch sync 150 entities", compliance_tags=["GDPR"])
        audit.log_query(actor="api", tenant="acme", detail="match_strict 14 gates")
    """

    def __init__(
        self,
        retention_policies: dict[str, RetentionPolicy] | None = None,
        siem_endpoint: str | None = None,
        buffer_size: int = 100,
    ):
        self._retention = retention_policies or DEFAULT_RETENTION
        self._siem_endpoint = siem_endpoint
        self._buffer: list[AuditEntry] = []
        self._buffer_size = buffer_size
        self._buffer_lock = asyncio.Lock()
        self._sync_lock = threading.Lock()
        self._log = logging.getLogger("l9.audit")

    # ── Public Logging Methods ─────────────────────────────

    def log_access(
        self,
        actor: str,
        tenant: str,
        resource: str,
        resource_type: str | None = None,
        trace_id: str | None = None,
        compliance_tags: list[str] | None = None,
        pii_fields_accessed: list[str] | None = None,
        data_subject_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a data access event."""
        severity = AuditSeverity.WARNING if pii_fields_accessed else AuditSeverity.INFO
        return self._emit(
            AuditEntry(
                action=AuditAction.ACCESS,
                severity=severity,
                actor=actor,
                tenant=tenant,
                resource=resource,
                resource_type=resource_type,
                trace_id=trace_id,
                compliance_tags=compliance_tags or [],
                pii_fields_accessed=pii_fields_accessed or [],
                data_subject_id=data_subject_id,
                metadata=metadata or {},
            )
        )

    def log_mutation(
        self,
        actor: str,
        tenant: str,
        resource: str,
        detail: str,
        resource_type: str | None = None,
        trace_id: str | None = None,
        payload_hash: str | None = None,
        compliance_tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a data mutation event (create, update, delete, sync)."""
        return self._emit(
            AuditEntry(
                action=AuditAction.MUTATION,
                severity=AuditSeverity.INFO,
                actor=actor,
                tenant=tenant,
                resource=resource,
                resource_type=resource_type,
                detail=detail,
                trace_id=trace_id,
                payload_hash=payload_hash,
                compliance_tags=compliance_tags or [],
                metadata=metadata or {},
            )
        )

    def log_query(
        self,
        actor: str,
        tenant: str,
        detail: str,
        trace_id: str | None = None,
        compliance_tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a query execution event (match, search, resolve)."""
        return self._emit(
            AuditEntry(
                action=AuditAction.QUERY,
                severity=AuditSeverity.INFO,
                actor=actor,
                tenant=tenant,
                detail=detail,
                trace_id=trace_id,
                compliance_tags=compliance_tags or [],
                metadata=metadata or {},
            )
        )

    def log_pii_erasure(
        self,
        actor: str,
        tenant: str,
        data_subject_id: str,
        detail: str,
        trace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a GDPR right-to-erasure operation. Always CRITICAL severity."""
        return self._emit(
            AuditEntry(
                action=AuditAction.PII_ERASURE,
                severity=AuditSeverity.CRITICAL,
                actor=actor,
                tenant=tenant,
                data_subject_id=data_subject_id,
                detail=detail,
                trace_id=trace_id,
                compliance_tags=["GDPR"],
                metadata=metadata or {},
            )
        )

    def log_delegation(
        self,
        actor: str,
        tenant: str,
        resource: str,
        detail: str,
        trace_id: str | None = None,
        compliance_tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a cross-node delegation event."""
        return self._emit(
            AuditEntry(
                action=AuditAction.DELEGATION,
                severity=AuditSeverity.WARNING,
                actor=actor,
                tenant=tenant,
                resource=resource,
                detail=detail,
                trace_id=trace_id,
                compliance_tags=compliance_tags or [],
                metadata=metadata or {},
            )
        )

    # ── Retention ──────────────────────────────────────────

    def get_retention_days(self, compliance_tags: Sequence[str]) -> int:
        """Return the longest retention period across all applicable tags."""
        if not compliance_tags:
            return 365  # default 1 year
        days = []
        for tag in compliance_tags:
            policy = self._retention.get(tag)
            if policy:
                days.append(policy.retention_days)
        return max(days) if days else 365

    def get_retention_policy(self, tag: str) -> RetentionPolicy | None:
        """Get retention policy for a specific compliance tag."""
        return self._retention.get(tag)

    # ── Buffer / Flush ─────────────────────────────────────

    async def flush(self) -> list[AuditEntry]:
        """Flush buffered entries (for batch insert to packet_audit_log)."""
        async with self._buffer_lock:
            entries = list(self._buffer)
            self._buffer.clear()
        return entries

    def flush_sync(self) -> list[AuditEntry]:
        """Synchronous flush for non-async contexts. Use flush() when possible."""
        entries = list(self._buffer)
        self._buffer.clear()
        return entries

    async def flush_to_store(self, db_pool: Any) -> int:
        """
        Flush buffered entries to PostgreSQL packet_audit_log.

        Uses batch insert with executemany for O(1) round trips.
        Thread-safe via asyncio.Lock.

        Args:
            db_pool: asyncpg connection pool

        Returns:
            Number of entries persisted
        """
        async with self._buffer_lock:
            entries = list(self._buffer)
            self._buffer.clear()

        if not entries:
            return 0

        insert_sql = """
            INSERT INTO packet_audit_log (
                audit_id, timestamp, action, severity, actor, tenant,
                trace_id, resource, resource_type, detail, payload_hash,
                compliance_tags, pii_fields_accessed, data_subject_id,
                outcome, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        """

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
                e.metadata,
            )
            for e in entries
        ]

        try:
            async with db_pool.acquire() as conn:
                await conn.executemany(insert_sql, batch_data)
        except Exception as e:
            logger.error(f"Failed to persist audit entries: {e}")
            async with self._buffer_lock:
                self._buffer = entries + self._buffer
            raise
        else:
            persisted = len(entries)
            logger.info(f"Persisted {persisted} audit entries to packet_audit_log")
            return persisted

    @property
    def buffer_count(self) -> int:
        return len(self._buffer)

    # ── Internal ───────────────────────────────────────────

    def _emit(self, entry: AuditEntry) -> AuditEntry:
        """Emit audit entry to structured log + buffer (thread-safe)."""
        log_data = entry.model_dump(mode="json")
        self._log.info(
            "audit_event",
            extra={"audit": log_data},
        )
        # Use synchronous lock for thread safety in non-async contexts
        # For async contexts, use emit_async() instead
        with self._sync_lock:
            self._buffer.append(entry)
            buffer_full = len(self._buffer) >= self._buffer_size
        if buffer_full:
            logger.debug(f"Audit buffer full ({self._buffer_size}), ready for flush")
        return entry

    async def emit_async(self, entry: AuditEntry) -> AuditEntry:
        """Emit audit entry with async lock protection for concurrent access."""
        log_data = entry.model_dump(mode="json")
        self._log.info(
            "audit_event",
            extra={"audit": log_data},
        )
        async with self._buffer_lock:
            self._buffer.append(entry)
            buffer_full = len(self._buffer) >= self._buffer_size
        if buffer_full:
            logger.debug(f"Audit buffer full ({self._buffer_size}), ready for flush")
        return entry
