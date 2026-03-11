"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: "*"
layer: [compliance]
tags: [chassis, audit, compliance, soc2, gdpr, engine-agnostic]
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
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
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


class AuditSeverity(str, Enum):
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
        resource: str | None = None,
        resource_type: str | None = None,
        detail: str | None = None,
        payload_hash: str | None = None,
        compliance_tags: list[str] | None = None,
        pii_fields_accessed: list[str] | None = None,
        data_subject_id: str | None = None,
        outcome: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Create and buffer an audit entry."""
        entry = AuditEntry(
            action=action,
            severity=severity,
            actor=actor,
            tenant=tenant,
            trace_id=trace_id,
            resource=resource,
            resource_type=resource_type,
            detail=detail,
            payload_hash=payload_hash,
            compliance_tags=compliance_tags or [],
            pii_fields_accessed=pii_fields_accessed or [],
            data_subject_id=data_subject_id,
            outcome=outcome,
            metadata=metadata or {},
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
