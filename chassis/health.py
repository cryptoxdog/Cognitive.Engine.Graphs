"""
--- L9_META ---
l9_schema: 1
origin: chassis
engine: "*"
layer: [api]
tags: [chassis, health, readiness, liveness, engine-agnostic]
owner: platform-team
status: active
--- /L9_META ---

chassis/health.py — Universal Health Check Aggregator

Engines register named health probes at startup.
The chassis runs them all and aggregates to a single status.

    healthy  → all probes pass  → HTTP 200
    degraded → some probes fail → HTTP 503
    unhealthy→ all probes fail  → HTTP 503

Supports:
    - Kubernetes liveness (GET /v1/health)
    - Kubernetes readiness (GET /v1/ready)
    - Individual probe status for dashboards
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

ProbeFunc = Callable[[], Awaitable[bool]]


@dataclass(frozen=True)
class ProbeResult:
    name: str
    healthy: bool
    latency_ms: float
    detail: str = ""


@dataclass
class HealthAggregator:
    """
    Collects named health probes and runs them in parallel.

    Usage:
        health = HealthAggregator()
        health.register("neo4j", check_neo4j)
        health.register("redis", check_redis)
        health.register("domain_loader", check_domains)

        result = await health.check_all()
        # → {"status": "healthy", "checks": {...}, "latency_ms": 42.1}
    """

    _probes: dict[str, ProbeFunc] = field(default_factory=dict)
    timeout_seconds: float = 5.0

    def register(self, name: str, probe: ProbeFunc) -> None:
        """Register a named health probe."""
        self._probes[name] = probe
        logger.debug("Health probe registered: %s", name)

    def deregister(self, name: str) -> None:
        """Remove a probe (for testing / dynamic reconfiguration)."""
        self._probes.pop(name, None)

    async def check_all(self) -> dict[str, Any]:
        """
        Run all probes concurrently with timeout.
        Returns aggregated health status.
        """
        if not self._probes:
            return {
                "status": "healthy",
                "checks": {},
                "latency_ms": 0.0,
                "probe_count": 0,
            }

        start = time.perf_counter()
        results = await asyncio.gather(
            *(self._run_probe(name, fn) for name, fn in self._probes.items()),
            return_exceptions=False,
        )
        total_ms = (time.perf_counter() - start) * 1000

        checks = {r.name: {"healthy": r.healthy, "latency_ms": r.latency_ms, "detail": r.detail} for r in results}
        all_healthy = all(r.healthy for r in results)
        any_healthy = any(r.healthy for r in results)

        if all_healthy:
            status = "healthy"
        elif any_healthy:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "checks": checks,
            "latency_ms": round(total_ms, 2),
            "probe_count": len(results),
        }

    async def check_one(self, name: str) -> ProbeResult:
        """Run a single named probe."""
        fn = self._probes.get(name)
        if fn is None:
            return ProbeResult(name=name, healthy=False, latency_ms=0, detail="probe not registered")
        return await self._run_probe(name, fn)

    async def _run_probe(self, name: str, fn: ProbeFunc) -> ProbeResult:
        start = time.perf_counter()
        try:
            healthy = await asyncio.wait_for(fn(), timeout=self.timeout_seconds)
            latency = (time.perf_counter() - start) * 1000
            return ProbeResult(name=name, healthy=bool(healthy), latency_ms=round(latency, 2))
        except asyncio.TimeoutError:
            latency = (time.perf_counter() - start) * 1000
            logger.warning("Health probe %s timed out after %.0fms", name, latency)
            return ProbeResult(name=name, healthy=False, latency_ms=round(latency, 2), detail="timeout")
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            logger.warning("Health probe %s failed: %s", name, exc)
            return ProbeResult(name=name, healthy=False, latency_ms=round(latency, 2), detail=str(exc))

    @property
    def probe_names(self) -> list[str]:
        return sorted(self._probes.keys())
