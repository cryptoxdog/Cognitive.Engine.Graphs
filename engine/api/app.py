"""
FastAPI application factory.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="L9 Graph Cognitive Matching Engine",
        version="1.0.0",
        description="Domain-agnostic graph-native matching with gate-then-score architecture",
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
    # from engine.api.routers import match, sync, admin, outcomes, health
    # app.include_router(match.router, prefix="/v1", tags=["match"])
    # app.include_router(sync.router, prefix="/v1", tags=["sync"])
    # app.include_router(admin.router, prefix="/v1/admin", tags=["admin"])
    # app.include_router(outcomes.router, prefix="/v1", tags=["outcomes"])
    # app.include_router(health.router, prefix="/v1", tags=["health"])

    logger.info("FastAPI app created")

    return app
