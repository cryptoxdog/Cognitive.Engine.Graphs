"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [hoprag]
tags: [hoprag, subsystem, init]
owner: engine-team
status: active
--- /L9_META ---

HopRAG subsystem for Cognitive Engine Graphs.

Provides multi-hop reasoning-augmented graph retrieval capabilities
based on HopRAG (ACL 2025). This subsystem adds:

- Graph-structured index construction with pseudo-queries on edges
- Multi-hop BFS traversal with optional LLM-guided reasoning
- Helpfulness scoring combining similarity and traversal importance
- Edge density control for sparse, traversal-friendly graphs

All features are gated behind ``settings.hoprag_enabled`` and configured
via the ``hoprag:`` section of domain-spec YAML.

Quick start::

    from engine.hoprag.config import HopRAGConfig
    from engine.scoring.helpfulness import HelpfulnessScorer
    from engine.scoring.importance import ImportanceScorer
    from engine.traversal.multihop import MultiHopTraverser

    config = HopRAGConfig()
    scorer = HelpfulnessScorer(alpha=config.alpha)
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = [
    "HopRAGConfig",
]

from engine.hoprag.config import HopRAGConfig
