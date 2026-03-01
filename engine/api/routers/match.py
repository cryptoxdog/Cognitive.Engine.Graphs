"""
Match router: POST /v1/match
Universal matching endpoint for all domains.
"""

import logging
from typing import Any

from engine.gates.compiler import GateCompiler
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from engine.config.loader import DomainPackLoader
from engine.graph.driver import GraphDriver
from engine.middleware import resolve_tenant
from engine.scoring.assembler import ScoringAssembler
from engine.traversal.assembler import TraversalAssembler
from engine.traversal.resolver import ParameterResolver

logger = logging.getLogger(__name__)

router = APIRouter()


class MatchRequest(BaseModel):
    """Universal match request schema."""

    query: dict[str, Any]
    match_direction: str
    top_n: int = 10
    weights: dict[str, float] = {}
    filters: dict[str, Any] = {}


class MatchResponse(BaseModel):
    """Match response schema."""

    candidates: list[dict[str, Any]]
    query_id: str
    match_direction: str
    total_candidates: int
    execution_time_ms: float


@router.post("/match", response_model=MatchResponse)
async def match_endpoint(
    request: MatchRequest,
    tenant: str = Depends(resolve_tenant),
    loader: DomainPackLoader = Depends(),
    graph_driver: GraphDriver = Depends(),
) -> MatchResponse:
    """
    Universal matching endpoint.

    Workflow:
    1. Load domain spec
    2. Resolve derived parameters
    3. Compile gates → WHERE clause
    4. Assemble traversal → MATCH clauses
    5. Assemble scoring → WITH clause
    6. Execute query
    7. Return ranked candidates
    """
    import time

    start_time = time.time()

    # Load domain spec
    try:
        domain_spec = loader.load_domain(tenant)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Domain '{tenant}' not found")

    # Resolve derived parameters
    resolver = ParameterResolver(domain_spec)
    resolved_query = resolver.resolve_parameters(request.query)

    # Compile gates
    gate_compiler = GateCompiler(domain_spec)
    where_clause = gate_compiler.compile_all_gates(request.match_direction)

    # Assemble traversal
    traversal_assembler = TraversalAssembler(domain_spec)
    traversal_clauses = traversal_assembler.assemble_traversal(request.match_direction)

    # Assemble scoring
    scoring_assembler = ScoringAssembler(domain_spec)
    scoring_clause = scoring_assembler.assemble_scoring_clause(
        request.match_direction,
        request.weights,
    )

    # Build complete query
    # Get candidate label
    candidate_labels = [
        c.label for c in domain_spec.matchentities.candidate if c.matchdirection == request.match_direction
    ]
    if not candidate_labels:
        raise HTTPException(status_code=400, detail=f"No candidate entity for direction '{request.match_direction}'")

    candidate_label = candidate_labels[0]

    cypher = f"""
    MATCH (candidate:{candidate_label})
    {chr(10).join(traversal_clauses)}
    WHERE {where_clause}
    {scoring_clause}
    RETURN candidate, score
    ORDER BY score DESC
    LIMIT {request.top_n}
    """

    logger.debug(f"Compiled query:\n{cypher}")

    # Execute query
    results = await graph_driver.execute_query(
        cypher=cypher,
        parameters={"query": resolved_query},
        database=domain_spec.domain.id,
    )

    execution_time = (time.time() - start_time) * 1000

    return MatchResponse(
        candidates=results,
        query_id=f"q_{int(time.time())}",
        match_direction=request.match_direction,
        total_candidates=len(results),
        execution_time_ms=execution_time,
    )
