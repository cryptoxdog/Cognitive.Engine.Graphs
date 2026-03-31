"""
GAP-5 FIX: Wire db_pool into ComplianceEngine so flush_audit() persists
to PostgreSQL instead of warning db_pool=None.

Call configure_audit_pool(pool) at app startup after asyncpg.create_pool().
"""
from __future__ import annotations
import logging, time
from typing import Any

import asyncpg  # type: ignore

logger = logging.getLogger(__name__)

_POOL: asyncpg.Pool | None = None

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   TEXT             NOT NULL,
    actor       TEXT             NOT NULL,
    action      TEXT             NOT NULL,
    detail      TEXT,
    created_at  DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_created
    ON audit_log (tenant_id, created_at DESC);
"""


async def configure_audit_pool(pool: asyncpg.Pool) -> None:
    """Call once at startup after asyncpg.create_pool()."""
    global _POOL
    _POOL = pool
    async with pool.acquire() as conn:
        await conn.execute(_CREATE_TABLE_SQL)
    logger.info("audit_persistence: PostgreSQL pool configured and schema verified")


async def flush_audit_entries(entries: list[dict[str, Any]]) -> int:
    """
    Persist audit entries to PostgreSQL.
    Replaces the warning-only stub in ComplianceEngine.flush_audit().
    Returns count of rows inserted.
    """
    if _POOL is None:
        logger.error(
            "flush_audit_entries called but db_pool is None — "
            "call configure_audit_pool() at startup. Entries dropped: %d",
            len(entries),
        )
        return 0
    if not entries:
        return 0

    rows = [
        (
            e.get("tenant_id", "unknown"),
            e.get("actor", "system"),
            e.get("action", "unknown"),
            e.get("detail"),
            e.get("created_at", time.time()),
        )
        for e in entries
    ]
    async with _POOL.acquire() as conn:
        await conn.executemany(
            "INSERT INTO audit_log (tenant_id, actor, action, detail, created_at) "
            "VALUES ($1, $2, $3, $4, $5)",
            rows,
        )
    logger.debug("audit_persistence: flushed %d entries to PostgreSQL", len(rows))
    return len(rows)
