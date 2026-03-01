"""
Health check router.
"""

from fastapi import APIRouter

from engine.api.app import get_graph_driver

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    try:
        driver = get_graph_driver()
        await driver.execute_query("RETURN 1 AS health")
        return {
            "status": "healthy",
            "database": "connected",
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
        }
