"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [integration]
tags: [gate, transport, outbound, sdk]
owner: engine-team
status: active
--- /L9_META ---

engine/gate_client.py — Gate_SDK client singleton for Cognitive.Engine.Graphs

All outbound inter-node calls MUST route through get_gate_client().
No raw HTTP calls to peer nodes are permitted (L9: raw_http_inter_node_calls).

Usage:
    from engine.gate_client import get_gate_client
    client = get_gate_client()
    response_packet = await client.send_to_gate(packet)
"""

from __future__ import annotations

import logging

from constellation_node_sdk.client import GateClient
from constellation_node_sdk.config import get_gate_client_config_from_env

logger = logging.getLogger(__name__)

_gate_client: GateClient | None = None


def get_gate_client() -> GateClient:
    """Return the process-level GateClient singleton.

    Lazily initialised on first call.
    Raises ValueError if GATE_URL is not configured.
    """
    global _gate_client
    if _gate_client is None:
        config = get_gate_client_config_from_env()
        _gate_client = GateClient(config)
        logger.info(
            "GateClient initialised: gate_url=%s local_node=%s",
            config.gate_url,
            config.local_node,
        )
    return _gate_client


def reset_gate_client() -> None:
    """Reset the singleton — for use in tests only."""
    global _gate_client
    _gate_client = None
