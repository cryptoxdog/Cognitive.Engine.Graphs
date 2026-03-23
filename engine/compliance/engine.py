"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [compliance]
tags: [compliance, engine]
owner: engine-team
status: active
--- /L9_META ---

Compliance orchestrator.
Coordinates prohibited-factor validation, PII handling, and audit logging
across match, sync, and admin request lifecycles.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from engine.compliance.audit import AuditLogger
from engine.compliance.pii import PIICategory, PIIHandler, PIISensitivity
from engine.compliance.prohibited_factors import ProhibitedFactorValidator

if TYPE_CHECKING:
    from engine.config.schema import DomainSpec, GateSpec, SyncEndpointSpec

logger = logging.getLogger(__name__)


class ComplianceEngine:
    """Orchestrates all compliance checks for a domain."""

    def __init__(self, domain_spec: DomainSpec, db_pool: Any | None = None) -> None:
        self._spec = domain_spec
        self._db_pool = db_pool
        self._prohibited = ProhibitedFactorValidator(domain_spec)

        # Domain-specific PII enrichment (optional)
        additional_pii: dict[str, tuple[PIICategory, PIISensitivity]] = {}
        compliance = getattr(domain_spec, "compliance", None)
        if compliance and getattr(compliance, "pii", None):
            pii_cfg = compliance.pii
            # Convention: compliance.pii.additional_fields: dict[name, (category, sensitivity)]
            if hasattr(pii_cfg, "additional_fields") and isinstance(pii_cfg.additional_fields, dict):
                additional_pii = pii_cfg.additional_fields

        self._pii = PIIHandler(additional_pii_fields=additional_pii)
        self._audit = AuditLogger()  # Uses default retention policies

        # Default to enabled for SOC2/HIPAA compliance.
        # Only disable if domain_spec.compliance.enabled is explicitly False.
        self._enabled = True
        if domain_spec.compliance and hasattr(domain_spec.compliance, "enabled"):
            if domain_spec.compliance.enabled is False:
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def flush_audit(self) -> int:
        """Flush audit buffer to persistent storage.

        Returns:
            Number of entries persisted.
        """
        if self._db_pool is None:
            logger.warning("No db_pool configured, cannot flush audit entries")
            return 0
        return await self._audit.flush_to_store(self._db_pool)

    def validate_gates(self, gates: list[GateSpec]) -> None:
        """Validate all gates against prohibited factors at compile time.

        Raises:
            ValueError: If any gate references a prohibited field.
        """
        for gate in gates:
            self._prohibited.validate_gate(gate)

    def validate_sync_fields(self, endpoint_spec: SyncEndpointSpec) -> None:
        """Validate sync endpoint field mappings against prohibited factors.

        Raises:
            ValueError: If endpoint maps to a prohibited field.
        """
        if not self._prohibited.blocked_fields:
            return

        # Check fieldsupdated list (PATCH operations)
        if endpoint_spec.fieldsupdated:
            for field in endpoint_spec.fieldsupdated:
                if field in self._prohibited.blocked_fields:
                    msg = (
                        f"Sync endpoint '{endpoint_spec.path}' updates prohibited "
                        f"field '{field}'. Blocked fields: {self._prohibited.blocked_fields}"
                    )
                    raise ValueError(msg)

        # Check idproperty
        if endpoint_spec.idproperty and endpoint_spec.idproperty in self._prohibited.blocked_fields:
            msg = (
                f"Sync endpoint '{endpoint_spec.path}' uses prohibited "
                f"idproperty '{endpoint_spec.idproperty}'. Blocked fields: {self._prohibited.blocked_fields}"
            )
            raise ValueError(msg)

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
        # Detect PII in query for audit logging — do NOT mask inbound queries.
        # Masking replaces values with '***', corrupting graph traversal results.
        # PII redaction is applied on the RESPONSE path via redact_response().
        pii_fields = self._pii.get_pii_field_paths(query)
        if pii_fields:
            logger.info(
                "PII detected in match query (fields: %s) — logged for audit, query passed through",
                [str(f) for f in pii_fields],
            )
            self._audit.log_access(
                actor=tenant,
                tenant=tenant,
                resource=", ".join(str(f) for f in pii_fields),
                resource_type="pii_field",
                pii_fields_accessed=[str(f) for f in pii_fields],
                trace_id=trace_id,
            )
        return query

    def check_sync_request(
        self,
        *,
        tenant: str,
        entity_type: str,
        batch: list[dict[str, Any]],
        trace_id: str | None = None,
        endpoint_spec: SyncEndpointSpec | None = None,
    ) -> None:
        """Audit sync operations and validate against prohibited factors."""
        # Validate endpoint spec if provided
        if endpoint_spec:
            self.validate_sync_fields(endpoint_spec)

        # Check batch data for prohibited fields
        for item in batch:
            if self._prohibited.blocked_fields:
                for field_name in item:
                    if field_name in self._prohibited.blocked_fields:
                        msg = (
                            f"Sync batch contains prohibited field '{field_name}'. "
                            f"Blocked fields: {self._prohibited.blocked_fields}"
                        )
                        raise ValueError(msg)

            # Detect and log PII access
            pii_fields = self._pii.get_pii_field_paths(item)
            if pii_fields:
                self._audit.log_access(
                    actor=tenant,
                    tenant=tenant,
                    resource=f"{entity_type}:{item.get('entity_id', 'unknown')}",
                    resource_type=entity_type,
                    trace_id=trace_id,
                )

        # Log the sync operation
        self._audit.log_mutation(
            actor=tenant,
            tenant=tenant,
            resource=entity_type,
            detail=f"Sync {entity_type} batch_size={len(batch)}",
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
