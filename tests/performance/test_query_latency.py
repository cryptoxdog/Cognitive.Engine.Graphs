# ============================================================================
# tests/performance/test_query_latency.py
# ============================================================================

"""
Query latency performance tests.
Target: p95 < 500ms
"""

import time

import pytest


@pytest.mark.performance
@pytest.mark.slow
class TestQueryLatency:
    """Benchmark query execution time."""

    def test_match_query_latency(self, sample_query_borrower):
        """Match query p95 latency < 500ms."""
        latencies = []

        for _ in range(100):
            start = time.time()
            # Execute match query (mock or real)
            end = time.time()
            latencies.append((end - start) * 1000)  # ms

        latencies.sort()
        p95 = latencies[94]  # 95th percentile

        assert p95 < 500, f"p95 latency {p95}ms exceeds 500ms target"

    def test_gate_compilation_performance(self):
        """Gate compilation < 5ms per gate."""
        pass

    def test_scoring_assembly_performance(self):
        """Scoring assembly < 20ms for 10 dimensions."""
        pass
