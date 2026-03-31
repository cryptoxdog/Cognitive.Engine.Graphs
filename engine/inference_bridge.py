"""
--- L9_META ---
l9_schema: 1
origin: gap-fix
engine: graph
layer: [inference]
tags: [deprecated, guard, v1, bridge]
owner: engine-team
status: deprecated
--- /L9_META ---

engine/inference_bridge.py

GAP-9 FIX: Guard against silent use of inference_bridge.py (v1).
Any direct import of the v1 bridge now raises ImportError with a
migration path pointing to inference_bridge_v2.py (DAG engine).

This file REPLACES the v1 bridge.
"""
raise ImportError(
    "engine.inference_bridge (v1) is deprecated and disabled. "
    "It bypasses the DerivationGraph DAG engine, causing inference to fire outside "
    "the topological sort order with no unlock-value targeting. "
    "Migrate all callers to: from engine.inference_bridge_v2 import DerivationGraph"
)
