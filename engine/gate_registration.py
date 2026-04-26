"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [integration]
tags: [gate, registration, sdk, startup]
owner: engine-team
status: active
--- /L9_META ---

engine/gate_registration.py — Gate self-registration hook for Cognitive.Engine.Graphs

Called from GraphLifecycle.startup() after init_dependencies().
Registration failure is intentionally non-fatal — the node starts regardless
and Gate will discover it on the next health poll.

Boot patch — add inside GraphLifecycle.startup() after init_dependencies():

    from engine.gate_registration import register_node_with_gate
    await register_node_with_gate()
"""

from __future__ import annotations

import logging

from constellation_node_sdk.registration import register_from_env

logger = logging.getLogger(__name__)


async def register_node_with_gate() -> None:
    """Attempt Gate self-registration from environment config.

    On success: Gate routing table updated immediately.
    On failure: logged as warning; node discovered on Gate health poll.
    Never raises — safe to call from inside lifecycle startup.
    """
    try:
        success = await register_from_env()
        if success:
            logger.info("gate_registration: node registered with Gate successfully")
        else:
            logger.warning(
                "gate_registration: registration returned False — "
                "node will be discovered on Gate health poll. "
                "Check GATE_URL, GATE_ADMIN_TOKEN, and engine/spec.yaml."
            )
    except Exception as exc:
        logger.warning(
            "gate_registration: unexpected error during registration (non-fatal): %s",
            exc,
        )
