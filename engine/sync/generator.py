"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [sync, cypher, merge]
owner: engine-team
status: active
--- /L9_META ---

Sync generator: Spec -> UNWIND MERGE/MATCH SET Cypher.
Generates batch sync queries from domain sync endpoint specs.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.config.schema import DomainSpec, SyncEndpointSpec, SyncStrategy
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


class SyncGenerator:
    """Generates batch sync Cypher queries."""

    def __init__(self, domain_spec: DomainSpec) -> None:
        self.domain_spec = domain_spec

    def generate_sync_query(
        self,
        endpoint_spec: SyncEndpointSpec,
        batch_data: list[dict[str, Any]],
    ) -> str:
        """Generate batch sync Cypher query."""
        if endpoint_spec.batchstrategy == SyncStrategy.UNWINDMERGE:
            return self._generate_unwind_merge(endpoint_spec)
        if endpoint_spec.batchstrategy == SyncStrategy.UNWINDMATCHSET:
            return self._generate_unwind_match_set(endpoint_spec)
        raise ValueError(f"Unknown sync strategy: {endpoint_spec.batchstrategy}")

    def _generate_unwind_merge(self, spec: SyncEndpointSpec) -> str:
        if not spec.targetnode:
            raise ValueError(f"Endpoint '{spec.path}': targetnode required for MERGE")
        if not spec.idproperty:
            raise ValueError(f"Endpoint '{spec.path}': idproperty required for MERGE")

        sanitized_target = sanitize_label(spec.targetnode)
        sanitized_id = sanitize_label(spec.idproperty)
        cypher_parts = [
            "UNWIND $batch AS row",
            f"MERGE (n:{sanitized_target} {{{sanitized_id}: row.{sanitized_id}}})",
            "SET n += row, n._tenant = $tenant",
        ]

        if spec.taxonomyedges:
            for tax_edge in spec.taxonomyedges:
                sanitized_tax_label = sanitize_label(tax_edge.targetlabel)
                sanitized_edge_type = sanitize_label(tax_edge.edgetype)
                sanitized_target_id = sanitize_label(tax_edge.targetid)
                sanitized_field = sanitize_label(tax_edge.field)
                cypher_parts.extend(
                    [
                        "WITH n, row",
                        f"OPTIONAL MATCH (tax:{sanitized_tax_label} {{{sanitized_target_id}: row.{sanitized_field}}})",
                        "FOREACH (_ IN CASE WHEN tax IS NOT NULL THEN [1] ELSE [] END |",
                        f"  MERGE (n)-[:{sanitized_edge_type}]->(tax)",
                        ")",
                    ]
                )

        if spec.childsync:
            for child in spec.childsync:
                sanitized_child_node = sanitize_label(child.targetnode)
                sanitized_child_edge = sanitize_label(child.edgetype)
                sanitized_child_field = sanitize_label(child.field)
                sanitized_child_target_id = sanitize_label(child.targetid)
                direction = "->" if child.edgedirection == "parenttochild" else "<-"
                cypher_parts.extend(
                    [
                        "WITH n, row",
                        f"UNWIND coalesce(row.{sanitized_child_field}, []) AS child_row",
                        f"MERGE (c:{sanitized_child_node} {{{sanitized_child_target_id}: child_row.{sanitized_child_target_id}}})",
                        "SET c += child_row, c._tenant = $tenant",
                        f"MERGE (n)-[:{sanitized_child_edge}]{direction}(c)",
                    ]
                )

        return "\n".join(cypher_parts)

    def _generate_unwind_match_set(self, spec: SyncEndpointSpec) -> str:
        if not spec.targetnode:
            raise ValueError(f"Endpoint '{spec.path}': targetnode required")
        if not spec.idproperty:
            raise ValueError(f"Endpoint '{spec.path}': idproperty required")

        sanitized_target = sanitize_label(spec.targetnode)
        sanitized_id = sanitize_label(spec.idproperty)
        cypher_parts = [
            "UNWIND $batch AS row",
            f"MATCH (n:{sanitized_target} {{{sanitized_id}: row.{sanitized_id}}})",
        ]

        if spec.fieldsupdated:
            set_clauses = [f"n.{sanitize_label(field)} = row.{sanitize_label(field)}" for field in spec.fieldsupdated]
            set_clauses.append("n._tenant = $tenant")
            set_clauses.append("n.updated_at = datetime()")
            cypher_parts.append("SET " + ",\n    ".join(set_clauses))
        else:
            cypher_parts.append("SET n += row, n._tenant = $tenant")

        return "\n".join(cypher_parts)
