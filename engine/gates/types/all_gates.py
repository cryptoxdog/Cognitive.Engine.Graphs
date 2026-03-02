# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [config]
# tags: [gates, types, implementation]
# owner: engine-team
# status: active
# --- /L9_META ---
# engine/gates/types/all_gates.py
"""
All 10 gate type implementations in one file.
Production-grade, enterprise-quality, frontier AI lab standard.
"""

import logging
from abc import ABC, abstractmethod

from engine.config.schema import DomainSpec, GateSpec

logger = logging.getLogger(__name__)


# ============================================================================
# BASE GATE
# ============================================================================


class BaseGate(ABC):
    """Abstract base class for all gate types."""

    def __init__(self, spec: GateSpec, domain_spec: DomainSpec):
        """
        Initialize gate.

        Args:
            spec: Gate specification
            domain_spec: Full domain specification
        """
        self.spec = spec
        self.domain_spec = domain_spec

    @abstractmethod
    def compile(self) -> str:
        """
        Compile gate into Cypher WHERE clause fragment.

        Returns:
            Cypher clause (without NULL handling)
        """

    def _prop_ref(self, prop: str) -> str:
        """Format property reference."""
        return f"candidate.{prop}" if not prop.startswith("candidate.") else prop

    def _param_ref(self, param: str) -> str:
        """Format query parameter reference."""
        return f"$query.{param}" if not param.startswith("$") else param


# ============================================================================
# 1. RANGE GATE
# ============================================================================


class RangeGate(BaseGate):
    """Candidate property falls within [min, max] from query."""

    def compile(self) -> str:
        """
        Example: candidate.creditscore >= $query.mincreditscore
                 AND candidate.creditscore <= $query.maxcreditscore
        """
        if not self.spec.candidateprop:
            raise ValueError(f"Gate '{self.spec.name}': candidateprop required for range gate")
        if not self.spec.queryparam_min or not self.spec.queryparam_max:
            raise ValueError(f"Gate '{self.spec.name}': queryparam_min and queryparam_max required")

        prop = self._prop_ref(self.spec.candidateprop)
        min_param = self._param_ref(self.spec.queryparam_min)
        max_param = self._param_ref(self.spec.queryparam_max)

        return f"{prop} >= {min_param} AND {prop} <= {max_param}"


# ============================================================================
# 2. THRESHOLD GATE
# ============================================================================


class ThresholdGate(BaseGate):
    """Candidate property meets minimum/maximum threshold."""

    def compile(self) -> str:
        """
        Example: candidate.creditscore >= $query.mincreditscore
        """
        if not self.spec.candidateprop:
            raise ValueError(f"Gate '{self.spec.name}': candidateprop required")
        if not self.spec.queryparam:
            raise ValueError(f"Gate '{self.spec.name}': queryparam required")
        if not self.spec.operator:
            raise ValueError(f"Gate '{self.spec.name}': operator required (>=, <=, >, <, =)")

        prop = self._prop_ref(self.spec.candidateprop)
        param = self._param_ref(self.spec.queryparam)
        operator = self.spec.operator

        return f"{prop} {operator} {param}"


# ============================================================================
# 3. BOOLEAN GATE
# ============================================================================


class BooleanGate(BaseGate):
    """Boolean flag match (true/false or presence)."""

    def compile(self) -> str:
        """
        Example: candidate.vaeligible = $query.vaeligible
        """
        if not self.spec.candidateprop:
            raise ValueError(f"Gate '{self.spec.name}': candidateprop required")
        if not self.spec.queryparam:
            raise ValueError(f"Gate '{self.spec.name}': queryparam required")

        prop = self._prop_ref(self.spec.candidateprop)
        param = self._param_ref(self.spec.queryparam)

        return f"{prop} = {param}"


# ============================================================================
# 4. COMPOSITE GATE
# ============================================================================


class CompositeGate(BaseGate):
    """Logical combination of multiple sub-gates (AND/OR)."""

    def compile(self) -> str:
        """
        Example: (gate1 AND gate2) OR gate3
        """
        if not self.spec.subgates:
            raise ValueError(f"Gate '{self.spec.name}': subgates required")
        if not self.spec.logic:
            raise ValueError(f"Gate '{self.spec.name}': logic required (AND/OR)")

        # Find subgate specs by name
        subgate_clauses = []
        for subgate_name in self.spec.subgates:
            subgate_spec = next((g for g in self.domain_spec.gates if g.name == subgate_name), None)
            if not subgate_spec:
                raise ValueError(f"Subgate '{subgate_name}' not found in domain spec")

            # Recursively compile subgate
            from engine.gates.registry import GateRegistry

            gate_class = GateRegistry.get_gate_class(subgate_spec.type)
            gate_instance = gate_class(subgate_spec, self.domain_spec)
            subgate_clauses.append(f"({gate_instance.compile()})")

        logic_op = f" {self.spec.logic.upper()} "
        return logic_op.join(subgate_clauses)


# ============================================================================
# 5. ENUMMAP GATE
# ============================================================================


