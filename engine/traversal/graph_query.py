"""
--- L9_META ---
l9_schema: 1
origin: phase2-implementation
engine: graph
layer: [traversal]
tags: [neo4j, cypher, parameterized, match, gate-lookup]
owner: engine-team
status: active
--- /L9_META ---

engine/traversal/graph_query.py

Parameterized Neo4j Query Execution.

All Cypher queries MUST be parameterized.
Never use string interpolation for query values.

Security:
  - Prevents Cypher injection
  - Enables query plan caching
  - Enforces type safety

Performance:
  - Neo4j caches parameterized query plans
  - Reduces parse overhead
"""
from __future__ import annotations

from typing import Any

import structlog

from engine.utils.security import sanitize_label

logger = structlog.get_logger("graph_query")


async def execute_match_query(
    driver: Any,
    entity_type: str,
    entity_id: str,
    dimension_keys: list[str],
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Execute CEG match query with parameterized Cypher.

    Query Pattern:
        MATCH (source {id: $entity_id})-[r:COMPATIBLE_WITH]-(target)
        WHERE source:$entity_type
        RETURN target, r.geo_score AS geo, r.temporal_score AS temporal, ...
        ORDER BY r.composite_score DESC
        LIMIT $limit

    Args:
        driver:         Neo4j driver instance
        entity_type:    Node label (e.g., "Material", "Facility")
        entity_id:      Source entity ID
        dimension_keys: Scoring dimension property names
        limit:          Max results to return

    Returns:
        List of candidate dicts with dimension scores

    Examples:
        >>> results = await execute_match_query(
        ...     driver,
        ...     entity_type="Material",
        ...     entity_id="MAT_001",
        ...     dimension_keys=["geo_score", "temporal_score"],
        ...     limit=10
        ... )
        >>> len(results) <= 10
        True
    """
    # Build RETURN clause — no value interpolation, only field names
    return_fields = ["target.id AS id", "target.name AS name"]
    for dim in dimension_keys:
        return_fields.append(f"r.{dim} AS {dim}")
    return_fields.append("target.confidence AS confidence")
    return_clause = ", ".join(return_fields)

    safe_entity_type = sanitize_label(entity_type)

    # entity_type is structural and therefore sanitized before insertion.
    # Values (entity_id, limit) always remain parameterized.
    query = "".join(
        [
            "MATCH (source {id: $entity_id})-[r:COMPATIBLE_WITH]-(target) ",
            "WHERE source:",
            safe_entity_type,
            " ",
            "RETURN ",
            return_clause,
            " ",
            "ORDER BY r.composite_score DESC ",
            "LIMIT $limit",
        ]
    )

    params = {
        "entity_id": entity_id,
        "limit": limit,
    }

    logger.info(
        "executing_match_query",
        entity_type=entity_type,
        entity_id=entity_id,
        dimensions=dimension_keys,
        limit=limit,
    )

    try:
        records = await driver.execute_query(query, params)
    except Exception as e:
        logger.error(
            "match_query_failed",
            error=str(e),
            entity_type=entity_type,
            entity_id=entity_id,
        )
        raise
    else:
        results = [dict(record) for record in records]
        logger.info("match_query_completed", results_count=len(results))
        return results


async def execute_gate_lookup(
    driver: Any,
    target_service: str,
    action: str,
) -> dict[str, Any] | None:
    """
    Lookup GATE endpoint configuration.

    Query Pattern:
        MATCH (node:GateNode {service_name: $target_service, action: $action})
        RETURN node.endpoint AS endpoint, node.timeout_ms AS timeout_ms

    Args:
        driver:         Neo4j driver instance
        target_service: Target service name (e.g., "ceg-engine")
        action:         Action name (e.g., "match")

    Returns:
        Endpoint config dict or None if not found

    Examples:
        >>> config = await execute_gate_lookup(driver, "ceg-engine", "match")
        >>> config["endpoint"]
        'http://ceg-engine:8000/v1/execute'
    """
    query = """
    MATCH (node:GateNode {service_name: $target_service, action: $action})
    RETURN node.endpoint AS endpoint, node.timeout_ms AS timeout_ms
    """
    params = {"target_service": target_service, "action": action}

    logger.info("gate_lookup", target_service=target_service, action=action)

    try:
        records = await driver.execute_query(query, params)
    except Exception as e:
        logger.error(
            "gate_lookup_failed",
            error=str(e),
            target_service=target_service,
            action=action,
        )
        raise
    else:
        if not records:
            logger.warning("gate_not_found", target_service=target_service, action=action)
            return None
        result = dict(records[0])
        logger.info("gate_found", endpoint=result.get("endpoint"))
        return result
