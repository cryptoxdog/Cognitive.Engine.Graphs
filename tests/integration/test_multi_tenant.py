"""
tests/integration/test_multi_tenant.py
Integration tests for multi-tenant isolation in the L9 Graph Cognitive Engine.
Validates that tenants cannot see each other's data at the graph level.

Note: Tenant resolution is now a chassis responsibility. These tests focus on
graph-level isolation only.
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from engine.graph.driver import GraphDriver


@pytest.mark.integration
class TestGraphLevelTenantIsolation:
    """Verify Neo4j queries are tenant-scoped — no cross-tenant data leakage."""

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_see_tenant_b_facilities(self, graph_driver):
        """Facilities created by tenant_a are invisible to tenant_b queries."""
        db = "neo4j"

        await graph_driver.execute_query(
            """
            MERGE (f:Facility {facility_id: 8001})
            SET f.name = 'TenantA-Only', f.tenant = 'tenant_a'
            """,
            database=db,
        )
        await graph_driver.execute_query(
            """
            MERGE (f:Facility {facility_id: 8002})
            SET f.name = 'TenantB-Only', f.tenant = 'tenant_b'
            """,
            database=db,
        )

        results_a = await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: 'tenant_a'}) RETURN f.facility_id AS fid",
            database=db,
        )
        results_b = await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: 'tenant_b'}) RETURN f.facility_id AS fid",
            database=db,
        )

        ids_a = {r["fid"] for r in results_a}
        ids_b = {r["fid"] for r in results_b}

        assert 8001 in ids_a
        assert 8002 not in ids_a, "Tenant A must not see Tenant B data"
        assert 8002 in ids_b
        assert 8001 not in ids_b, "Tenant B must not see Tenant A data"

        # Cleanup
        await graph_driver.execute_query(
            "MATCH (f:Facility) WHERE f.facility_id IN [8001, 8002] DETACH DELETE f",
            database=db,
        )

    @pytest.mark.asyncio
    async def test_exclusion_edges_respect_tenant_scope(self, graph_driver):
        """EXCLUDED_FROM edges only apply within the same tenant context."""
        db = "neo4j"

        await graph_driver.execute_query(
            """
            MERGE (a:Facility {facility_id: 8010, tenant: 'tenant_x', name: 'X-Alpha'})
            MERGE (b:Facility {facility_id: 8011, tenant: 'tenant_x', name: 'X-Beta'})
            MERGE (c:Facility {facility_id: 8012, tenant: 'tenant_y', name: 'Y-Gamma'})
            MERGE (a)-[:EXCLUDED_FROM]->(b)
            """,
            database=db,
        )

        # Tenant X: facility 8010 excluded from 8011
        results_x = await graph_driver.execute_query(
            """
            MATCH (f:Facility {tenant: 'tenant_x'})
            WHERE NOT EXISTS {
                MATCH (excluder:Facility {facility_id: 8010})-[:EXCLUDED_FROM]->(f)
            }
            RETURN f.facility_id AS fid
            """,
            database=db,
        )
        fids_x = {r["fid"] for r in results_x}
        assert 8010 in fids_x
        assert 8011 not in fids_x, "8011 should be excluded by 8010"

        # Tenant Y: unaffected by Tenant X exclusions
        results_y = await graph_driver.execute_query(
            """
            MATCH (f:Facility {tenant: 'tenant_y'})
            RETURN f.facility_id AS fid
            """,
            database=db,
        )
        fids_y = {r["fid"] for r in results_y}
        assert 8012 in fids_y, "Tenant Y data must be unaffected by Tenant X exclusions"

        await graph_driver.execute_query(
            "MATCH (f:Facility) WHERE f.facility_id IN [8010, 8011, 8012] DETACH DELETE f",
            database=db,
        )

    @pytest.mark.asyncio
    async def test_sync_batch_scoped_to_tenant(self, graph_driver):
        """Batch UNWIND/MERGE sets tenant property and doesn't leak across tenants."""
        db = "neo4j"
        batch = [
            {"facility_id": 8020, "name": "SyncTest-A"},
            {"facility_id": 8021, "name": "SyncTest-B"},
        ]

        await graph_driver.execute_query(
            """
            UNWIND $batch AS row
            MERGE (f:Facility {facility_id: row.facility_id})
            SET f += row, f.tenant = $tenant
            """,
            parameters={"batch": batch, "tenant": "sync_tenant"},
            database=db,
        )

        # Verify tenant property set
        results = await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: 'sync_tenant'}) RETURN f.facility_id AS fid",
            database=db,
        )
        assert len(results) == 2

        # Verify other tenants don't see it
        results_other = await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: 'other_tenant'}) RETURN count(f) AS cnt",
            database=db,
        )
        assert results_other[0]["cnt"] == 0

        await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: 'sync_tenant'}) DETACH DELETE f",
            database=db,
        )
