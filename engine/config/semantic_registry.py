"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [config, semantic-registry]
owner: engine-team
status: active
--- /L9_META ---
"""

from __future__ import annotations

from dataclasses import dataclass

CANONICAL_ENTITY_TYPES = {
    "company",
    "person",
    "facility",
    "product",
    "transaction",
    "market",
}


@dataclass(frozen=True)
class SemanticRegistry:
    allowed_types: set[str]

    def is_allowed(self, canonical_label: str) -> bool:
        return canonical_label in self.allowed_types


DEFAULT_SEMANTIC_REGISTRY = SemanticRegistry(allowed_types=CANONICAL_ENTITY_TYPES)
