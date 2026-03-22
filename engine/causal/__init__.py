"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [causal]
tags: [causal, edges, attribution]
owner: engine-team
status: active
--- /L9_META ---

Causal edge subsystem.
Domain-agnostic infrastructure for causal relationship types.
"""

from engine.causal.attribution import AttributionCalculator
from engine.causal.causal_compiler import CausalCompiler
from engine.causal.edge_taxonomy import CausalEdgeType, CausalEdgeValidator

__all__ = [
    "AttributionCalculator",
    "CausalCompiler",
    "CausalEdgeType",
    "CausalEdgeValidator",
]
