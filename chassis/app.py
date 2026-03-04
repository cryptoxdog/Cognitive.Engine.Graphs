"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: graph
layer: [api]
tags: [api, fastapi, chassis, single-ingress]
owner: platform-team
status: active
--- /L9_META ---

FastAPI application factory for L9 Graph Cognitive Engine.
Single ingress: POST /v1/execute → chassis.actions.execute_action()
Health probe: GET /v1/health (unauthenticated)

Chassis owns HTTP. Engine owns domain logic.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from chassis.actions import execute_action
from engine.config.loader import DomainPackLoader
from engine.config.settings import settings
from engine.graph.driver import GraphDriver
from engine.handlers import init_dependencies

logger = logging.getLogger(__name__)


# --- Chassis-owned envelope models ---


class ExecuteRequest(BaseModel):
    """Universal execute request envelope (chassis contract)."""

    action: str
    tenant: str
    payload: dict[str, Any] = {}
    trace_id: str | None = None


class ExecuteResponse(BaseModel):
    """Universal execute response envelope (chassis contract)."""

    status: str
    action: str
    tenant: str
    data: dict[str, Any]
    meta: dict[str, Any]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and cleanup resources."""
    logger.info("Starting L9 Graph Cognitive Engine...")

    graph_driver = GraphDriver(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )
    await graph_driver.connect()

    domain_loader = DomainPackLoader(config_path=str(settings.domains_root))

    init_dependencies(graph_driver, domain_loader)

    logger.info("L9 Graph Cognitive Engine started successfully")
    yield

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

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["POST", "GET"],
            allow_headers=["*"],
        )

    @application.post("/v1/execute", response_model=ExecuteResponse)
    async def execute(request: ExecuteRequest) -> ExecuteResponse:
        """
        Universal action endpoint — single ingress.
        Routes to engine handlers via chassis action router.
        """
        trace_id = request.trace_id or f"trace_{uuid.uuid4().hex[:12]}"

        try:
            result = await execute_action(
                action=request.action,
                payload=request.payload,
                tenant=request.tenant,
                trace_id=trace_id,
            )
            if result.get("status") == "failed":
                error_detail = result.get("data", {}).get(
                    "error", "Handler execution failed"
                )
                if (
                    "validation" in error_detail.lower()
                    or "invalid" in error_detail.lower()
                ):
                    raise HTTPException(status_code=422, detail=error_detail)
                raise HTTPException(status_code=500, detail=error_detail)
            return ExecuteResponse(**result)
        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.exception("Execute failed: %s", e)
            raise HTTPException(
                status_code=500, detail="Internal server error"
            ) from e

    @application.get("/v1/health")
    async def health(request: Request) -> JSONResponse:
        """Health check endpoint (unauthenticated)."""
        tenant = request.query_params.get("tenant", "default")
        trace_id = f"health_{uuid.uuid4().hex[:8]}"

        try:
            result = await execute_action(
                action="health",
                payload={},
                tenant=tenant,
                trace_id=trace_id,
            )
            status_code = (
                200
                if result.get("data", {}).get("status") == "healthy"
                else 503
            )
            return JSONResponse(content=result, status_code=status_code)
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return JSONResponse(
                content={
                    "status": "unhealthy",
                    "error": "health_check_failed",
                },
                status_code=503,
            )

    return application


# NOTE: Use --factory flag with uvicorn:
#   uvicorn chassis.app:create_app --factory
