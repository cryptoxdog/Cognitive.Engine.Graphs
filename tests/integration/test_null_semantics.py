# ============================================================================
# tests/integration/test_null_semantics.py
# ============================================================================

"""
NULL semantics integration tests.
Target Coverage: 85%+
"""

import pytest


@pytest.mark.integration
class TestNullSemantics:
    """Test NULL behavior across all gate types."""

    def test_threshold_null_pass_allows_candidates(self):
        """Candidates with NULL pass when nullbehavior=pass."""
        pass

    def test_threshold_null_fail_blocks_candidates(self):
        """Candidates with NULL blocked when nullbehavior=fail."""
        pass

    def test_range_null_semantics(self):
        """Range gates handle NULL according to config."""
        pass
