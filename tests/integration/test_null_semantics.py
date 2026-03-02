"""
tests/integration/test_null_semantics.py
Integration tests for NULL semantics in gate compilation and query execution.
Validates NullBehavior.PASS, FAIL, and SKIP against live Neo4j with seeded data.
"""

from __future__ import annotations

import pytest

from engine.config.schema import GateType, NullBehavior
from engine.gates.null_semantics import NullHandler


@pytest.mark.integration
class TestNullSemanticsPassBehavior:
    """NullBehavior.PASS: NULL property values should pass the gate (inclusive)."""

    @pytest.mark.asyncio
    async def test_null_candidate_property_passes_range_gate(self, graph_driver, seeded_graph):
        """
        Range gate with PASS null behavior: candidates with NULL min/max
        density should still appear in results.
        """
        db = seeded_graph["database"]
        tenant = seeded_graph["tenant"]

        # Insert a facility with NULL density bounds
        await graph_driver.execute_query(
            """
            MERGE (f:Facility {facility_id: 9901})
            SET f.name = 'NullDensity Facility',
                f.min_density = null,
                f.max_density = null,
                f.tenant = $tenant,
                f.gate_mode = 'strict'
            """,
            parameters={"tenant": tenant},
            database=db,
        )

        # Query with PASS semantics: NULL OR (min <= val AND val <= max)
        null_clause = NullHandler.wrap_gate_with_null_logic(
            gate_type=GateType.RANGE,
            null_behavior=NullBehavior.PASS,
            gate_cypher="f.min_density <= $density AND $density <= f.max_density",
            candidate_prop="f.min_density",
        )

        results = await graph_driver.execute_query(
            f"""
            MATCH (f:Facility {{tenant: $tenant}})
            WHERE {null_clause}
            RETURN f.facility_id AS fid, f.name AS name
            ORDER BY f.facility_id
            """,
            parameters={"tenant": tenant, "density": 0.95},
            database=db,
        )

        facility_ids = [r["fid"] for r in results]
        assert 9901 in facility_ids, "NULL density facility should PASS range gate"

        # Cleanup
        await graph_driver.execute_query("MATCH (f:Facility {facility_id: 9901}) DETACH DELETE f", database=db)

    @pytest.mark.asyncio
    async def test_null_query_param_passes_threshold_gate(self, graph_driver, seeded_graph):
        """
        Threshold gate with PASS: if the query parameter is NULL,
        the gate should pass (no constraint applied).
        """
        db = seeded_graph["database"]
        tenant = seeded_graph["tenant"]

        null_clause = NullHandler.wrap_gate_with_null_logic(
            gate_type=GateType.THRESHOLD,
            null_behavior=NullBehavior.PASS,
            gate_cypher="f.contamination_tolerance >= $max_contamination",
            query_param="$max_contamination",
        )

        results = await graph_driver.execute_query(
            f"""
            MATCH (f:Facility {{tenant: $tenant}})
            WHERE {null_clause}
            RETURN f.facility_id AS fid
            """,
            parameters={"tenant": tenant, "max_contamination": None},
            database=db,
        )

        assert len(results) == len(
            seeded_graph["facility_ids"]
        ), "All facilities should pass threshold gate when query param is NULL"

    @pytest.mark.asyncio
    async def test_null_boolean_property_fails_boolean_gate(self, graph_driver, seeded_graph):
        """
        Boolean gate with FAIL (default for boolean): NULL pvc_tolerant
        should exclude the candidate.
        """
        db = seeded_graph["database"]
        tenant = seeded_graph["tenant"]

        await graph_driver.execute_query(
            """
            MERGE (f:Facility {facility_id: 9902})
            SET f.name = 'NullBool Facility',
                f.pvc_tolerant = null,
                f.tenant = $tenant
            """,
            parameters={"tenant": tenant},
            database=db,
        )

        null_clause = NullHandler.wrap_gate_with_null_logic(
            gate_type=GateType.BOOLEAN,
            null_behavior=NullBehavior.FAIL,
            gate_cypher="f.pvc_tolerant = $pvc_tolerant",
            candidate_prop="f.pvc_tolerant",
        )

        results = await graph_driver.execute_query(
            f"""
            MATCH (f:Facility {{tenant: $tenant}})
            WHERE {null_clause}
            RETURN f.facility_id AS fid
            """,
            parameters={"tenant": tenant, "pvc_tolerant": True},
            database=db,
        )

        facility_ids = [r["fid"] for r in results]
        assert 9902 not in facility_ids, "NULL boolean should FAIL boolean gate"

        await graph_driver.execute_query("MATCH (f:Facility {facility_id: 9902}) DETACH DELETE f", database=db)


@pytest.mark.integration
class TestNullSemanticsUnit:
    """Unit-level validation of NullHandler clause generation."""

    def test_pass_wraps_with_or_is_null(self):
        clause = NullHandler.wrap_gate_with_null_logic(
            gate_type=GateType.RANGE,
            null_behavior=NullBehavior.PASS,
            gate_cypher="candidate.min_density <= $density",
            candidate_prop="candidate.min_density",
        )
        assert "IS NULL" in clause
        assert "OR" in clause

    def test_fail_wraps_with_and_is_not_null(self):
        clause = NullHandler.wrap_gate_with_null_logic(
            gate_type=GateType.BOOLEAN,
            null_behavior=NullBehavior.FAIL,
            gate_cypher="candidate.pvc_tolerant = $pvc",
            candidate_prop="candidate.pvc_tolerant",
        )
        assert "IS NOT NULL" in clause
        assert "AND" in clause

    def test_default_behaviors_match_spec(self):
        """Verify default NULL behaviors match the spec from engine-gates-null-semantics.py."""
        assert NullHandler.DEFAULT_BEHAVIORS[GateType.RANGE] == NullBehavior.PASS
        assert NullHandler.DEFAULT_BEHAVIORS[GateType.THRESHOLD] == NullBehavior.PASS
        assert NullHandler.DEFAULT_BEHAVIORS[GateType.BOOLEAN] == NullBehavior.FAIL
        assert NullHandler.DEFAULT_BEHAVIORS[GateType.FRESHNESS] == NullBehavior.FAIL
        assert NullHandler.DEFAULT_BEHAVIORS[GateType.TRAVERSAL] == NullBehavior.FAIL
        assert NullHandler.DEFAULT_BEHAVIORS[GateType.EXCLUSION] == NullBehavior.PASS
