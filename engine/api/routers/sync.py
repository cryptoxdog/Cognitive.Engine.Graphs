"""
Sync router: POST /v1/sync/{entity_type}
Batch entity synchronization.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path

from engine.config.loader import DomainPackLoader
from engine.graph.driver import GraphDriver
from engine.middleware import resolve_tenant
from engine.sync.generator import SyncGenerator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/sync/{entity_type}")
async def sync_endpoint(
    entity_type: str = Path(..., description="Entity type to sync"),
    batch: list[dict[str, Any]] = ...,
    tenant: str = Depends(resolve_tenant),
    loader: DomainPackLoader = Depends(),
    graph_driver: GraphDriver = Depends(),
) -> dict[str, Any]:
    """
    Batch sync entities.

    Args:
        entity_type: Target entity type (e.g., "loanproduct", "facility")
        batch: List of entity objects
        tenant: Resolved tenant ID
    """
    # Load domain spec
    domain_spec = loader.load_domain(tenant)

    # Find sync endpoint spec
    if not domain_spec.sync:
        raise HTTPException(status_code=404, detail="No sync endpoints configured")

    endpoint_spec = next((e for e in domain_spec.sync.endpoints if entity_type in e.path), None)

    if not endpoint_spec:
        raise HTTPException(status_code=404, detail=f"No sync endpoint for entity type '{entity_type}'")

    # Generate sync query
    generator = SyncGenerator(domain_spec)
    cypher = generator.generate_sync_query(endpoint_spec, batch)

    logger.info(f"Syncing {len(batch)} {entity_type} entities")

    # Execute sync
    result = await graph_driver.execute_query(
        cypher=cypher,
        parameters={"batch": batch},
        database=domain_spec.domain.id,
    )

    return {
        "status": "success",
        "entity_type": entity_type,
        "synced_count": len(batch),
    }
