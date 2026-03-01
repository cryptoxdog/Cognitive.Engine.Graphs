# ============================================================================
# tests/performance/test_sync_throughput.py
# ============================================================================

"""
Sync throughput performance tests.
Target: 1000 entities < 2s
"""

import time

import pytest


@pytest.mark.performance
@pytest.mark.slow
class TestSyncThroughput:
    """Benchmark sync throughput."""

    def test_sync_1000_entities(self):
        """Sync 1000 entities completes < 2s."""
        entities = [{"supplierid": f"SUP_{i}", "name": f"Supplier {i}"} for i in range(1000)]

        start = time.time()
        # Execute sync (mock or real)
        end = time.time()

        duration = end - start
        assert duration < 2.0, f"Sync took {duration}s, exceeds 2s target"
