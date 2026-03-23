"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [kge, embeddings]
owner: engine-team
status: active
--- /L9_META ---

Knowledge Graph Embedding (KGE) — Phase 4 module.

Provides CompoundE3D model, beam search variant discovery,
and ensemble fusion for the GRAPH Cognitive Engine.

All imports gated behind settings.kge_enabled.
"""

from engine.kge.beam_search import BeamSearchConfig, BeamSearchEngine, CascadeVariant
from engine.kge.compound_e3d import CompoundE3D, CompoundE3DConfig
from engine.kge.cross_dimensional_ensemble import (
    CrossDimensionalEnsemble,
    CrossDimensionalResult,
    DimensionalScore,
)
from engine.kge.ensemble import EnsembleController, VariantScore
from engine.kge.pareto_ensemble import ParetoEnsembleController, ParetoEnsembleResult
from engine.kge.transformations import (
    Flip,
    Hyperplane,
    Rotation,
    Scale,
    Shear,
    Transformation3D,
    Translation,
)

__all__ = [
    "BeamSearchConfig",
    "BeamSearchEngine",
    "CascadeVariant",
    "CompoundE3D",
    "CompoundE3DConfig",
    "CrossDimensionalEnsemble",
    "CrossDimensionalResult",
    "DimensionalScore",
    "EnsembleController",
    "Flip",
    "Hyperplane",
    "ParetoEnsembleController",
    "ParetoEnsembleResult",
    "Rotation",
    "Scale",
    "Shear",
    "Transformation3D",
    "Translation",
    "VariantScore",
]
