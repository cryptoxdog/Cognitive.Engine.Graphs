"""
GAP-6 FIX: Export Louvain community labels from Neo4j back to ENRICH
as known_fields context so convergence_controller uses them in Pass N+1.

Attach to GDSScheduler post-job completion hook for "louvain" jobs.
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def export_community_labels_to_enrich(
    graph_driver,
    tenant_id: str,
    domain_id: str,
) -> dict[str, Any]:
    """
    Query Neo4j for community labels from the last Louvain run, then submit
    them to GraphToEnrichReturnChannel as enrichment targets.
    """
    from engine.graph_return_channel import (
        GraphToEnrichReturnChannel,
        build_graph_inference_result_envelope,
    )

    cypher = """
    MATCH (n)
    WHERE n.tenant = $tenant AND n.community_id IS NOT NULL
    RETURN n.entity_id AS entity_id, n.community_id AS community_id
    LIMIT 10000
    """
    try:
        records = await graph_driver.execute_query(
            cypher=cypher,
            parameters={"tenant": tenant_id},
            database=domain_id,
        )
    except Exception:
        logger.exception(
            "community_export: failed to query community labels tenant=%s", tenant_id
        )
        return {"status": "error", "exported": 0}

    if not records:
        logger.debug("community_export: no community labels for tenant=%s", tenant_id)
        return {"status": "ok", "exported": 0}

    inference_outputs = [
        {
            "entity_id": r["entity_id"],
            "field": "community_id",
            "value": r["community_id"],
            "confidence": 0.95,   # Louvain is deterministic
            "rule": "louvain_community_detection",
        }
        for r in records
        if r.get("entity_id") and r.get("community_id") is not None
    ]

    if not inference_outputs:
        return {"status": "ok", "exported": 0}

    envelope = build_graph_inference_result_envelope(
        tenant_id=tenant_id,
        inference_outputs=inference_outputs,
    )
    channel = GraphToEnrichReturnChannel.get_instance()
    count = await channel.submit(envelope)
    logger.info(
        "community_export: submitted %d community label targets tenant=%s",
        count, tenant_id,
    )
    return {"status": "ok", "exported": count, "packet_id": envelope.packet_id}
