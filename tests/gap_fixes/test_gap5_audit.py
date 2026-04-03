"""
Tests for GAP-5: audit_persistence.py
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.compliance import audit_persistence


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset module-level pool between tests."""
    original = audit_persistence._POOL
    audit_persistence._POOL = None
    yield
    audit_persistence._POOL = original


@pytest.mark.asyncio
async def test_flush_returns_zero_when_no_pool() -> None:
    entries = [{"tenant_id": "t1", "actor": "system", "action": "match"}]
    result = await audit_persistence.flush_audit_entries(entries)
    assert result == 0


@pytest.mark.asyncio
async def test_flush_returns_zero_for_empty_entries() -> None:
    mock_pool = MagicMock()
    audit_persistence._POOL = mock_pool
    result = await audit_persistence.flush_audit_entries([])
    assert result == 0


@pytest.mark.asyncio
async def test_flush_inserts_rows() -> None:
    entries = [
        {"tenant_id": "t1", "actor": "system", "action": "match", "detail": "ok", "created_at": time.time()},
        {"tenant_id": "t1", "actor": "user1", "action": "sync"},
    ]

    mock_conn = AsyncMock()
    mock_conn.executemany = AsyncMock()

    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock(return_value=False))
    )
    audit_persistence._POOL = mock_pool

    result = await audit_persistence.flush_audit_entries(entries)
    assert result == 2
    mock_conn.executemany.assert_called_once()
    call_args = mock_conn.executemany.call_args
    assert "INSERT INTO audit_log" in call_args[0][0]
    assert len(call_args[0][1]) == 2
