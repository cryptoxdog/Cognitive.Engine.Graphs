# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [config]
# tags: [gates, null-semantics]
# owner: engine-team
# status: active
# --- /L9_META ---
# engine/gates/null_semantics.py
"""
NULL value handling for gates.
Defines deterministic behavior when candidate properties or query parameters are NULL.
"""

import logging

from engine.config.schema import GateType, NullBehavior

logger = logging.getLogger(__name__)


class NullHandler:
    """Manages NULL semantics per gate type."""

    # Default NULL behavior per gate type (can be overridden in spec)
    DEFAULT_BEHAVIORS = {
        GateType.RANGE: NullBehavior.PASS,
        GateType.THRESHOLD: NullBehavior.PASS,
        GateType.BOOLEAN: NullBehavior.FAIL,
        GateType.COMPOSITE: NullBehavior.PASS,  # Depends on subgates
        GateType.ENUMMAP: NullBehavior.PASS,
        GateType.EXCLUSION: NullBehavior.PASS,  # No exclusion edge = pass
        GateType.SELFRANGE: NullBehavior.PASS,
        GateType.FRESHNESS: NullBehavior.FAIL,  # Missing timestamp = stale
        GateType.TEMPORALRANGE: NullBehavior.PASS,
        GateType.TRAVERSAL: NullBehavior.FAIL,  # Missing required traversal = fail
    }

    @classmethod
    def get_null_clause(
        cls,
        gate_type: GateType,
        null_behavior: NullBehavior,
        candidate_prop: str | None = None,
        query_param: str | None = None,
    ) -> str:
        """
        Generate Cypher NULL handling clause.

        Args:
            gate_type: Type of gate
            null_behavior: Desired NULL behavior (pass/fail)
            candidate_prop: Candidate property path (e.g., "candidate.creditscore")
            query_param: Query parameter reference (e.g., "$query.mincreditscore")

        Returns:
            Cypher WHERE clause fragment
        """
        conditions = []

        # Build NULL checks for candidate and query
        if candidate_prop:
            conditions.append(f"{candidate_prop} IS NOT NULL")
        if query_param:
            conditions.append(f"{query_param} IS NOT NULL")

        if not conditions:
            return ""

        null_check = " AND ".join(conditions)

        if null_behavior == NullBehavior.PASS:
            # If any value is NULL, pass the gate (OR gate logic)
            return f"({null_check})"
        # FAIL
        # If any value is NULL, fail the gate (require all non-NULL)
        return null_check

    @classmethod
    def wrap_gate_with_null_logic(
        cls,
        gate_type: GateType,
        null_behavior: NullBehavior,
        gate_cypher: str,
        candidate_prop: str | None = None,
        query_param: str | None = None,
    ) -> str:
        """
        Wrap gate Cypher with NULL handling logic.

        Args:
            gate_type: Type of gate
            null_behavior: Desired NULL behavior
            gate_cypher: Core gate logic (without NULL handling)
            candidate_prop: Candidate property reference
            query_param: Query parameter reference

        Returns:
            Complete gate clause with NULL semantics
        """
        if null_behavior == NullBehavior.PASS:
            # NULL values pass gate: (value IS NULL OR gate_logic)
            null_conditions = []
            if candidate_prop:
                null_conditions.append(f"{candidate_prop} IS NULL")
            if query_param:
                null_conditions.append(f"{query_param} IS NULL")

            if null_conditions:
                null_clause = " OR ".join(null_conditions)
                return f"({null_clause} OR ({gate_cypher}))"
            return gate_cypher

        # FAIL
        # NULL values fail gate: (value IS NOT NULL AND gate_logic)
        null_conditions = []
        if candidate_prop:
            null_conditions.append(f"{candidate_prop} IS NOT NULL")
        if query_param:
            null_conditions.append(f"{query_param} IS NOT NULL")

        if null_conditions:
            null_clause = " AND ".join(null_conditions)
            return f"({null_clause} AND ({gate_cypher}))"
        return gate_cypher
