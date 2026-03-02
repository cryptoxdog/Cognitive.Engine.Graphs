"""
engine/handlers.py
Action handlers for L9 chassis integration.

The chassis calls these handlers via chassis.router.register_handler().
Handlers receive (tenant: str, payload: dict) and return dict.
No FastAPI, no HTTP, no auth — the chassis owns all that.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from engine.config.loader import DomainPackLoader
from engine.gates.compiler import GateCompiler
from engine.graph.driver import GraphDriver
from engine.scoring.assembler import ScoringAssembler
from engine.sync.generator import SyncGenerator
from engine.traversal.assembler import TraversalAssembler
from engine.traversal.resolver import ParameterResolver
from engine.utils.security import sanitize_label

logger = logging.getLogger(__name__)

# Global dependencies (injected at startup or passed by chassis)
_graph_driver: GraphDriver | None = None
_domain_loader: DomainPackLoader | None = None


def init_dependencies(graph_driver: GraphDriver, domain_loader: DomainPackLoader) -> None:
    """Called by chassis at startup to inject dependencies."""
    global _graph_driver, _domain_loader
    _graph_driver = graph_driver
    _domain_loader = domain_loader


async def handle_match(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Match action: gate-then-score graph traversal.
    
    Payload schema:
      - query: dict[str, Any]  # Query entity attributes
      - match_direction: str   # e.g., "buyer_to_seller"
      - top_n: int = 10
      - weights: dict[str, float] = {}
      - filters: dict[str, Any] = {}
    
    Returns:
      - candidates: list[dict]
      - query_id: str
      - match_direction: str
      - total_candidates: int
      - execution_time_ms: float
    """
    start_time = time.time()
    
    # Extract payload fields
    query = payload["query"]
    match_direction = payload["match_direction"]
    top_n = payload.get("top_n", 10)
    weights = payload.get("weights", {})
    
    # Load domain spec
    domain_spec = _domain_loader.load_domain(tenant)
    
    # Resolve derived parameters
    resolver = ParameterResolver(domain_spec)
    resolved_query = resolver.resolve_parameters(query)
    
    # Compile gates → WHERE clause
    gate_compiler = GateCompiler(domain_spec)
    where_clause = gate_compiler.compile_all_gates(match_direction)
    
    # Assemble traversal → MATCH clauses
    traversal_assembler = TraversalAssembler(domain_spec)
    traversal_clauses = traversal_assembler.assemble_traversal(match_direction)
    
    # Assemble scoring → WITH clause
    scoring_assembler = ScoringAssembler(domain_spec)
    scoring_clause = scoring_assembler.assemble_scoring_clause(match_direction, weights)
    
    # Get candidate label (with sanitization)
    candidate_labels = [
        c.label for c in domain_spec.match_entities.candidate
        if c.match_direction == match_direction
    ]
    if not candidate_labels:
        raise ValueError(f"No candidate entity for direction {match_direction!r}")
    
    candidate_label = sanitize_label(candidate_labels[0])  # SECURITY FIX
    
    # Build Cypher query
    cypher = f"""
    MATCH (candidate:{candidate_label})
    {chr(10).join(traversal_clauses)}
    WHERE {where_clause}
    {scoring_clause}
    RETURN candidate, score
    ORDER BY score DESC
    LIMIT {top_n}
    """
    
    logger.debug(f"Compiled Cypher for tenant={tenant}, direction={match_direction}:\n{cypher}")
    
    # Execute
    results = await _graph_driver.execute_query(
        cypher=cypher,
        parameters={"query": resolved_query},
        database=domain_spec.domain.id,
    )
    
    execution_time_ms = (time.time() - start_time) * 1000
    
    return {
        "candidates": results,
        "query_id": f"q_{int(time.time())}",
        "match_direction": match_direction,
        "total_candidates": len(results),
        "execution_time_ms": execution_time_ms,
    }


async def handle_sync(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Sync action: batch UNWIND MERGE/MATCH SET for graph entities.
    
    Payload schema:
      - entity_type: str
      - batch: list[dict[str, Any]]
    
    Returns:
      - status: str
      - entity_type: str
      - synced_count: int
    """
    entity_type = payload["entity_type"]
    batch = payload["batch"]
    
    # Load domain spec
    domain_spec = _domain_loader.load_domain(tenant)
    
    # Find sync endpoint spec
    if not domain_spec.sync:
        raise ValueError("No sync endpoints configured for this domain")
    
    endpoint_spec = next(
        (e for e in domain_spec.sync.endpoints if entity_type in e.path),
        None
    )
    if not endpoint_spec:
        raise ValueError(f"No sync endpoint for entity type {entity_type!r}")
    
    # Generate sync Cypher
    generator = SyncGenerator(domain_spec)
    cypher = generator.generate_sync_query(endpoint_spec, batch)
    
    logger.info(f"Syncing {len(batch)} {entity_type} entities for tenant={tenant}")
    
    # Execute
    await _graph_driver.execute_query(
        cypher=cypher,
        parameters={"batch": batch},
        database=domain_spec.domain.id,
    )
    
    return {
        "status": "success",
        "entity_type": entity_type,
        "synced_count": len(batch),
    }


async def handle_admin(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Admin action: domain introspection, schema init, GDS trigger.
    
    Payload schema:
      - subaction: str  # "list_domains", "get_domain", "init_schema", "trigger_gds"
      - domain_id: str (for get_domain, init_schema, trigger_gds)
      - job_name: str (for trigger_gds)
    
    Returns:
      - Subaction-specific dict
    """
    subaction = payload["subaction"]
    
    if subaction == "list_domains":
        # Return domains from loader
        domains = _domain_loader.list_domains()
        return {"domains": domains}
    
    elif subaction == "get_domain":
        domain_id = payload["domain_id"]
        spec = _domain_loader.load_domain(domain_id)
        return {"domain": spec.model_dump()}
    
    elif subaction == "init_schema":
        # Schema initialization logic (from admin.py init_schema)
        # DEFER: Move DDL sanitization + constraint creation here
        raise NotImplementedError("init_schema moved to admin action")
    
    elif subaction == "trigger_gds":
        # Manual GDS job trigger
        raise NotImplementedError("trigger_gds moved to admin action")
    
    else:
        raise ValueError(f"Unknown admin subaction: {subaction!r}")


def register_all(chassis_router) -> None:
    """
    Register all action handlers with the chassis.
    
    Called by chassis at startup:
      from engine.handlers import register_all
      register_all(chassis.router)
    """
    chassis_router.register_handler("match", handle_match)
    chassis_router.register_handler("sync", handle_sync)
    chassis_router.register_handler("admin", handle_admin)
    logger.info("Registered 3 action handlers: match, sync, admin")
