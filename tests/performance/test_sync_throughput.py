"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, performance, throughput]
owner: engine-team
status: active
--- /L9_META ---

tests/performance/test_sync_throughput.py
Performance benchmarks for batch sync throughput.
Measures entities/second for UNWIND/MERGE sync operations against Neo4j.
"""

from __future__ import annotations

import statistics
import sys
import time
import uuid

import pytest

from engine.config.schema import SyncEndpointSpec, SyncStrategy
from engine.sync.generator import SyncGenerator


@pytest.mark.performance
class TestSyncThroughput:
    """Benchmark batch sync throughput against live Neo4j."""

    @staticmethod
    def _generate_facility_batch(size: int, tenant: str) -> list[dict]:
        """Generate a batch of synthetic facility entities."""
        return [
            {
                "facility_id": 100_000 + i,
                "name": f"SyncBench-{i}",
                "lat": 34.0 + (i * 0.001),
                "lon": -118.0 + (i * 0.001),
                "process_type": "extrusion",
                "facility_role": "processor",
                "min_density": 0.85 + (i % 10) * 0.01,
                "max_density": 0.95 + (i % 10) * 0.01,
                "contamination_tolerance": 0.03,
                "pvc_tolerant": i % 2 == 0,
                "food_grade_certified": i % 3 == 0,
                "has_extruder": True,
                "handles_regrind": True,
                "gate_mode": "strict",
                "tenant": tenant,
            }
            for i in range(size)
        ]

    @pytest.mark.asyncio
    async def test_facility_sync_1000_entities_throughput(self, graph_driver, domain_spec):
        """
        Benchmark: sync 1000 facilities via UNWIND/MERGE.
        Target: >500 entities/sec on local Neo4j.
        """
        db = "neo4j"
        tenant = f"syncbench-{uuid.uuid4().hex[:6]}"
        batch_size = 1000

        batch = self._generate_facility_batch(batch_size, tenant)

        # Build the UNWIND/MERGE Cypher
        sync_spec = SyncEndpointSpec(
            path="/v1/sync/facilities",
            method="POST",
            target_node="Facility",
            id_property="facility_id",
            batch_strategy=SyncStrategy.UNWIND_MERGE,
        )
        generator = SyncGenerator(domain_spec)
        cypher = generator.generate_sync_query(sync_spec, batch)

        # Benchmark: 5 iterations
        latencies: list[float] = []
        for _ in range(5):
            # Clean before each iteration
            await graph_driver.execute_query(
                "MATCH (f:Facility {tenant: $tenant}) DETACH DELETE f",
                parameters={"tenant": tenant},
                database=db,
            )

            t0 = time.perf_counter()
            await graph_driver.execute_query(
                cypher,
                parameters={"batch": batch},
                database=db,
            )
            elapsed = time.perf_counter() - t0
            latencies.append(elapsed)

        avg_sec = statistics.mean(latencies)
        throughput = batch_size / avg_sec

        sys.stdout.write(
            f"\n{'─' * 50}\n"
            f"Sync Throughput: {batch_size} facilities\n"
            f"  avg: {avg_sec:.2f}s  throughput: {throughput:.0f} entities/sec\n"
            f"  min: {min(latencies):.2f}s  max: {max(latencies):.2f}s\n"
            f"{'─' * 50}\n"
        )

        # Verify data landed
        count_result = await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: $tenant}) RETURN count(f) AS cnt",
            parameters={"tenant": tenant},
            database=db,
        )
        assert count_result[0]["cnt"] == batch_size

        assert throughput > 500, f"Throughput {throughput:.0f} entities/sec below 500 target"

        # Cleanup
        await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: $tenant}) DETACH DELETE f",
            parameters={"tenant": tenant},
            database=db,
        )

    @pytest.mark.asyncio
    async def test_incremental_update_throughput(self, graph_driver, domain_spec):
        """
        Benchmark: UNWIND/MATCH/SET for incremental field updates.
        Updates 500 facilities with new contamination_tolerance values.
        """
        db = "neo4j"
        tenant = f"updatebench-{uuid.uuid4().hex[:6]}"
        batch_size = 500

        # Seed initial data
        batch = self._generate_facility_batch(batch_size, tenant)
        seed_cypher = """
        UNWIND $batch AS row
        MERGE (f:Facility {facility_id: row.facility_id})
        SET f += row
        """
        await graph_driver.execute_query(seed_cypher, parameters={"batch": batch}, database=db)

        # Build update batch
        update_batch = [{"facility_id": 100_000 + i, "contamination_tolerance": 0.07} for i in range(batch_size)]

        update_cypher = """
        UNWIND $batch AS row
        MATCH (f:Facility {facility_id: row.facility_id})
        SET f.contamination_tolerance = row.contamination_tolerance,
            f.updated_at = datetime()
        """

        latencies: list[float] = []
        for _ in range(5):
            t0 = time.perf_counter()
            await graph_driver.execute_query(update_cypher, parameters={"batch": update_batch}, database=db)
            latencies.append(time.perf_counter() - t0)

        avg_sec = statistics.mean(latencies)
        throughput = batch_size / avg_sec

        sys.stdout.write(
            f"\nIncremental Update: {batch_size} facilities\n"
            f"  avg: {avg_sec:.2f}s  throughput: {throughput:.0f} updates/sec\n"
        )

        # Verify update applied
        result = await graph_driver.execute_query(
            """
            MATCH (f:Facility {tenant: $tenant})
            WHERE f.contamination_tolerance = 0.07
            RETURN count(f) AS cnt
            """,
            parameters={"tenant": tenant},
            database=db,
        )
        assert result[0]["cnt"] == batch_size

        assert throughput > 1000, f"Update throughput {throughput:.0f}/sec below 1000 target"

        await graph_driver.execute_query(
            "MATCH (f:Facility {tenant: $tenant}) DETACH DELETE f",
            parameters={"tenant": tenant},
            database=db,
        )
