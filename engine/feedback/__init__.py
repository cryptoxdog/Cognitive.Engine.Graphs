"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [feedback]
tags: [feedback, convergence, signal-weights]
owner: engine-team
status: active
--- /L9_META ---

Outcome feedback loop engine.
Closes the gap between handle_outcomes and the scoring/matching pipeline.
Signal weight retraining and convergence.
"""

from engine.feedback.convergence import ConvergenceLoop
from engine.feedback.pattern_matcher import ConfigurationMatcher
from engine.feedback.score_propagator import ScorePropagator
from engine.feedback.signal_weights import SignalWeightCalculator

__all__ = [
    "ConfigurationMatcher",
    "ConvergenceLoop",
    "ScorePropagator",
    "SignalWeightCalculator",
]
