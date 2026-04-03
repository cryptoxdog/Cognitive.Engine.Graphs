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

import asyncio
import logging
from typing import Any

from chassis.chassis_app import LifecycleHook
from engine.config.loader import DomainPackLoader
from engine.config.settings import settings
from engine.graph.driver import GraphDriver
from engine.handlers import init_dependencies
from engine.state import get_state

logger = logging.getLogger(__name__)

_WEIGHT_CEILING = 1.0
_WEIGHT_SUM_TOLERANCE = 1e-9


def _assert_default_weight_sum() -> None:
    """W1-02: Assert default scoring weights sum to <= 1.0 at startup.

    Prevents misconfiguration from silently producing unbounded scores.
    """
    weight_sum = (
        settings.w_structural
        + settings.w_geo
        + settings.w_reinforcement
        + settings.w_freshness
    )
    if weight_sum > _WEIGHT_CEILING + _WEIGHT_SUM_TOLERANCE:
        msg = (
            f"Default scoring weights sum to {weight_sum:.4f} "
            f"(W_STRUCTURAL={settings.w_structural} + W_GEO={settings.w_geo} + "
            f"W_REINFORCEMENT={settings.w_reinforcement} + W_FRESHNESS={settings.w_freshness}), "
            f"exceeding {_WEIGHT_CEILING}"
        )
        raise ValueError(msg)
    logger.info(
        "W1-02: Default weight sum validated: %.4f <= %.1f",
        weight_sum,
        _WEIGHT_CEILING,
    )


class GraphLifecycle(LifecycleHook):
    """
    Wires Neo4j, domain packs, handler dependencies, gap fixes,
    convergence-controller patch, and GDS scheduler lifecycle for the
    L9 Graph Cognitive Engine.
    """

    def __init__(self) -> None:
        self._graph_driver: GraphDriver | None = None
        self._domain_loader: DomainPackLoader | None = None
        self._schedulers: list[Any] = []
        self._compliance_flush_task: asyncio.Task[None] | None = None

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
        try:
            await self._graph_driver.connect()
            logger.info("GraphLifecycle.startup → Neo4j connected")
        except Exception as exc:
            # Neo4j unreachable at startup — container comes up anyway.
            # Health endpoint will report neo4j=error:connection_failed.
            # The driver retries on first query; no need to crash here.
            logger.warning("GraphLifecycle.startup → Neo4j unavailable: %s", exc)

        self._domain_loader = DomainPackLoader(
            config_path=str(settings.domains_root),
        )

        init_dependencies(self._graph_driver, self._domain_loader)

        # ── FIX(RULE-9 + GAP-2/3/5/6): Apply all gap fixes before serving requests ──
        # startup_wiring.apply_all_gap_fixes wires:
        #   Gap-5: PostgreSQL audit pool → compliance flush is now persistent
        #   Gap-3: Domain KB inference rules → loaded into InferenceRuleRegistry
        #   Gap-2: GraphToEnrichReturnChannel singleton → initialised before first packet
        #   Gap-6: Community export hook → registered on GDSScheduler post-louvain
        # Fail-closed: if pg_dsn is absent or pool creation fails, startup raises.
        await _apply_gap_fixes(self._graph_driver, self._domain_loader)

        # ── FIX(RULE-9 + GAP-4/7/8): Activate convergence_controller_patch ──
        # extract_per_field_confidence, apply_return_channel_targets, and
        # enforce_domain_spec are utility functions — they require no module-level
        # registration; they are called by convergence_controller directly.
        # We validate the patch is importable here so a broken import surfaces at
        # boot rather than at first convergence pass.
        _assert_convergence_patch_importable()

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
            logger.info(
                "GDS disabled via settings.gds_enabled=False — skipping scheduler startup"
            )

        # W4-04: Start periodic compliance audit flush task
        self._compliance_flush_task = asyncio.create_task(self._compliance_flush_loop())
        logger.info(
            "W4-04: Compliance flush task started (interval=%ds, buffer_max=%d)",
            settings.compliance_flush_interval,
            settings.compliance_buffer_max,
        )

        # W6-03: Register GDS health probe
        if settings.gds_enabled and self._schedulers:
            self._register_gds_health_probe()

        logger.info("GraphLifecycle.startup complete")

    def _register_gds_health_probe(self) -> None:
        """W6-03: Register a health probe that checks GDS algorithm staleness."""

        async def gds_health_check() -> dict[str, Any]:
            from datetime import UTC, datetime, timedelta

            max_staleness = timedelta(hours=settings.gds_max_staleness_hours)
            now = datetime.now(tz=UTC)
            stale_jobs: list[str] = []
            for scheduler in self._schedulers:
                history = await scheduler.get_job_history()
                seen: set[str] = set()
                for entry in reversed(history):
                    algo = entry.get("algorithm") or entry.get("job", "unknown")
                    if algo in seen:
                        continue
                    seen.add(algo)
                    ts_str = entry.get("timestamp")
                    if ts_str:
                        try:
                            ts = datetime.fromisoformat(ts_str)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=UTC)
                            if (now - ts) > max_staleness:
                                stale_jobs.append(algo)
                        except (ValueError, TypeError):
                            stale_jobs.append(algo)
                    else:
                        stale_jobs.append(algo)
            if stale_jobs:
                return {"gds": f"degraded: stale jobs: {', '.join(stale_jobs)}"}
            return {"gds": "ok"}

        self._gds_health_check = gds_health_check
        logger.info("W6-03: GDS health probe registered")

    async def shutdown(self) -> None:
        logger.info(
            "GraphLifecycle.shutdown → stopping schedulers and closing Neo4j pool"
        )

        # W4-04: Cancel compliance flush task
        if self._compliance_flush_task is not None:
            self._compliance_flush_task.cancel()
            try:
                await self._compliance_flush_task
            except asyncio.CancelledError:
                pass
            self._compliance_flush_task = None
            logger.info("W4-04: Compliance flush task stopped")

        # Final flush of all compliance engines before shutdown
        state = get_state()
        for domain_id, ce in state.compliance_engines.items():
            try:
                await ce.flush_audit()
            except Exception as exc:
                logger.warning(
                    "Final compliance flush failed for %s: %s", domain_id, exc
                )

        await state.shutdown()
        logger.info("GraphLifecycle.shutdown complete")

    # --- W4-04: compliance flush loop ----------------------------------------

    async def _compliance_flush_loop(self) -> None:
        """Periodically flush audit entries from all compliance engine singletons."""
        interval = settings.compliance_flush_interval
        while True:
            try:
                await asyncio.sleep(interval)
                state = get_state()
                for domain_id, ce in list(state.compliance_engines.items()):
                    try:
                        await ce.flush_audit()
                    except Exception as exc:
                        logger.warning(
                            "Compliance flush failed for domain=%s: %s", domain_id, exc
                        )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Compliance flush loop error: %s", exc)

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


