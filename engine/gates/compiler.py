"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [gates, compiler, cypher]
owner: engine-team
status: active
--- /L9_META ---

engine/gates/compiler.py
Compile gate definitions from domain spec YAML into executable Cypher WHERE clauses.
Handles all 10 gate types, null semantics, role exemptions, and direction filtering.

Exports: GateCompiler
"""

from __future__ import annotations

import logging

from engine.config.schema import (
    DomainSpec,
    GateSpec,
    GateType,
    NullBehavior,
)
from engine.gates.null_semantics import NullHandler

logger = logging.getLogger(__name__)


class GateCompiler:
    """
    Compiles GateSpec objects from a domain spec into Cypher WHERE clause fragments.

    Each gate type maps to a specific Cypher predicate pattern:
        boolean   → candidate.prop = $param
        threshold → candidate.prop >= $param (or <=, configurable)
        range     → $param_min <= candidate.prop <= $param_max  (or candidate range check)
        enum      → candidate.prop IN $param_list
        exclusion → NOT (candidate)-[:EXCLUDED_FROM]->(query)
        composite → (gate1 AND gate2) OR gate3
        self_range→ candidate.min_prop <= $param AND $param <= candidate.max_prop
        freshness → candidate.prop >= datetime() - duration({days: $days})
        temporal_range → candidate.prop >= $start AND candidate.prop <= $end
        traversal → (candidate)-[:EDGE]->(target {prop: $param})

    Usage:
        compiler = GateCompiler(domain_spec)
        where_clause = compiler.compile_all_gates("buyer_to_seller")
        single = compiler.compile(gate_spec)
    """

    def __init__(self, domain_spec: DomainSpec):
        self.domain_spec = domain_spec
        self._gates: list[GateSpec] = domain_spec.gates if domain_spec.gates else []
        self._compliance = getattr(domain_spec, "compliance", None)

    # ── Public API ─────────────────────────────────────────

    def compile(self, gate: GateSpec) -> str:
        """
        Compile a single GateSpec into a Cypher WHERE fragment.

        Returns a string like:
            "candidate.min_density <= $density AND $density <= candidate.max_density"
        """
        handler = self._get_handler(gate.type)
        raw_predicate = handler(gate)
        return self._wrap_null_semantics(gate, raw_predicate)

    def compile_all_gates(
        self,
        match_direction: str,
        role: str | None = None,
    ) -> str:
        """
        Compile all gates into a combined WHERE clause.

        Args:
            match_direction: Current match direction (e.g., "buyer_to_seller")
            role: Facility role for exemption checking

        Returns:
            Combined Cypher WHERE clause (without the WHERE keyword)
        """
        fragments: list[str] = []

        for gate in self._gates:
            # Direction filter
            if gate.matchdirections and match_direction not in gate.matchdirections:
                continue

            # Role exemption
            if role and gate.roleexempt and role in gate.roleexempt:
                logger.debug(f"Gate {gate.name} exempted for role={role}")
                continue

            fragment = self.compile(gate)
            if fragment:
                fragments.append(f"({fragment})")

        if not fragments:
            return "true"

        return " AND ".join(fragments)

    def compile_relaxed(
        self,
        match_direction: str,
        role: str | None = None,
    ) -> str:
        """
        Compile gates for relaxed matching.
        Non-critical gates become score penalties instead of hard filters.
        Only gates with relaxedpenalty == 0.0 are included as hard WHERE.
        """
        hard_fragments: list[str] = []

        for gate in self._gates:
            if gate.matchdirections and match_direction not in gate.matchdirections:
                continue
            if role and gate.roleexempt and role in gate.roleexempt:
                continue

            if gate.relaxedpenalty == 0.0:
                fragment = self.compile(gate)
                if fragment:
                    hard_fragments.append(f"({fragment})")

        if not hard_fragments:
            return "true"

        return " AND ".join(hard_fragments)

    # ── Gate Type Handlers ─────────────────────────────────

    def _get_handler(self, gate_type: GateType):
        """Route to the correct handler for each gate type."""
        handlers = {
            GateType.BOOLEAN: self._compile_boolean,
            GateType.THRESHOLD: self._compile_threshold,
            GateType.RANGE: self._compile_range,
            GateType.ENUMMAP: self._compile_enum,
            GateType.EXCLUSION: self._compile_exclusion,
            GateType.COMPOSITE: self._compile_composite,
            GateType.SELFRANGE: self._compile_self_range,
            GateType.FRESHNESS: self._compile_freshness,
            GateType.TEMPORALRANGE: self._compile_temporal_range,
            GateType.TRAVERSAL: self._compile_traversal,
        }
        handler = handlers.get(gate_type)
        if not handler:
            logger.warning(f"Unknown gate type: {gate_type}, defaulting to passthrough")
            return lambda g: "true"
        return handler

    def _compile_boolean(self, gate: GateSpec) -> str:
        """Boolean gate: candidate.prop = $param OR candidate.prop = true."""
        if gate.queryparam:
            return f"candidate.{gate.candidateprop} = ${gate.queryparam}"
        return f"candidate.{gate.candidateprop} = true"

    def _compile_threshold(self, gate: GateSpec) -> str:
        """
        Threshold gate: candidate.prop >= $param (default).
        Supports operator override via gate.operator: >=, <=, >, <, =
        """
        op = gate.operator or ">="
        return f"candidate.{gate.candidateprop} {op} ${gate.queryparam}"

    def _compile_range(self, gate: GateSpec) -> str:
        """
        Range gate: query value falls within candidate's min/max range.
        Pattern: candidate.min_prop <= $param AND $param <= candidate.max_prop
        """
        min_prop = gate.candidateprop_min or f"min_{gate.candidateprop}"
        max_prop = gate.candidateprop_max or f"max_{gate.candidateprop}"
        param = gate.queryparam

        parts = []
        parts.append(f"(candidate.{min_prop} IS NULL OR candidate.{min_prop} <= ${param})")
        parts.append(f"(candidate.{max_prop} IS NULL OR ${param} <= candidate.{max_prop})")
        return " AND ".join(parts)

    def _compile_enum(self, gate: GateSpec) -> str:
        """
        Enum gate: candidate.prop IN $param_list
        Or inverse: $param IN candidate.prop_list
        """
        if gate.invertible:
            return f"${gate.queryparam} IN candidate.{gate.candidateprop}"
        return f"candidate.{gate.candidateprop} IN ${gate.queryparam}"

    def _compile_exclusion(self, gate: GateSpec) -> str:
        """
        Exclusion gate: NOT exists((candidate)-[:EXCLUDED_FROM]->(query_entity))
        Uses the EXCLUDED_FROM edge type from the graph schema.
        """
        edge_type = gate.edgetype or "EXCLUDED_FROM"
        if gate.fromnode:
            return f"NOT exists(({gate.fromnode})-[:{edge_type}]->({gate.tonode or 'candidate'}))"
        return f"NOT exists((candidate)-[:{edge_type}]->(query))"

    def _compile_composite(self, gate: GateSpec) -> str:
        """
        Composite gate: combines sub-gates with AND/OR.
        gate.subgates is a list of gate names (strings), gate.logic is 'AND' or 'OR'.
        """
        if not gate.subgates:
            return "true"

        combinator = f" {gate.logic or 'AND'} "
        sub_fragments = []
        for sub_gate_name in gate.subgates:
            sub_gate_spec = next((g for g in self._gates if g.name == sub_gate_name), None)
            if sub_gate_spec is None:
                logger.warning(f"Subgate '{sub_gate_name}' not found, skipping")
                continue
            fragment = self.compile(sub_gate_spec)
            if fragment:
                sub_fragments.append(f"({fragment})")

        if not sub_fragments:
            return "true"

        return combinator.join(sub_fragments)

    def _compile_self_range(self, gate: GateSpec) -> str:
        """
        Self-range gate: candidate defines its own min/max that the query value must fall into.
        Pattern: candidate.min_prop <= $param AND $param <= candidate.max_prop
        Differs from range in that both bounds come from the candidate.
        """
        min_prop = gate.candidateprop_min or f"min_{gate.candidateprop}"
        max_prop = gate.candidateprop_max or f"max_{gate.candidateprop}"
        param = gate.queryparam

        return (
            f"(candidate.{min_prop} IS NULL OR candidate.{min_prop} <= ${param}) AND "
            f"(candidate.{max_prop} IS NULL OR ${param} <= candidate.{max_prop})"
        )

    def _compile_freshness(self, gate: GateSpec) -> str:
        """
        Freshness gate: candidate.prop >= datetime() - duration({days: N})
        Ensures data recency (e.g., rate sheets updated within 24h).
        """
        duration_field = "days"
        duration_value = gate.maxagedays or 1
        return f"candidate.{gate.candidateprop} >= datetime() - duration({{{duration_field}: {duration_value}}})"

    def _compile_temporal_range(self, gate: GateSpec) -> str:
        """
        Temporal range gate: candidate.prop between two datetime parameters.
        """
        start_param = gate.queryparam_start or f"{gate.queryparam}_start"
        end_param = gate.queryparam_end or f"{gate.queryparam}_end"
        return f"candidate.{gate.candidateprop} >= ${start_param} AND candidate.{gate.candidateprop} <= ${end_param}"

    def _compile_traversal(self, gate: GateSpec) -> str:
        """
        Traversal gate: requires an edge path to exist.
        Pattern: exists((candidate)-[:EDGE_TYPE]->(target {prop: $param}))
        """
        edge_type = gate.edgetype or "RELATES_TO"
        target_label = gate.tonode or ""
        target_filter = ""

        if gate.candidateprop and gate.queryparam:
            target_filter = f" {{{gate.candidateprop}: ${gate.queryparam}}}"

        label_clause = f":{target_label}" if target_label else ""
        return f"exists((candidate)-[:{edge_type}]->(t{label_clause}{target_filter}))"

    # ── Null Semantics ─────────────────────────────────────

    def _wrap_null_semantics(self, gate: GateSpec, predicate: str) -> str:
        """
        Wrap predicate with NULL handling based on gate's null behavior.

        NullBehavior.PASS   → (candidate.prop IS NULL OR <predicate>)
        NullBehavior.FAIL   → (candidate.prop IS NOT NULL AND <predicate>)
        """
        null_behavior = gate.nullbehavior
        if null_behavior is None or null_behavior == NullBehavior.PASS:
            null_behavior = NullHandler.DEFAULT_BEHAVIORS.get(gate.type, NullBehavior.PASS)

        return NullHandler.wrap_gate_with_null_logic(
            gate_type=gate.type,
            null_behavior=null_behavior,
            gate_cypher=predicate,
            candidate_prop=f"candidate.{gate.candidateprop}" if gate.candidateprop else None,
            query_param=f"${gate.queryparam}" if gate.queryparam else None,
        )
