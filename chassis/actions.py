"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api]
tags: [chassis, actions]
owner: platform-team
status: active
--- /L9_META ---

chassis/actions.py
Chassis integration: inflate requests, call engine handlers, deflate responses.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Lazy-loaded engine components (initialized on first use)
_engine_handlers: dict[str, Any] | None = None
_inflate_ingress: Any = None
_deflate_egress: Any = None


def _init_engine() -> None:
    """Lazy-initialize engine handlers and packet functions."""
    global _engine_handlers, _inflate_ingress, _deflate_egress

    if _engine_handlers is not None:
        return

    try:
        from engine.handlers import (
            handle_admin,
            handle_enrich,
            handle_health,
            handle_healthcheck,
            handle_match,
            handle_outcomes,
            handle_resolve,
            handle_sync,
        )
        from engine.packet.chassis_contract import deflate_egress, inflate_ingress

        _engine_handlers = {
            "match": handle_match,
            "sync": handle_sync,
            "admin": handle_admin,
            "outcomes": handle_outcomes,
            "resolve": handle_resolve,
            "health": handle_health,
            "healthcheck": handle_healthcheck,
            "enrich": handle_enrich,
        }
        _inflate_ingress = inflate_ingress
        _deflate_egress = deflate_egress
        logger.info("Engine handlers initialized: %d actions registered", len(_engine_handlers))
    except ImportError as e:
        logger.error(f"Failed to import engine handlers: {e}")
        _engine_handlers = {}
        raise RuntimeError("Engine initialization failed") from e


def _get_engine_error_class() -> type | None:
    """Get EngineError class if available (for error type checking)."""
    try:
        from engine.handlers import EngineError
    except ImportError:
        return None
    else:
        return EngineError


async def execute_action(
    action: str,
    payload: dict[str, Any],
    tenant: str,
    trace_id: str,
) -> dict[str, Any]:
    """
    Chassis entrypoint: POST /v1/execute

    1. Inflate inbound JSON → PacketEnvelope (request)
    2. Route to engine handler by action
    3. Execute handler
    4. Deflate engine response → PacketEnvelope (response)
    5. Return outbound envelope as JSON
    """
    # Lazy-initialize engine on first call
    _init_engine()

    start_time = time.time()

    # Inflate request into PacketEnvelope
    request_packet = _inflate_ingress(
        action=action,
        payload=payload,
        tenant=tenant,
        trace_id=trace_id,
        source_node="chassis",
    )

    # Route to engine handler
    handler = _engine_handlers.get(action) if _engine_handlers else None
    if not handler:
        raise ValueError(f"Unknown action: {action!r}")

    # Execute engine logic
    engine_error_cls = _get_engine_error_class()
    try:
        engine_data = await handler(tenant, payload)
        status = "success"
    except Exception as e:
        if engine_error_cls is not None and isinstance(e, engine_error_cls):
            logger.warning(f"Engine error in {action}: {e}")
        else:
            logger.exception(f"Handler {action} failed for tenant={tenant}")
        engine_data = {"error": str(e)}
        status = "failed"

    # Deflate response into PacketEnvelope
    processing_ms = (time.time() - start_time) * 1000
    _response_packet = _deflate_egress(
        request=request_packet,
        engine_data=engine_data,
        status=status,
        processing_ms=processing_ms,
        engine_version="1.1.0",
        responding_node="graph-engine",
    )

    # DEFERRED: Persist request_packet + response_packet to packet_store via memory substrate
    # Tracking: https://github.com/cryptoxdog/Cognitive.Engine.Graphs/issues/TBD
    # Reason: Requires memory substrate integration (PostgreSQL + PacketStore schema)
    # Priority: Post-MVP - audit trail enhancement

    # Return outbound envelope as JSON
    return {
        "status": status,
        "action": action,
        "tenant": tenant,
        "data": engine_data,
        "meta": {
            "trace_id": trace_id,
            "execution_ms": processing_ms,
            "version": "1.1.0",
            "timestamp": datetime.now(UTC).isoformat(),
        },
    }
