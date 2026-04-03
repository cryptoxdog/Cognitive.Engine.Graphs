"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [causal]
tags: [causal, compiler, cypher]
owner: engine-team
status: active
--- /L9_META ---

Causal edge compiler.
Compiles causal edge declarations from domain spec into parameterized Cypher.
"""

from __future__ import annotations

import logging

from engine.config.schema import CausalEdgeSpec, DomainSpec
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


class CausalCompiler:
    """
    Compiles causal edge declarations from domain spec into
    Cypher MERGE patterns with temporal validation.

    Similar to GateCompiler for gates -- takes spec declarations
    and produces parameterized Cypher.
    """

    def __init__(self, domain_spec: DomainSpec) -> None:
        self._spec = domain_spec
        self._causal_spec = domain_spec.causal

    def compile_causal_edge_create(
        self,
        edge_spec: CausalEdgeSpec,
    ) -> str:
        """
        Generate Cypher for creating a causal edge with validation.

        All labels are sanitized. Values use parameterized queries.
        Temporal validation is included when edge_spec.temporal_validation is True.
        """
        source_label = sanitize_label(edge_spec.source_label)
        target_label = sanitize_label(edge_spec.target_label)
        edge_type = sanitize_label(edge_spec.edge_type)

        temporal_clause = ""
        if edge_spec.temporal_validation:
            temporal_clause = "WHERE source.created_at < target.created_at\n"

        confidence_clause = ""
        if edge_spec.confidence_threshold > 0.0:
            confidence_clause = f"AND $confidence >= {edge_spec.confidence_threshold}\n"

        cypher = (
            "MATCH (source:"
            + source_label
            + " {entity_id: $source_id})\n"
            + "MATCH (target:"
            + target_label
            + " {entity_id: $target_id})\n"
            + temporal_clause
            + confidence_clause
            + "MERGE (source)-[r:"
            + edge_type
            + " {\n"
            + "    confidence: $confidence,\n"
            + "    mechanism: $mechanism,\n"
            + "    created_at: datetime()\n"
            + "}]->(target)\n"
            + "RETURN r"
        )

        return cypher

    def compile_causal_chain_query(
        self,
        root_label: str,
        edge_types: list[str] | None = None,
        max_depth: int | None = None,
    ) -> str:
        """
        Generate Cypher for traversing causal chains from a root node.

        Uses variable-length path patterns to discover causal chains
        up to the configured depth limit.
        """
        safe_root = sanitize_label(root_label)
        depth = max_depth or self._causal_spec.chain_depth_limit

        if edge_types:
            safe_types = [sanitize_label(t) for t in edge_types]
            edge_pattern = "|".join(safe_types)
            rel_pattern = f"[:{edge_pattern}*1..{depth}]"
        # Use all causal edge types from the spec
        elif self._causal_spec.causal_edges:
            safe_types = [sanitize_label(e.edge_type) for e in self._causal_spec.causal_edges]
            edge_pattern = "|".join(safe_types)
            rel_pattern = f"[:{edge_pattern}*1..{depth}]"
        else:
            rel_pattern = f"[*1..{depth}]"

        cypher = (
            f"MATCH path = (root:{safe_root})-{rel_pattern}->(effect)\n"
            f"RETURN root, nodes(path) AS chain_nodes,\n"
            f"       relationships(path) AS chain_edges,\n"
            f"       length(path) AS chain_depth\n"
            f"ORDER BY chain_depth DESC"
        )

        return cypher

    def compile_all_edge_creates(self) -> list[tuple[CausalEdgeSpec, str]]:
        """Compile Cypher for all causal edges declared in the domain spec."""
        compiled: list[tuple[CausalEdgeSpec, str]] = []
        for edge_spec in self._causal_spec.causal_edges:
            cypher = self.compile_causal_edge_create(edge_spec)
            compiled.append((edge_spec, cypher))
        return compiled
