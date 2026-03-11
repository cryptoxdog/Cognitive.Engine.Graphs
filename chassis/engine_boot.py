"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [boot]
tags: [lifecycle, boot, graph-engine]
owner: engine-team
status: active
--- /L9_META ---

engine/boot.py — Graph Cognitive Engine LifecycleHook

Concrete implementation of chassis.app.LifecycleHook for the
Graph Cognitive Engine.  This is the ONLY file that couples
engine internals to the chassis contract.

    L9_LIFECYCLE_HOOK=engine.boot:GraphLifecycle
"""

from __future__ import annotations

import logging
from typing import Any

from chassis.app import LifecycleHook

from engine.config.loader import DomainPackLoader
from engine.config.settings import settings
from engine.graph.driver import GraphDriver
from engine.handlers import init_dependencies

logger = logging.getLogger(__name__)


class GraphLifecycle(LifecycleHook):
    """
    Wires Neo4j, domain packs, and handler dependencies for the
    L9 Graph Cognitive Engine.
    """

    def __init__(self) -> None:
        self._graph_driver: GraphDriver | None = None
        self._domain_loader: DomainPackLoader | None = None

    # --- lifecycle ----------------------------------------------------------

    async def startup(self) -> None:
        logger.info("GraphLifecycle.startup → connecting Neo4j")

        self._graph_driver = GraphDriver(
            uri=settings.neo4j_uri,
            username=settings.neo4j_username,
            password=settings.neo4j_password,
        )
        await self._graph_driver.connect()

        self._domain_loader = DomainPackLoader(
            config_path=str(settings.domains_root),
        )

        init_dependencies(self._graph_driver, self._domain_loader)
        logger.info("GraphLifecycle.startup complete")

    async def shutdown(self) -> None:
        logger.info("GraphLifecycle.shutdown → closing Neo4j pool")
        if self._graph_driver:
            await self._graph_driver.close()
        logger.info("GraphLifecycle.shutdown complete")

    # --- action routing -----------------------------------------------------

    async def execute(
        self,
        action: str,
        payload: dict[str, Any],
        tenant: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Delegate to chassis.actions.execute_action (PacketEnvelope bridge)."""
        from chassis.actions import execute_action

        return await execute_action(
            action=action,
            payload=payload,
            tenant=tenant,
            trace_id=trace_id,
        )
