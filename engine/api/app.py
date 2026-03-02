# engine/api/app.py
"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [api]
tags: [api, fastapi, chassis]
owner: engine-team
status: active
--- /L9_META ---

FastAPI application factory for L9 Graph Cognitive Engine.
Wires POST /v1/execute to chassis.execute_action() and GET /v1/health.

This is the ONLY file in engine/ that imports FastAPI (Contract 1 exception).
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chassis.actions import execute_action
from engine.config.loader import DomainPackLoader
from engine.config.settings import settings
from engine.graph.driver import GraphDriver
from engine.handlers import init_dependencies

logger = logging.getLogger(__name__)


class ExecuteRequest(BaseModel):
    """Universal execute request envelope."""

    action: str
    tenant: str
    payload: dict[str, Any] = {}
    trace_id: str | None = None


class ExecuteResponse(BaseModel):
    """Universal execute response envelope."""

    status: str
    action: str
    tenant: str
    data: dict[str, Any]
    meta: dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanup resources."""
    logger.info("Starting L9 Graph Cognitive Engine...")

    # Initialize graph driver
    graph_driver = GraphDriver(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )
    await graph_driver.connect()

    # Initialize domain loader
    domain_loader = DomainPackLoader(config_path=str(settings.domains_root))

    # Inject dependencies into handlers
    init_dependencies(graph_driver, domain_loader)

    logger.info("L9 Graph Cognitive Engine started successfully")
    yield

    # Cleanup
    logger.info("Shutting down L9 Graph Cognitive Engine...")
    await graph_driver.close()
    logger.info("L9 Graph Cognitive Engine shutdown complete")


def create_app() -> FastAPI:
    """Factory function for creating the FastAPI application."""
    application = FastAPI(
        title="L9 Graph Cognitive Engine",
        description="Domain-agnostic graph-native matching engine",
        version="1.1.0",
        lifespan=lifespan,
    )

    @application.post("/v1/execute", response_model=ExecuteResponse)
    async def execute(request: ExecuteRequest) -> ExecuteResponse:
        """
        Universal action endpoint.

        Routes to engine handlers via chassis integration:
        - match: Gate-then-score graph traversal
        - sync: Batch UNWIND MERGE/MATCH SET
        - admin: Introspection, schema init, GDS trigger
        - outcomes: Write transaction outcomes
        - resolve: Entity resolution
        - health: Health check
        - healthcheck: Health check alias
        - enrich: Add computed properties
        """
        trace_id = request.trace_id or f"trace_{uuid.uuid4().hex[:12]}"

        try:
            result = await execute_action(
                action=request.action,
                payload=request.payload,
                tenant=request.tenant,
                trace_id=trace_id,
            )
            return ExecuteResponse(**result)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.exception("Execute failed: %s", e)
            raise HTTPException(status_code=500, detail="Internal server error") from e

    @application.get("/v1/health")
    async def health(request: Request) -> JSONResponse:
        """Health check endpoint."""
        # Use default tenant for health check
        tenant = request.query_params.get("tenant", "default")
        trace_id = f"health_{uuid.uuid4().hex[:8]}"

        try:
            result = await execute_action(
                action="health",
                payload={},
                tenant=tenant,
                trace_id=trace_id,
            )
            status_code = 200 if result.get("data", {}).get("status") == "healthy" else 503
            return JSONResponse(content=result, status_code=status_code)
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return JSONResponse(
                content={"status": "unhealthy", "error": "health_check_failed"},
                status_code=503,
            )

    return application


# Module-level app instance for uvicorn
app = create_app()
