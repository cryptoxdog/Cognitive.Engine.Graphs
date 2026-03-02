"""
engine/gates/registry.py
Maps GateType enum values → gate implementation classes.
Used by CompositeGate for recursive subgate compilation.
"""
from __future__ import annotations

from engine.config.schema import GateType
from engine.gates.types.all_gates import (
    BaseGate,
    BooleanGate,
    CompositeGate,
    EnumMapGate,
    ExclusionGate,
    FreshnessGate,
    RangeGate,
    SelfRangeGate,
    TemporalRangeGate,
    ThresholdGate,
    TraversalGate,
)


class GateRegistry:
    """Static registry mapping GateType → gate implementation class."""

    _REGISTRY: dict[GateType, type[BaseGate]] = {
        GateType.RANGE: RangeGate,
        GateType.THRESHOLD: ThresholdGate,
        GateType.BOOLEAN: BooleanGate,
        GateType.COMPOSITE: CompositeGate,
        GateType.ENUMMAP: EnumMapGate,
        GateType.EXCLUSION: ExclusionGate,
        GateType.SELFRANGE: SelfRangeGate,
        GateType.FRESHNESS: FreshnessGate,
        GateType.TEMPORALRANGE: TemporalRangeGate,
        GateType.TRAVERSAL: TraversalGate,
    }

    @classmethod
    def get_gate_class(cls, gate_type: GateType) -> type[BaseGate]:
        """
        Look up gate implementation class by GateType enum.

        Raises:
            ValueError: If gate_type has no registered implementation.
        """
        gate_class = cls._REGISTRY.get(gate_type)
        if gate_class is None:
            raise ValueError(f"No gate implementation registered for type: {gate_type!r}")
        return gate_class
