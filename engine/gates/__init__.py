# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [config]
# tags: [gates]
# owner: engine-team
# status: active
# --- /L9_META ---
# engine/gates/__init__.py
"""Gate compilation and execution system."""

from engine.gates.compiler import GateCompiler
from engine.gates.null_semantics import NullHandler

__all__ = [
    "GateCompiler",
    "NullHandler",
]
