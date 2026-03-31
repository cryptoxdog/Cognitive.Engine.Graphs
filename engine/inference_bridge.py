"""
GAP-9 FIX: Replace engine/inference_bridge.py with this file.

Any direct import of the v1 bridge now raises ImportError immediately,
forcing all callers to migrate to inference_bridge_v2.py (DAG engine).

This eliminates silent bypass of the DerivationGraph topological sort
and unlock-value targeting that the v1 bridge was causing.
"""
raise ImportError(
    "engine.inference_bridge (v1) is DISABLED.\n\n"
    "It bypasses the DerivationGraph DAG engine, causing inference to fire "
    "outside topological sort order with no unlock-value targeting.\n\n"
    "Migrate all callers to:\n"
    "  from engine.inference_bridge_v2 import DerivationGraph\n\n"
    "See docs/migration/inference_bridge_v2.md for the migration guide."
)
