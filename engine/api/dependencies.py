"""
engine/api/dependencies.py

FastAPI dependency injection. Provides shared resources to route handlers.
All dependencies are async-compatible and respect the application lifespan.
"""

import logging
from functools import lru_cache

from engine.config.loader import DomainPackLoader
from engine.config.settings import settings
from engine.graph.driver import GraphDriver

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singletons — created once, reused across requests
# ---------------------------------------------------------------------------

_graph_driver: GraphDriver | None = None
_domain_loader: DomainPackLoader | None = None


async def startup() -> None:
    """Initialize shared resources. Called from app lifespan."""
    global _graph_driver, _domain_loader

    # Neo4j
    _graph_driver = GraphDriver(
        uri=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
    )
    await _graph_driver.connect()
    logger.info("GraphDriver connected")

    # Domain loader
    _domain_loader = DomainPackLoader(domains_root=settings.domains_root)
    domains = _domain_loader.list_domains()
    logger.info(f"DomainPackLoader initialized — {len(domains)} domains: {domains}")


async def shutdown() -> None:
    """Clean up shared resources. Called from app lifespan."""
    global _graph_driver
    if _graph_driver:
        await _graph_driver.close()
        _graph_driver = None
        logger.info("GraphDriver closed")


# ---------------------------------------------------------------------------
# FastAPI Dependencies — inject via Depends()
# ---------------------------------------------------------------------------


def get_graph_driver() -> GraphDriver:
    """Get the shared Neo4j driver instance."""
    if _graph_driver is None:
        raise RuntimeError("GraphDriver not initialized. App startup incomplete.")
    return _graph_driver


def get_domain_loader() -> DomainPackLoader:
    """Get the shared domain pack loader."""
    if _domain_loader is None:
        raise RuntimeError("DomainPackLoader not initialized. App startup incomplete.")
    return _domain_loader


@lru_cache
def get_settings():
    """Get application settings (cached)."""
    return settings


# ---------------------------------------------------------------------------
# Redis (lazy init — only when needed)
# ---------------------------------------------------------------------------

_redis_client = None


async def get_redis():
    """Get Redis client. Lazy-initialized on first call."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis

            _redis_client = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis_client.ping()
            logger.info(f"Redis connected: {settings.redis_url}")
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}. Caching disabled.")
            return None
    return _redis_client
