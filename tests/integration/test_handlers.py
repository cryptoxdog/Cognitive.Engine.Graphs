"""Legacy aggregate handler integration tests.

These scenarios were superseded by the dedicated integration suites:
- tests/integration/test_match_handler.py
- tests/integration/test_sync_handler.py
- tests/integration/test_outcomes_handler.py

The old file targeted removed compatibility APIs (DomainSpecLoader, in-memory
GraphDriver constructor shape, older handler payloads) and now serves only as a
legacy placeholder so collection stays explicit.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Superseded by dedicated handler integration suites and legacy compatibility APIs were removed."
)
