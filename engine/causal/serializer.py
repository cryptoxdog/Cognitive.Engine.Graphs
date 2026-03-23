"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [causal]
tags: [causal, serializer, bfs, explanation]
owner: engine-team
status: active
--- /L9_META ---

BFS-based causal subgraph serialization for match explanations.

Reference: Jiang et al. (2023) "ReasoningLM: Enabling Structural Subgraph
Reasoning in Pre-trained Language Models", Section 4.2.1.
Converts a subgraph into a flat sequence preserving structural information.
"""

from __future__ import annotations

from typing import Any

import structlog

from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver
from engine.utils.security import sanitize_label

logger = structlog.get_logger(__name__)


class CausalSubgraphSerializer:
    """
    Serializes the causal neighborhood around a node using BFS.

    Produces a human-readable explanation of why a candidate was selected,
    preserving structural information from the causal subgraph.
    """

    def __init__(self, graph_driver: GraphDriver, domain_spec: DomainSpec) -> None:
        self._driver = graph_driver
        self._spec = domain_spec
        self._db = domain_spec.domain.id

    async def serialize_neighborhood(
        self,
        node_id: str,
        node_label: str,
        max_depth: int = 2,
        max_nodes: int = 20,
    ) -> dict[str, Any]:
        """
        BFS from node_id, collecting edges and properties.

        Returns:
        - serialized: human-readable path string
        - nodes_visited: count of unique nodes
        - edges_traversed: list of edge types encountered
        - depth_reached: actual BFS depth
        """
        safe_label = sanitize_label(node_label)

        # Build causal edge pattern from domain spec
        causal_spec = self._spec.causal
        if causal_spec.causal_edges:
            safe_types = [sanitize_label(e.edge_type) for e in causal_spec.causal_edges]
            edge_filter = "|".join(safe_types)
            rel_pattern = f"[r:{edge_filter}]"
        else:
            rel_pattern = "[r]"

        cypher = f"""
        MATCH (start:{safe_label} {{entity_id: $node_id}})
        CALL {{
            WITH start
            MATCH path = (start)-{rel_pattern}->(neighbor)
            WITH path, length(path) AS depth
            WHERE depth <= $max_depth
            RETURN path, depth
            ORDER BY depth ASC
            LIMIT $max_nodes
        }}
        WITH path, depth,
             [n IN nodes(path) | {{id: n.entity_id, label: labels(n)[0], name: coalesce(n.name, n.entity_id)}}] AS path_nodes,
             [r IN relationships(path) | {{type: type(r), confidence: coalesce(r.confidence, 0.0)}}] AS path_rels
        RETURN path_nodes, path_rels, depth
        ORDER BY depth ASC
        """

        try:
            results = await self._driver.execute_query(
                cypher,
                parameters={
                    "node_id": node_id,
                    "max_depth": max_depth,
                    "max_nodes": max_nodes,
                },
                database=self._db,
            )
        except Exception:
            logger.warning(
                "causal_serialization_failed",
                node_id=node_id,
                node_label=node_label,
            )
            return {
                "serialized": "",
                "nodes_visited": 0,
                "edges_traversed": [],
                "depth_reached": 0,
            }

        if not results:
            return {
                "serialized": "",
                "nodes_visited": 0,
                "edges_traversed": [],
                "depth_reached": 0,
            }

        # Collect unique nodes and edges, build serialized string
        visited_nodes: set[str] = set()
        edge_types: list[str] = []
        path_strings: list[str] = []
        max_depth_seen = 0

        for record in results:
            path_nodes = record.get("path_nodes", [])
            path_rels = record.get("path_rels", [])
            depth = record.get("depth", 0)
            max_depth_seen = max(max_depth_seen, depth)

            # Build path string: Node[id] -[REL_TYPE]-> Node[id]
            parts: list[str] = []
            for i, node in enumerate(path_nodes):
                node_str = f"{node.get('label', '?')}[{node.get('name', '?')}]"
                visited_nodes.add(str(node.get("id", "")))
                parts.append(node_str)
                if i < len(path_rels):
                    rel = path_rels[i]
                    rel_type = rel.get("type", "?")
                    edge_types.append(rel_type)
                    parts.append(f"-[{rel_type}]->")

            path_str = " ".join(parts)
            if path_str and path_str not in path_strings:
                path_strings.append(path_str)

        serialized = "; ".join(path_strings)

        return {
            "serialized": serialized,
            "nodes_visited": len(visited_nodes),
            "edges_traversed": list(dict.fromkeys(edge_types)),
            "depth_reached": max_depth_seen,
        }
