# --- L9_META ---
# l9_schema: 1
# origin: engine-specific
# engine: graph
# layer: [kge]
# tags: [kge, compound-e3d, embeddings, phase-4]
# owner: engine-team
# status: active
# --- /L9_META ---
# engine/kge/__init__.py
"""
Knowledge Graph Embedding (KGE) — Phase 4 module.

Provides CompoundE3D model, beam search variant discovery,
and ensemble fusion for the GRAPH Cognitive Engine.

All imports gated behind settings.kge_enabled.
"""

from engine.kge.beam_search import BeamSearchConfig, BeamSearchEngine
from engine.kge.compound_e3d import CompoundE3D, CompoundE3DConfig
from engine.kge.ensemble import EnsembleController, VariantScore
from engine.kge.transformations import (
    Flip,
    Hyperplane,
    Rotation,
    Scale,
    Transformation3D,
    Translation,
)

__all__ = [
    "BeamSearchConfig",
    "BeamSearchEngine",
    "CompoundE3D",
    "CompoundE3DConfig",
    "EnsembleController",
    "Flip",
    "Hyperplane",
    "Rotation",
    "Scale",
    "Transformation3D",
    "Translation",
    "VariantScore",
]
