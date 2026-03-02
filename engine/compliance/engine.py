# engine/compliance/engine.py
"""
Compliance orchestrator.
Coordinates prohibited-factor validation, PII handling, and audit logging
across match, sync, and admin request lifecycles.
"""
from __future__ import annotations

import logging
from typing import Any

from engine.compliance.audit import AuditAction, AuditLogger, AuditSeverity
from engine.compliance.pii import PIIHandler
from engine.compliance.prohibited_factors import ProhibitedFactorValidator
from engine.config.schema import DomainSpec, GateSpec

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """Orchestrates all compliance checks for a domain."""

    def __init__(self, domain_spec: DomainSpec) -> None:
        self._spec = domain_spec
        self._prohibited = ProhibitedFactorValidator(domain_spec)
        self._pii = PIIHandler(domain_spec)
        self._audit = AuditLogger(domain_spec)
        self._enabled = bool(
            domain_spec.compliance
            and any([
                domain_spec.compliance.prohibitedfactors
                and domain_spec.compliance.prohibitedfactors.enabled,
                domain_spec.compliance.pii and domain_spec.compliance.pii.enabled,
                domain_spec.compliance.audit and domain_spec.compliance.audit.enabled,
            ])
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    def validate_gates(self, gates: list[GateSpec]) -> None:
        """Validate all gates against prohibited factors at compile time.

        Raises:
            ValueError: If any gate references a prohibited field.
        """
        for gate in gates:
            self._prohibited.validate_gate(gate)

    def check_match_request(
        self,
        *,
        tenant: str,
        query: dict[str, Any],
        match_direction: str,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Run pre-match compliance checks. Returns sanitized query."""
        self._audit.log(
            action=AuditAction.MATCH,
            actor=tenant,
            tenant=tenant,
            detail=f"Match request direction={match_direction}",
            trace_id=trace_id,
        )
        return self._pii.mask_query(query)

    def check_sync_request(
        self,
        *,
        tenant: str,
        entity_type: str,
        batch_size: int,
        trace_id: str | None = None,
    ) -> None:
        """Audit sync operations."""
        self._audit.log(
            action=AuditAction.SYNC,
            actor=tenant,
            tenant=tenant,
            detail=f"Sync {entity_type} batch_size={batch_size}",
            trace_id=trace_id,
        )

    def redact_response(
        self,
        response: dict[str, Any],
        tenant: str,
    ) -> dict[str, Any]:
        """Redact PII from response before returning to client."""
        if not self._enabled:
            return response
        return self._pii.redact_response(response)

    def log_outcome(
        self,
        *,
        tenant: str,
        outcome_id: str,
        outcome: str,
        trace_id: str | None = None,
    ) -> None:
        """Audit outcome feedback."""
        self._audit.log(
            action=AuditAction.MUTATION,
            actor=tenant,
            tenant=tenant,
            detail=f"Outcome recorded: {outcome_id} result={outcome}",
            trace_id=trace_id,
        )

    def log_admin(
        self,
        *,
        tenant: str,
        subaction: str,
        trace_id: str | None = None,
    ) -> None:
        """Audit admin operations."""
        self._audit.log(
            action=AuditAction.ADMIN,
            severity=AuditSeverity.WARNING,
            actor=tenant,
            tenant=tenant,
            detail=f"Admin subaction={subaction}",
            trace_id=trace_id,
        )
