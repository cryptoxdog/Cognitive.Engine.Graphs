"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [chassis, actions]
owner: engine-team
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

from engine.handlers import handle_admin, handle_match, handle_sync
from engine.packet.chassis_contract import deflate_egress, inflate_ingress

logger = logging.getLogger(__name__)


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
    start_time = time.time()

    # Inflate request into PacketEnvelope
    request_packet = inflate_ingress(
        action=action,
        payload=payload,
        tenant=tenant,
        trace_id=trace_id,
        source_node="chassis",
    )

    # Route to engine handler
    handler_map = {
        "match": handle_match,
        "sync": handle_sync,
        "admin": handle_admin,
    }
    handler = handler_map.get(action)
    if not handler:
        raise ValueError(f"Unknown action: {action!r}")

    # Execute engine logic
    try:
        engine_data = await handler(tenant, payload)
        status = "success"
    except Exception as e:
        logger.exception(f"Handler {action} failed for tenant={tenant}")
        engine_data = {"error": str(e)}
        status = "failed"

    # Deflate response into PacketEnvelope
    processing_ms = (time.time() - start_time) * 1000
    _response_packet = deflate_egress(
        request=request_packet,
        engine_data=engine_data,
        status=status,
        processing_ms=processing_ms,
        engine_version="1.1.0",
        responding_node="graph-engine",
    )

    # TODO: Persist request_packet + response_packet to packet_store via memory substrate
    # (Requires memory substrate integration or direct SQL insert)

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
