"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [scoring]
owner: engine-team
status: active
--- /L9_META ---

Scoring system."""
from engine.scoring.assembler import ScoringAssembler

__all__ = ["ScoringAssembler"]


