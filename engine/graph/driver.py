"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [graph, driver, neo4j]
owner: engine-team
status: active
--- /L9_META ---

Neo4j driver wrapper.
Manages connection pooling and multi-database routing.
"""

import logging
import os

from neo4j import AsyncDriver, AsyncGraphDatabase

logger = logging.getLogger(__name__)


class GraphDriver:
    """Neo4j async driver manager."""

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        """
        Initialize driver.

        Args:
            uri: Neo4j URI (defaults to NEO4J_URI env var)
            username: Neo4j username (defaults to NEO4J_USERNAME env var)
            password: Neo4j password (defaults to NEO4J_PASSWORD env var)
        """
        self.uri: str = uri or os.getenv("NEO4J_URI") or "bolt://localhost:7687"
        self.username: str = username or os.getenv("NEO4J_USERNAME") or "neo4j"
        self.password: str = password or os.getenv("NEO4J_PASSWORD") or "password"

        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish driver connection."""
        if self._driver:
            logger.warning("Driver already connected")
            return

        logger.info(f"Connecting to Neo4j at {self.uri}")
        self._driver = AsyncGraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
        )

        # Verify connectivity
        await self._driver.verify_connectivity()
        logger.info("Neo4j driver connected successfully")

    async def close(self) -> None:
        """Close driver connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None
            logger.info("Neo4j driver closed")

    def get_driver(self) -> AsyncDriver:
        """Get driver instance."""
        if not self._driver:
            raise RuntimeError("Driver not connected. Call connect() first.")
        return self._driver

    async def execute_query(
        self,
        cypher: str,
        parameters: dict | None = None,
        database: str = "neo4j",
    ) -> list:
        """
        Execute Cypher query.

        Args:
            cypher: Cypher query
            parameters: Query parameters
            database: Target database name

        Returns:
            List of record dictionaries
        """
        driver = self.get_driver()

        async with driver.session(database=database) as session:
            result = await session.run(cypher, parameters or {})
            records = await result.data()
            return records
