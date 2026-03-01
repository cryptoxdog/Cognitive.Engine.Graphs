"""
FastAPI application factory.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from engine.graph.driver import GraphDriver

logger = logging.getLogger(__name__)

# Global driver instance
_graph_driver: GraphDriver | None = None


def get_graph_driver() -> GraphDriver:
    """Get the global graph driver instance."""
    if _graph_driver is None:
        raise RuntimeError("Graph driver not initialized")
    return _graph_driver


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _graph_driver
    
    # Startup: connect to Neo4j
    uri = os.getenv("PLASTICOS_NEO4J_URI", os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    username = os.getenv("PLASTICOS_NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j"))
    password = os.getenv("PLASTICOS_NEO4J_PASSWORD", os.getenv("NEO4J_PASSWORD", "password"))
    
    _graph_driver = GraphDriver(uri=uri, username=username, password=password)
    await _graph_driver.connect()
    logger.info("Graph driver connected on startup")
    
    yield
    
    # Shutdown: close connection
    if _graph_driver:
        await _graph_driver.close()
        logger.info("Graph driver closed on shutdown")


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="L9 Graph Cognitive Matching Engine",
        version="1.0.0",
        description="Domain-agnostic graph-native matching with gate-then-score architecture",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers (import routes)
    from engine.api.routers import match, sync, health, admin

    app.include_router(match.router, prefix="/v1", tags=["match"])
    app.include_router(sync.router, prefix="/v1", tags=["sync"])
    app.include_router(health.router, prefix="/v1", tags=["health"])
    app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])

    logger.info("FastAPI app created")

    return app
