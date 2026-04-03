"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [state, lifecycle, sel4]
owner: engine-team
status: active
--- /L9_META ---

engine/state.py — Explicit Engine State Management (seL4 W4-01)

Single, explicit container for all CEG engine shared mutable state.
Replaces module-level globals in engine/handlers.py with a well-defined
EngineState class accessible via get_state().

seL4 Analogue: seL4 requires that all kernel mutable state is fully
explicit — no hidden globals, no partially-initialised singletons.
EngineState is the CEG equivalent.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from engine.compliance.engine import ComplianceEngine
    from engine.config.loader import DomainPackLoader
    from engine.gds.scheduler import GDSScheduler
    from engine.graph.driver import GraphDriver

logger = logging.getLogger(__name__)


class EngineState:
    """Explicit, async-safe container for all CEG engine shared mutable state.

    All public attributes are accessed via properties that raise RuntimeError
    if the state has not been initialized. Mutation only through dedicated
    lifecycle methods (initialize, shutdown, reset).
    """

    def __init__(self) -> None:
        self._lock: asyncio.Lock = asyncio.Lock()
        self._initialized: bool = False
        self._initialize_time: float = 0.0
        self._shutdown_time: float = 0.0

        # Core dependencies (None until initialized)
        self._graph_driver: GraphDriver | None = None
        self._domain_loader: DomainPackLoader | None = None
        self._gds_schedulers: dict[str, GDSScheduler] = {}
        self._compliance_engines: dict[str, ComplianceEngine] = {}
        self._tenant_allowlist: set[str] | None = None  # None = all tenants allowed

    # ------------------------------------------------------------------
    # Properties (read-only after initialization)
    # ------------------------------------------------------------------

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def graph_driver(self) -> GraphDriver:
        if self._graph_driver is None:
            msg = "EngineState.graph_driver accessed before initialize(). Call await state.initialize() first."
            raise RuntimeError(msg)
        return self._graph_driver

    @property
    def domain_loader(self) -> DomainPackLoader:
        if self._domain_loader is None:
            msg = "EngineState.domain_loader accessed before initialize(). Call await state.initialize() first."
            raise RuntimeError(msg)
        return self._domain_loader

    @property
    def gds_schedulers(self) -> dict[str, Any]:
        return self._gds_schedulers

    @property
    def compliance_engines(self) -> dict[str, ComplianceEngine]:
        return self._compliance_engines

    @property
    def tenant_allowlist(self) -> set[str] | None:
        return self._tenant_allowlist

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(
        self,
        graph_driver: GraphDriver,
        domain_loader: DomainPackLoader,
        tenant_allowlist: set[str] | None = None,
    ) -> None:
        """Initialize the engine state. Idempotent — second call logs warning and returns."""
        async with self._lock:
            if self._initialized:
                logger.warning("EngineState.initialize() called on already-initialized state")
                return

            self._graph_driver = graph_driver
            self._domain_loader = domain_loader
            self._gds_schedulers = {}
            self._compliance_engines = {}

            # Resolve tenant allowlist from parameter or environment
            if tenant_allowlist is not None:
                self._tenant_allowlist = tenant_allowlist
            else:
                allowlist_raw = os.getenv("TENANT_ALLOWLIST", "")
                if allowlist_raw.strip():
                    self._tenant_allowlist = {t.strip() for t in allowlist_raw.split(",") if t.strip()}
                    logger.info("Tenant allowlist configured: %s", self._tenant_allowlist)
                else:
                    self._tenant_allowlist = None
                    logger.warning("No TENANT_ALLOWLIST configured — all tenants accessible")

            self._initialize_time = time.time()
            self._initialized = True
            logger.info("EngineState initialized at %.3f", self._initialize_time)

    async def shutdown(self) -> None:
        """Gracefully shut down: stop schedulers, close driver, clear state."""
        async with self._lock:
            if not self._initialized:
                return

            logger.info("Shutting down EngineState...")

            # Stop GDS schedulers
            for domain_id, scheduler in self._gds_schedulers.items():
                try:
                    scheduler.shutdown()
                    logger.info("GDS scheduler stopped for domain=%s", domain_id)
                except Exception as exc:
                    logger.warning("Scheduler shutdown error for %s: %s", domain_id, exc)
            self._gds_schedulers.clear()

            # Clear compliance engines
            self._compliance_engines.clear()

            # Close graph driver
            if self._graph_driver is not None:
                try:
                    await self._graph_driver.close()
                except Exception as exc:
                    logger.warning("Error closing graph driver: %s", exc)

            self._graph_driver = None
            self._domain_loader = None
            self._tenant_allowlist = None
            self._shutdown_time = time.time()
            self._initialized = False
            logger.info("EngineState shut down at %.3f", self._shutdown_time)

    def reset(self) -> None:
        """Synchronous reset for test isolation. Does NOT close driver."""
        self._initialized = False
        self._initialize_time = 0.0
        self._graph_driver = None
        self._domain_loader = None
        self._gds_schedulers = {}
        self._compliance_engines = {}
        self._tenant_allowlist = None
        self._lock = asyncio.Lock()

    def health_check(self) -> dict[str, Any]:
        """Return a health snapshot for monitoring."""
        return {
            "initialized": self._initialized,
            "initialize_time": self._initialize_time,
            "shutdown_time": self._shutdown_time,
            "graph_driver_present": self._graph_driver is not None,
            "domain_loader_present": self._domain_loader is not None,
            "tenant_count": len(self._tenant_allowlist) if self._tenant_allowlist else 0,
            "gds_scheduler_count": len(self._gds_schedulers),
            "compliance_engine_count": len(self._compliance_engines),
        }


# ---------------------------------------------------------------------------
# Process-singleton accessor
# ---------------------------------------------------------------------------

_ENGINE_STATE: EngineState | None = None


def get_state() -> EngineState:
    """Return the process-singleton EngineState instance (lazy-created)."""
    global _ENGINE_STATE
    if _ENGINE_STATE is None:
        _ENGINE_STATE = EngineState()
    return _ENGINE_STATE


def _reset_singleton() -> None:
    """Reset the process-singleton for test isolation. Do NOT call in production."""
    global _ENGINE_STATE
    if _ENGINE_STATE is not None:
        _ENGINE_STATE.reset()
    _ENGINE_STATE = None
