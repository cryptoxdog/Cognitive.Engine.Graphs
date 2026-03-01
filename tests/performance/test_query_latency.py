"""
tests/performance/test_query_latency.py
Performance benchmarks for match query latency.
Tests p50/p95/p99 latency against Neo4j with seeded graph data.
Requires: pytest-benchmark or manual timing.
"""
from __future__ import annotations

import statistics
import time
from typing import List

import pytest

from engine.gates.compiler import GateCompiler
from engine.scoring.assembler import ScoringAssembler
from engine.traversal.assembler import TraversalAssembler


@pytest.mark.performance
class TestMatchQueryLatency:
    """Benchmark end-to-end match query execution latency."""

    @pytest.mark.asyncio
    async def test_strict_match_latency_under_100ms(
        self, graph_driver, seeded_graph, domain_spec
    ):
        """
        Strict match query should complete within 100ms p95 on a
        small seeded graph (3 facilities, 4 polymers, 5 forms).
        Realistic cold-cache benchmark.
        """
        db = seeded_graph["database"]
        tenant = seeded_graph["tenant"]

        gate_compiler = GateCompiler(domain_spec)
        scoring_assembler = ScoringAssembler(domain_spec)
        traversal_assembler = TraversalAssembler(domain_spec)

        direction = "intake_to_buyer"
        where_clause = gate_compiler.compile_all_gates(direction)
        traversal_clauses = traversal_assembler.assemble_traversal(direction)
        scoring_clause = scoring_assembler.assemble_scoring_clause(direction, {})

        # Build the full Cypher query
        traversal_block = "\n".join(traversal_clauses) if traversal_clauses else ""
        cypher = f"""
        MATCH (candidate:Facility {{tenant: $tenant}})
        {traversal_block}
        WHERE {where_clause}
        {scoring_clause}
        RETURN candidate.facility_id AS fid, candidate.name AS name, score
        ORDER BY score DESC
        LIMIT 10
        """

        query_params = {
            "tenant": tenant,
            "density": 0.95,
            "mfi": 12.0,
            "max_contamination": 0.05,
            "polymer": "HDPE",
            "form": "regrind",
        }

        # Warmup
        await graph_driver.execute_query(cypher, parameters=query_params, database=db)

        # Benchmark: 50 iterations
        latencies: List[float] = []
        for _ in range(50):
            t0 = time.perf_counter()
            results = await graph_driver.execute_query(
                cypher, parameters=query_params, database=db
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed_ms)

        p50 = statistics.median(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        p99 = sorted(latencies)[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)

        print(f"\n{'─' * 50}")
        print(f"Match Query Latency (n=50, {len(seeded_graph['facility_ids'])} facilities)")
        print(f"  avg: {avg:.1f}ms  p50: {p50:.1f}ms  p95: {p95:.1f}ms  p99: {p99:.1f}ms")
        print(f"{'─' * 50}")

        assert p95 < 100, f"p95 latency {p95:.1f}ms exceeds 100ms target"

    @pytest.mark.asyncio
    async def test_relaxed_match_latency_under_200ms(
        self, graph_driver, seeded_graph, domain_spec
    ):
        """
        Relaxed match (fewer hard gates, more scoring penalties) should
        complete within 200ms p95. Relaxed queries scan more candidates.
        """
        db = seeded_graph["database"]
        tenant = seeded_graph["tenant"]

        gate_compiler = GateCompiler(domain_spec)
        direction = "intake_to_buyer"
        where_clause = gate_compiler.compile_relaxed(direction)

        cypher = f"""
        MATCH (candidate:Facility {{tenant: $tenant}})
        WHERE {where_clause}
        RETURN candidate.facility_id AS fid, candidate.name AS name
        ORDER BY candidate.name
        LIMIT 25
        """

        query_params = {"tenant": tenant, "density": 0.95}

        # Warmup
        await graph_driver.execute_query(cypher, parameters=query_params, database=db)

        latencies: List[float] = []
        for _ in range(50):
            t0 = time.perf_counter()
            await graph_driver.execute_query(cypher, parameters=query_params, database=db)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            latencies.append(elapsed_ms)

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        avg = statistics.mean(latencies)

        print(f"\nRelaxed Match: avg={avg:.1f}ms  p95={p95:.1f}ms")

        assert p95 < 200, f"p95 latency {p95:.1f}ms exceeds 200ms target"
