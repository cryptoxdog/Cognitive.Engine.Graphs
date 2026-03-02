# chassis/__init__.py
"""
L9 Chassis Integration Layer.
Bridges HTTP boundary to engine action handlers via PacketEnvelope.
"""

from chassis.actions import execute_action

__all__ = ["execute_action"]
