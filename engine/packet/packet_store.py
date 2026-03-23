"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [packet]
tags: [packet, audit, persistence]
owner: engine-team
status: active
--- /L9_META ---

engine/packet/packet_store.py
PacketStore — async persistence interface for PacketEnvelope audit trail.

Currently a no-op stub. Wire to asyncpg + packet_store.sql schema post-MVP.
Tracking: implement with PostgreSQL/pgvector memory substrate integration.
"""

from __future__ import annotations

import logging

from engine.packet.packet_envelope import PacketEnvelope

logger = logging.getLogger(__name__)

_PACKET_STORE_ENABLED = False  # Flip to True when DB integration is wired


class PacketStore:
    """Async persistence layer for PacketEnvelope request/response pairs."""

    async def persist(
        self,
        request: PacketEnvelope,
        response: PacketEnvelope,
    ) -> None:
        """Persist an immutable request/response PacketEnvelope pair.

        Currently a no-op stub. When enabled, writes to packet_store
        PostgreSQL schema defined in engine/packet/packet_store.sql.
        """
        if not _PACKET_STORE_ENABLED:
            logger.debug(
                "PacketStore is disabled (stub mode). packet_id=%s",
                request.packet_id,
            )
            return
        logger.warning("PacketStore persistence not yet implemented")


# Module-level singleton — inject into execute_action via dependency
_packet_store = PacketStore()


def get_packet_store() -> PacketStore:
    """Return the module-level PacketStore singleton."""
    return _packet_store
