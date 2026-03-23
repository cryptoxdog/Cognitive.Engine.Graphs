"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [engine, boot, lifecycle]
owner: engine-team
status: active
--- /L9_META ---

engine/boot.py — Graph Cognitive Engine LifecycleHook

Concrete implementation of chassis.chassis_app.LifecycleHook for the
Graph Cognitive Engine.  This is the ONLY file that couples
engine internals to the chassis contract.

    L9_LIFECYCLE_HOOK=engine.boot:GraphLifecycle

NOTE: chassis/engine_boot.py was removed (was a stale duplicate of this file).
"""

from __future__ import annotations

import logging
from typing import Any

from chassis.chassis_app import LifecycleHook
from engine.config.loader import DomainPackLoader
from engine.config.settings import settings
from engine.graph.driver import GraphDriver
from engine.handlers import init_dependencies

logger = logging.getLogger(__name__)

_WEIGHT_CEILING = 1.0
_WEIGHT_SUM_TOLERANCE = 1e-9


def _assert_default_weight_sum() -> None:
    """W1-02: Assert default scoring weights sum to <= 1.0 at startup.

    Prevents misconfiguration from silently producing unbounded scores.
    """
    weight_sum = settings.w_structural + settings.w_geo + settings.w_reinforcement + settings.w_freshness
    if weight_sum > _WEIGHT_CEILING + _WEIGHT_SUM_TOLERANCE:
        msg = (
            f"Default scoring weights sum to {weight_sum:.4f} "
            f"(W_STRUCTURAL={settings.w_structural} + W_GEO={settings.w_geo} + "
            f"W_REINFORCEMENT={settings.w_reinforcement} + W_FRESHNESS={settings.w_freshness}), "
            f"exceeding {_WEIGHT_CEILING}"
        )
        raise ValueError(msg)
    logger.info("W1-02: Default weight sum validated: %.4f <= %.1f", weight_sum, _WEIGHT_CEILING)


class GraphLifecycle(LifecycleHook):
    """
    Wires Neo4j, domain packs, handler dependencies, and GDS scheduler
    lifecycle for the L9 Graph Cognitive Engine.
    """

    def __init__(self) -> None:
        self._graph_driver: GraphDriver | None = None
        self._domain_loader: DomainPackLoader | None = None
        self._schedulers: list[Any] = []

    # --- lifecycle ----------------------------------------------------------

    async def startup(self) -> None:
        from engine.gds.scheduler import GDSScheduler

        logger.info("GraphLifecycle.startup → connecting Neo4j")

        # W1-02: Startup weight-sum assertion
        if settings.score_clamp_enabled:
            _assert_default_weight_sum()

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

        # Start GDS schedulers for all loaded domains (if GDS enabled)
        if settings.gds_enabled:
            for domain_id in self._domain_loader.list_domains():
                try:
                    spec = self._domain_loader.load_domain(domain_id)
                    if spec.gdsjobs:
                        scheduler = GDSScheduler(spec, self._graph_driver)
                        scheduler.register_jobs()
                        scheduler.start()
                        self._schedulers.append(scheduler)
                        logger.info(
                            "GDS scheduler started for domain=%s (%d jobs)",
                            domain_id,
                            len(spec.gdsjobs),
                        )
                except Exception as exc:
                    logger.warning(
                        "Failed to start GDS scheduler for domain=%s: %s",
                        domain_id,
                        exc,
                    )
        else:
            logger.info("GDS disabled via settings.gds_enabled=False — skipping scheduler startup")

        logger.info("GraphLifecycle.startup complete")

    async def shutdown(self) -> None:
        logger.info("GraphLifecycle.shutdown → stopping schedulers and closing Neo4j pool")
        # Shut down all GDS schedulers
        from engine.handlers import _gds_schedulers

        for domain_id, scheduler in _gds_schedulers.items():
            try:
                logger.info("Shutting down GDS scheduler for domain: %s", domain_id)
                scheduler.shutdown()
            except Exception as exc:
                logger.warning("Scheduler shutdown error for %s: %s", domain_id, exc)
        _gds_schedulers.clear()
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
