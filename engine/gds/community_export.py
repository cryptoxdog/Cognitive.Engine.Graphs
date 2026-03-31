"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [gds]
tags: [gds, community, export, louvain, enrich-bridge]
owner: engine-team
status: active
--- /L9_META ---

engine/gds/community_export.py

Post-Louvain hook: exports community label assignments from Neo4j back to
the GraphToEnrichReturnChannel so that community membership becomes an
enrichment field available to downstream scoring and routing.

Architecture:
    GDSScheduler._run_louvain()
        └─► execute post_job_hooks(job_type="louvain")
                └─► export_community_labels_to_enrich()
                        └─► GraphToEnrichReturnChannel.submit(envelope)
                                └─► ENRICH convergence_controller Pass N+1

FIX(RULE-2 + GAP-6): This module replaces the orphan top-level `graph/community_export.py`
reference in startup_wiring.py. All imports resolve to existing modules within engine/.
The top-level `graph/` package must not be imported anywhere in the engine.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.graph.driver import GraphDriver

from engine.graph_return_channel import (
    GraphInferenceResultEnvelope,
    GraphToEnrichReturnChannel,
    build_graph_inference_result_envelope,
)
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)

# Minimum number of nodes a community must contain before it is exported.
# Singletons and pairs carry no community signal and inflate the queue.
_MIN_COMMUNITY_SIZE: int = 3

# Confidence assigned to community-membership inference outputs.
# Lower than direct graph evidence (0.8+) but above the 0.55 CONFIDENCE_FLOOR.
_COMMUNITY_INFERENCE_CONFIDENCE: float = 0.72

# Field name written to each entity as an enrichment target.
_COMMUNITY_FIELD: str = "community_id"

# Inference rule name for provenance tracking in EnrichmentTarget.
_INFERENCE_RULE: str = "louvain_community_membership"


async def export_community_labels_to_enrich(
    driver: GraphDriver,
    tenant_id: str,
    domain_id: str,
    *,
    node_label: str = "Facility",
    community_property: str = "communityId",
    min_community_size: int = _MIN_COMMUNITY_SIZE,
) -> dict[str, Any]:
    """Export Louvain community labels as re-enrichment targets via return channel.

    Queries Neo4j for all nodes that have a community label written by the
    Louvain GDS job, then submits them as a GraphInferenceResultEnvelope to the
    GraphToEnrichReturnChannel. The convergence controller drains this channel
    at the start of each new pass and injects community_id as a seed field.

    Args:
        driver:              GraphDriver instance (already connected).
        tenant_id:           Tenant scope — every query and target is scoped here.
        domain_id:           Domain database name used in the Neo4j query.
        node_label:          Node label to query (default "Facility").
        community_property:  Property written by Louvain (default "communityId").
        min_community_size:  Exclude communities smaller than this threshold.

    Returns:
        Dict with keys: nodes_exported, communities_found, targets_enqueued.

    Raises:
        Exception: Propagates Neo4j driver errors — caller logs and continues.
    """
    safe_label = sanitize_label(node_label)
    safe_prop = sanitize_label(community_property)

    # FIX(RULE-4): ALL values use $param — zero f-string value interpolation.
    # Label and property names have been sanitized and are f-string safe per RULE-4.
    cypher = (
        f"MATCH (n:{safe_label}) "
        f"WHERE n.{safe_prop} IS NOT NULL "
        f"WITH n.{safe_prop} AS community_id, collect(n.entity_id) AS members "
        f"WHERE size(members) >= $min_size "
        f"UNWIND members AS entity_id "
        f"RETURN entity_id, community_id "
        f"ORDER BY community_id, entity_id"
    )

    results = await driver.execute_query(
        cypher=cypher,
        parameters={"min_size": min_community_size},
        database=domain_id,
    )

    if not results:
        logger.info(
            "community_export: no community labels found for tenant=%s domain=%s",
            tenant_id,
            domain_id,
        )
        return {"nodes_exported": 0, "communities_found": 0, "targets_enqueued": 0}

    # Build inference_outputs list for the envelope
    inference_outputs: list[dict[str, Any]] = []
    communities_seen: set[Any] = set()

    for row in results:
        entity_id = row.get("entity_id")
        community_id = row.get("community_id")
        if entity_id is None or community_id is None:
            continue
        communities_seen.add(community_id)
        inference_outputs.append(
            {
                "entity_id": str(entity_id),
                "field": _COMMUNITY_FIELD,
                "value": int(community_id),
                "confidence": _COMMUNITY_INFERENCE_CONFIDENCE,
                "rule": _INFERENCE_RULE,
            }
        )

    if not inference_outputs:
        logger.info(
            "community_export: zero valid rows after filtering — tenant=%s domain=%s",
            tenant_id,
            domain_id,
        )
        return {"nodes_exported": 0, "communities_found": 0, "targets_enqueued": 0}

    envelope = build_graph_inference_result_envelope(
        tenant_id=tenant_id,
        inference_outputs=inference_outputs,
    )

    channel = GraphToEnrichReturnChannel.get_instance()
    targets_enqueued = await channel.submit(envelope)

    logger.info(
        "community_export: tenant=%s domain=%s nodes=%d communities=%d targets_enqueued=%d",
        tenant_id,
        domain_id,
        len(inference_outputs),
        len(communities_seen),
        targets_enqueued,
    )
    return {
        "nodes_exported": len(inference_outputs),
        "communities_found": len(communities_seen),
        "targets_enqueued": targets_enqueued,
    }
