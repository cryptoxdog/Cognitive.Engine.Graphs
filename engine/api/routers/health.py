"""
Health check router.
"""

from fastapi import APIRouter, Depends

from engine.graph.driver import GraphDriver

router = APIRouter()


@router.get("/health")
async def health_check(graph_driver: GraphDriver = Depends()) -> dict:
    """Health check endpoint."""
    try:
        # Verify Neo4j connectivity
        await graph_driver.execute_query("RETURN 1 AS health")
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
