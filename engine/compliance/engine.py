# engine/compliance/engine.py
"""
Compliance orchestrator.
Coordinates prohibited-factor validation, PII handling, and audit logging
across match, sync, and admin request lifecycles.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from engine.compliance.audit import AuditLogger
from engine.compliance.pii import PIIHandler
from engine.compliance.prohibited_factors import ProhibitedFactorValidator

if TYPE_CHECKING:
    from engine.config.schema import DomainSpec, GateSpec

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """Orchestrates all compliance checks for a domain."""

    def __init__(self, domain_spec: DomainSpec) -> None:
        self._spec = domain_spec
        self._prohibited = ProhibitedFactorValidator(domain_spec)

        # Extract domain-specific PII fields if configured
        additional_pii = None
        if (
            domain_spec.compliance
            and domain_spec.compliance.pii
            and hasattr(domain_spec.compliance.pii, "additional_fields")
        ):
            additional_pii = domain_spec.compliance.pii.additional_fields

        self._pii = PIIHandler(additional_pii_fields=additional_pii)
        self._audit = AuditLogger()  # Uses default retention policies
        self._enabled = bool(
            domain_spec.compliance
            and any(
                [
                    domain_spec.compliance.prohibitedfactors and domain_spec.compliance.prohibitedfactors.enabled,
                    domain_spec.compliance.pii and domain_spec.compliance.pii.enabled,
                    domain_spec.compliance.audit and domain_spec.compliance.audit.enabled,
                ]
            )
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
        self._audit.log_query(
            actor=tenant,
            tenant=tenant,
            detail=f"Match request direction={match_direction}",
            trace_id=trace_id,
        )
        # Detect and mask PII in query
        pii_fields = self._pii.get_pii_field_paths(query)
        if pii_fields:
            return self._pii.mask_fields(query, list(pii_fields))
        return query

    def check_sync_request(
        self,
        *,
        tenant: str,
        entity_type: str,
        batch: list[dict[str, Any]],
        trace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run pre-sync compliance checks.

        1. Audit the sync operation
        2. Scan batch for PII fields
        3. Mask PII in batch data before sync

        Returns:
            Sanitized batch with PII masked
        """
        batch_size = len(batch)

        # Audit the sync operation
        self._audit.log_mutation(
            actor=tenant,
            tenant=tenant,
            resource=entity_type,
            detail=f"Sync {entity_type} batch_size={batch_size}",
            trace_id=trace_id,
        )

        if not self._enabled or not batch:
            return batch

        # Scan and mask PII in each batch item
        sanitized_batch = []
        pii_detected = False

        for item in batch:
            pii_fields = self._pii.get_pii_field_paths(item)
            if pii_fields:
                pii_detected = True
                # Log PII access for audit trail
                self._audit.log_access(
                    actor=tenant,
                    tenant=tenant,
                    resource=f"{entity_type}:{item.get('entity_id', 'unknown')}",
                    resource_type=entity_type,
                    trace_id=trace_id,
                    pii_fields_accessed=list(pii_fields),
                )
                # Mask PII before sync
                sanitized_batch.append(self._pii.mask_fields(item, list(pii_fields)))
            else:
                sanitized_batch.append(item)

        if pii_detected:
            logger.warning(f"PII detected and masked in sync batch for {entity_type}")

        return sanitized_batch

    def redact_response(
        self,
        response: dict[str, Any],
        tenant: str,
    ) -> dict[str, Any]:
        """Redact PII from response before returning to client."""
        if not self._enabled:
            return response
        # Detect and redact PII fields
        pii_fields = self._pii.get_pii_field_paths(response)
        if pii_fields:
            return self._pii.redact(response, list(pii_fields))
        return response

    def log_outcome(
        self,
        *,
        tenant: str,
        outcome_id: str,
        outcome: str,
        trace_id: str | None = None,
    ) -> None:
        """Audit outcome feedback."""
        self._audit.log_mutation(
            actor=tenant,
            tenant=tenant,
            resource=outcome_id,
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
        self._audit.log_delegation(
            actor=tenant,
            tenant=tenant,
            resource="admin",
            detail=f"Admin subaction={subaction}",
            trace_id=trace_id,
        )
