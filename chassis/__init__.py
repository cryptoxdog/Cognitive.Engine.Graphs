# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [config]
# tags: [chassis]
# owner: engine-team
# status: active
# --- /L9_META ---
# chassis/__init__.py
"""
L9 Chassis Integration Layer.
Bridges HTTP boundary to engine action handlers via PacketEnvelope.
"""

from chassis.actions import execute_action
from chassis.app import create_app

__all__ = ["execute_action", "create_app"]