class EnumMapGate(BaseGate):
    """Query enum value maps to candidate's allowed set."""

    def compile(self) -> str:
        """
        Example: $query.propertytype IN candidate.allowedpropertytypes
        """
        if not self.spec.candidateprop:
            raise ValueError(f"Gate '{self.spec.name}': candidateprop required")
        if not self.spec.queryparam:
            raise ValueError(f"Gate '{self.spec.name}': queryparam required")

        prop = self._prop_ref(self.spec.candidateprop)
        param = self._param_ref(self.spec.queryparam)

        # Check if mapping is provided (query value → candidate values)
        if self.spec.mapping:
            # Build CASE WHEN for complex mapping
            cases = []
            for query_val, candidate_vals in self.spec.mapping.items():
                val_list = ", ".join([f"'{v}'" for v in candidate_vals])
                cases.append(f"WHEN {param} = '{query_val}' THEN {prop} IN [{val_list}]")

            case_expr = " ".join(cases)
            return f"CASE {case_expr} ELSE false END"
        # Simple membership check
        return f"{param} IN {prop}"


# ============================================================================
# 6. EXCLUSION GATE
# ============================================================================


class ExclusionGate(BaseGate):
    """Blocks matches based on exclusion edges (e.g., BLACKLISTED)."""

    def compile(self) -> str:
        """
        Example: NOT EXISTS((query)-[:BLACKLISTEDLENDER]->(candidate))
        """
        if not self.spec.edgetype:
            raise ValueError(f"Gate '{self.spec.name}': edgetype required")

        edge = self.spec.edgetype
        from_node = self.spec.fromnode or "query"
        to_node = self.spec.tonode or "candidate"

        return f"NOT EXISTS(({from_node})-[:{edge}]->({to_node}))"


# ============================================================================
# 7. SELFRANGE GATE
# ============================================================================


class SelfRangeGate(BaseGate):
    """Candidate's own property range contains query value."""

    def compile(self) -> str:
        """
        Example: $query.mfi >= candidate.mfi_min AND $query.mfi <= candidate.mfi_max
        """
        if not self.spec.candidateprop_min or not self.spec.candidateprop_max:
            raise ValueError(f"Gate '{self.spec.name}': candidateprop_min and candidateprop_max required")
        if not self.spec.queryparam:
            raise ValueError(f"Gate '{self.spec.name}': queryparam required")

        min_prop = self._prop_ref(self.spec.candidateprop_min)
        max_prop = self._prop_ref(self.spec.candidateprop_max)
        param = self._param_ref(self.spec.queryparam)

        return f"{param} >= {min_prop} AND {param} <= {max_prop}"


# ============================================================================
# 8. FRESHNESS GATE
# ============================================================================


class FreshnessGate(BaseGate):
    """Candidate data must be fresher than threshold."""

    def compile(self) -> str:
        """
        Example: duration.between(candidate.ratesheetdate, datetime()).days <= 7
        """
        if not self.spec.candidateprop:
            raise ValueError(f"Gate '{self.spec.name}': candidateprop (timestamp) required")
        if not self.spec.maxagedays:
            raise ValueError(f"Gate '{self.spec.name}': maxagedays required")

        prop = self._prop_ref(self.spec.candidateprop)
        max_age = self.spec.maxagedays

        return f"duration.between({prop}, datetime()).days <= {max_age}"


# ============================================================================
# 9. TEMPORALRANGE GATE
# ============================================================================


class TemporalRangeGate(BaseGate):
    """Candidate's temporal window overlaps with query window."""

    def compile(self) -> str:
        """
        Example: candidate.availablestart <= $query.needbydate
                 AND candidate.availableend >= $query.needbydate
        """
        if not self.spec.candidateprop_start or not self.spec.candidateprop_end:
            raise ValueError(f"Gate '{self.spec.name}': candidateprop_start and candidateprop_end required")
        if not self.spec.queryparam_start or not self.spec.queryparam_end:
            raise ValueError(f"Gate '{self.spec.name}': queryparam_start and queryparam_end required")

        cand_start = self._prop_ref(self.spec.candidateprop_start)
        cand_end = self._prop_ref(self.spec.candidateprop_end)
        query_start = self._param_ref(self.spec.queryparam_start)
        query_end = self._param_ref(self.spec.queryparam_end)

        return f"{cand_start} <= {query_end} AND {cand_end} >= {query_start}"


# ============================================================================
# 10. TRAVERSAL GATE
# ============================================================================


class TraversalGate(BaseGate):
    """Gate checks condition on a traversed relationship or node."""

    def compile(self) -> str:
        """
        Example: EXISTS { MATCH (candidate)-[:OPERATESIN]->(s:State)
                          WHERE s.statecode = $query.propertystate }
        """
        if not self.spec.pattern:
            raise ValueError(f"Gate '{self.spec.name}': pattern required")
        if not self.spec.condition:
            raise ValueError(f"Gate '{self.spec.name}': condition required")

        pattern = self.spec.pattern
        condition = self.spec.condition

        return f"EXISTS {{ MATCH {pattern} WHERE {condition} }}"


# ============================================================================
# EXPORT ALL GATE CLASSES
# ============================================================================

__all__ = [
    "BaseGate",
    "BooleanGate",
    "CompositeGate",
    "EnumMapGate",
    "ExclusionGate",
    "FreshnessGate",
    "RangeGate",
    "SelfRangeGate",
    "TemporalRangeGate",
    "ThresholdGate",
    "TraversalGate",
]
