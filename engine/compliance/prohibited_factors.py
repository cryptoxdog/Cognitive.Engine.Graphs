"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [compliance, prohibited-factors]
owner: engine-team
status: active
--- /L9_META ---

Prohibited factor enforcement.
Blocks protected attributes at compile-time (ECOA, HIPAA, etc.).
"""

import logging

from engine.config.schema import DomainSpec, GateSpec

logger = logging.getLogger(__name__)


class ProhibitedFactorValidator:
    """Validates gates don't use prohibited factors."""

    def __init__(self, domain_spec: DomainSpec):
        self.domain_spec = domain_spec
        self.blocked_fields: set[str] = set()

        if domain_spec.compliance and domain_spec.compliance.prohibitedfactors:
            pf_config = domain_spec.compliance.prohibitedfactors
            if pf_config.enabled:
                self.blocked_fields = set(pf_config.blockedfields)

    def validate_gate(self, gate_spec: GateSpec) -> None:
        """
        Validate gate doesn't reference prohibited fields.

        Args:
            gate_spec: Gate specification

        Raises:
            ValueError: If gate references prohibited field
        """
        if not self.blocked_fields:
            return  # No prohibited factors configured

        # Check candidate property
        if gate_spec.candidateprop and gate_spec.candidateprop in self.blocked_fields:
            raise ValueError(
                f"Gate '{gate_spec.name}' references prohibited field '{gate_spec.candidateprop}'. "
                f"Blocked fields: {self.blocked_fields}"
            )

        # Check query parameter
        if gate_spec.queryparam and gate_spec.queryparam in self.blocked_fields:
            raise ValueError(
                f"Gate '{gate_spec.name}' references prohibited field '{gate_spec.queryparam}'. "
                f"Blocked fields: {self.blocked_fields}"
            )

        logger.debug(f"Gate '{gate_spec.name}' passed prohibited factor validation")
