"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [diagnostics]
tags: [diagnostics, fingerprint, drift, dissimilarity]
owner: engine-team
status: active
--- /L9_META ---

Algorithmic diagnostics for persona composition and drift detection.
"""

from engine.diagnostics.dissimilarity import chi_squared_dissimilarity, detect_drift
from engine.diagnostics.fingerprint import AlgorithmicFingerprint, compute_fingerprint

__all__ = [
    "AlgorithmicFingerprint",
    "chi_squared_dissimilarity",
    "compute_fingerprint",
    "detect_drift",
]
