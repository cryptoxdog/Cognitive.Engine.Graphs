"""
Sync generator: Spec → UNWIND MERGE/MATCH SET Cypher.
Generates batch sync queries from domain sync endpoint specs.
"""

import logging
from typing import Any

from engine.config.schema import DomainSpec, SyncEndpointSpec, SyncStrategy
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)


class SyncGenerator:
    """Generates batch sync Cypher queries."""

    def __init__(self, domain_spec: DomainSpec):
        self.domain_spec = domain_spec

    def generate_sync_query(
        self,
        endpoint_spec: SyncEndpointSpec,
        batch_data: list[dict[str, Any]],
    ) -> str:
        """
        Generate batch sync Cypher query.

        Args:
            endpoint_spec: Sync endpoint specification
            batch_data: List of entities to sync

        Returns:
            Cypher UNWIND query
        """
        if endpoint_spec.batchstrategy == SyncStrategy.UNWINDMERGE:
            return self._generate_unwind_merge(endpoint_spec)
        elif endpoint_spec.batchstrategy == SyncStrategy.UNWINDMATCHSET:
            return self._generate_unwind_match_set(endpoint_spec)
        else:
            raise ValueError(f"Unknown sync strategy: {endpoint_spec.batchstrategy}")

    def _generate_unwind_merge(self, spec: SyncEndpointSpec) -> str:
        """
        Generate UNWIND MERGE query (create or update).

        Example:
        UNWIND $batch AS row
        MERGE (n:LoanProduct {productid: row.productid})
        SET n += row
        WITH n, row
        MATCH (lender:Lender {lenderid: row.lenderid})
        MERGE (n)-[:OFFEREDBY]->(lender)
        """
        if not spec.targetnode:
            raise ValueError(f"Endpoint '{spec.path}': targetnode required for MERGE")
        if not spec.idproperty:
            raise ValueError(f"Endpoint '{spec.path}': idproperty required for MERGE")

        # SECURITY: Sanitize labels to prevent Cypher injection
        sanitized_target = sanitize_label(spec.targetnode)

        cypher_parts = [
            "UNWIND $batch AS row",
            f"MERGE (n:{sanitized_target} {{{spec.idproperty}: row.{spec.idproperty}}})",
            "SET n += row",
        ]

        # Add taxonomy edge creation
        if spec.taxonomyedges:
            for tax_edge in spec.taxonomyedges:
                sanitized_tax_label = sanitize_label(tax_edge.targetlabel)
                sanitized_edge_type = sanitize_label(tax_edge.edgetype)
                cypher_parts.extend(
                    [
                        "WITH n, row",
                        f"OPTIONAL MATCH (tax:{sanitized_tax_label} {{{tax_edge.targetid}: row.{tax_edge.field}}})",
                        "FOREACH (_ IN CASE WHEN tax IS NOT NULL THEN [1] ELSE [] END |",
                        f"  MERGE (n)-[:{sanitized_edge_type}]->(tax)",
                        ")",
                    ]
                )

        # Add child sync
        if spec.childsync:
            for child in spec.childsync:
                sanitized_child_node = sanitize_label(child.targetnode)
                sanitized_child_edge = sanitize_label(child.edgetype)
                direction = "->" if child.edgedirection == "parenttochild" else "<-"
                cypher_parts.extend(
                    [
                        "WITH n, row",
                        f"UNWIND coalesce(row.{child.field}, []) AS child_row",
                        f"MERGE (c:{sanitized_child_node} {{{child.targetid}: child_row.{child.targetid}}})",
                        "SET c += child_row",
                        f"MERGE (n)-[:{sanitized_child_edge}]{direction}(c)",
                    ]
                )

        return "\n".join(cypher_parts)

    def _generate_unwind_match_set(self, spec: SyncEndpointSpec) -> str:
        """
        Generate UNWIND MATCH SET query (update only, no create).

        Example:
        UNWIND $batch AS row
        MATCH (n:LoanProduct {productid: row.productid})
        SET n.currentpipelinecount = row.currentpipelinecount,
            n.updated_at = datetime()
        """
        if not spec.targetnode:
            raise ValueError(f"Endpoint '{spec.path}': targetnode required")
        if not spec.idproperty:
            raise ValueError(f"Endpoint '{spec.path}': idproperty required")

        # SECURITY: Sanitize labels to prevent Cypher injection
        sanitized_target = sanitize_label(spec.targetnode)

        cypher_parts = [
            "UNWIND $batch AS row",
            f"MATCH (n:{sanitized_target} {{{spec.idproperty}: row.{spec.idproperty}}})",
        ]

        # Build SET clause from fieldsupdated
        if spec.fieldsupdated:
            set_clauses = [f"n.{field} = row.{field}" for field in spec.fieldsupdated]
            set_clauses.append("n.updated_at = datetime()")
            cypher_parts.append("SET " + ",\n    ".join(set_clauses))
        else:
            # Update all fields
            cypher_parts.append("SET n += row")

        return "\n".join(cypher_parts)