# ---------------------------------------------------------------------------
# Private startup helpers (not part of LifecycleHook contract)
# ---------------------------------------------------------------------------


async def _apply_gap_fixes(
    graph_driver: GraphDriver,
    domain_loader: DomainPackLoader,
) -> None:
    """FIX(RULE-9 + GAP-2/3/5/6): Wire all merged-but-inactive gap fixes.

    This is the ONLY call site for apply_all_gap_fixes. The function is
    idempotent: safe to call once per process lifetime.

    Fail-closed: raises on missing L9_POSTGRES_DSN or pool creation failure.
    The engine MUST NOT serve requests with an uninitialized audit pool.
    """
    if not settings.l9_postgres_dsn:
        msg = (
            "L9_POSTGRES_DSN is not set. Gap-5 (audit pool) cannot be wired. "
            "Set L9_POSTGRES_DSN in .env or environment before starting the engine."
        )
        raise RuntimeError(msg)

    from engine.startup_wiring import apply_all_gap_fixes

    await apply_all_gap_fixes(
        pg_dsn=settings.l9_postgres_dsn,
        neo4j_driver=graph_driver,
        domain_pack_loader=domain_loader,
    )
    logger.info("startup: all gap fixes applied (Gaps 2, 3, 5, 6)")


def _assert_convergence_patch_importable() -> None:
    """FIX(RULE-2 + GAP-4/7/8): Verify convergence_controller_patch imports cleanly at boot.

    The patch functions are called by convergence_controller at runtime.
    A broken import would silently surface at first convergence pass —
    validating here makes it a boot-time failure instead.
    """
    try:
        from engine.convergence_controller_patch import (  # noqa: F401
            DomainSpecRequiredError,
            apply_return_channel_targets,
            emit_schema_proposal,
            enforce_domain_spec,
            extract_per_field_confidence,
        )
    except ImportError as exc:
        msg = f"convergence_controller_patch failed to import: {exc}. Cannot start."
        raise RuntimeError(msg) from exc
    logger.info("startup: convergence_controller_patch verified importable (Gaps 4, 7, 8)")
