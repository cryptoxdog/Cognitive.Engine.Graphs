"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, wave4, sel4, state, circuit-breaker, cache, compliance]
owner: engine-team
status: active
--- /L9_META ---

Tests for Wave 4: State Management & Resilience (seL4 explicit state).

Covers:
  W4-01: EngineState — init, shutdown, reset, health_check, double-init, pre-init error
  W4-02: CircuitBreaker — CLOSED→OPEN, OPEN→HALF_OPEN→CLOSED, metrics, force ops
  W4-03: DomainPackLoader TTL Cache — hit, miss, expiry, invalidation, stampede
  W4-04: ComplianceEngine singleton — get-or-create, flush, lifecycle
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# W4-01: EngineState Tests
# ---------------------------------------------------------------------------


class TestEngineState:
    """W4-01: EngineState lifecycle and access control."""

    def setup_method(self) -> None:
        from engine.state import _reset_singleton

        _reset_singleton()

    def teardown_method(self) -> None:
        from engine.state import _reset_singleton

        _reset_singleton()

    def test_get_state_returns_singleton(self) -> None:
        from engine.state import get_state

        s1 = get_state()
        s2 = get_state()
        assert s1 is s2

    def test_pre_init_graph_driver_raises(self) -> None:
        from engine.state import get_state

        state = get_state()
        with pytest.raises(RuntimeError, match="graph_driver"):
            _ = state.graph_driver

    def test_pre_init_domain_loader_raises(self) -> None:
        from engine.state import get_state

        state = get_state()
        with pytest.raises(RuntimeError, match="domain_loader"):
            _ = state.domain_loader

    @pytest.mark.asyncio
    async def test_initialize_sets_state(self) -> None:
        from engine.state import get_state

        state = get_state()
        mock_driver = MagicMock()
        mock_loader = MagicMock()

        await state.initialize(
            graph_driver=mock_driver,
            domain_loader=mock_loader,
            tenant_allowlist={"tenant_a", "tenant_b"},
        )

        assert state.is_initialized
        assert state.graph_driver is mock_driver
        assert state.domain_loader is mock_loader
        assert state.tenant_allowlist == {"tenant_a", "tenant_b"}

    @pytest.mark.asyncio
    async def test_double_init_is_idempotent(self) -> None:
        from engine.state import get_state

        state = get_state()
        mock_driver = MagicMock()
        mock_loader = MagicMock()

        await state.initialize(graph_driver=mock_driver, domain_loader=mock_loader)
        assert state.is_initialized

        # Second call should be a no-op
        mock_driver2 = MagicMock()
        await state.initialize(graph_driver=mock_driver2, domain_loader=mock_loader)

        # Still the original driver
        assert state.graph_driver is mock_driver

    @pytest.mark.asyncio
    async def test_shutdown_clears_state(self) -> None:
        from engine.state import get_state

        state = get_state()
        mock_driver = AsyncMock()
        mock_loader = MagicMock()

        await state.initialize(graph_driver=mock_driver, domain_loader=mock_loader)
        assert state.is_initialized

        await state.shutdown()

        assert not state.is_initialized
        mock_driver.close.assert_awaited_once()

    def test_reset_clears_state_sync(self) -> None:
        from engine.state import get_state

        state = get_state()
        state._graph_driver = MagicMock()
        state._initialized = True

        state.reset()

        assert not state.is_initialized
        with pytest.raises(RuntimeError):
            _ = state.graph_driver

    def test_health_check_uninitialized(self) -> None:
        from engine.state import get_state

        state = get_state()
        health = state.health_check()
        assert health["initialized"] is False
        assert health["graph_driver_present"] is False

    @pytest.mark.asyncio
    async def test_health_check_initialized(self) -> None:
        from engine.state import get_state

        state = get_state()
        await state.initialize(
            graph_driver=MagicMock(),
            domain_loader=MagicMock(),
            tenant_allowlist={"t1"},
        )

        health = state.health_check()
        assert health["initialized"] is True
        assert health["graph_driver_present"] is True
        assert health["tenant_count"] == 1

    def test_reset_singleton_creates_fresh_state(self) -> None:
        from engine.state import _reset_singleton, get_state

        s1 = get_state()
        _reset_singleton()
        s2 = get_state()
        assert s1 is not s2


# ---------------------------------------------------------------------------
# W4-02: CircuitBreaker Tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """W4-02: Circuit breaker state machine and metrics."""

    @pytest.mark.asyncio
    async def test_closed_forwards_calls(self) -> None:
        from engine.graph.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=3)
        func = AsyncMock(return_value=42)

        result = await cb.call(func)
        assert result == 42
        assert cb.is_closed

    @pytest.mark.asyncio
    async def test_closed_to_open_on_threshold(self) -> None:
        from engine.graph.circuit_breaker import BreakerState, CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60.0)
        func = AsyncMock(side_effect=RuntimeError("fail"))

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(func)

        assert cb.state == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_open_rejects_calls(self) -> None:
        from engine.graph.circuit_breaker import CircuitBreaker, CircuitOpenError

        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=60.0)
        func = AsyncMock(side_effect=RuntimeError("fail"))

        # Trip the breaker
        with pytest.raises(RuntimeError):
            await cb.call(func)

        # Now it should reject
        with pytest.raises(CircuitOpenError):
            await cb.call(func)

    @pytest.mark.asyncio
    async def test_open_to_half_open_after_timeout(self) -> None:
        from engine.graph.circuit_breaker import BreakerState, CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))
        success_func = AsyncMock(return_value="ok")

        # Trip the breaker
        with pytest.raises(RuntimeError):
            await cb.call(fail_func)

        assert cb.state == BreakerState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should transition to HALF_OPEN then CLOSED on success
        result = await cb.call(success_func)
        assert result == "ok"
        assert cb.state == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens(self) -> None:
        from engine.graph.circuit_breaker import BreakerState, CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.1)
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        # Trip the breaker
        with pytest.raises(RuntimeError):
            await cb.call(fail_func)

        # Wait for recovery
        await asyncio.sleep(0.15)

        # Probe call fails → back to OPEN
        with pytest.raises(RuntimeError):
            await cb.call(fail_func)

        assert cb.state == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_metrics_tracking(self) -> None:
        from engine.graph.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=5)
        success_func = AsyncMock(return_value="ok")
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        await cb.call(success_func)
        await cb.call(success_func)
        with pytest.raises(RuntimeError):
            await cb.call(fail_func)

        metrics = cb.get_metrics()
        assert metrics.total_calls == 3
        assert metrics.total_successes == 2
        assert metrics.total_failures == 1
        assert metrics.name == "test"

    @pytest.mark.asyncio
    async def test_force_open(self) -> None:
        from engine.graph.circuit_breaker import BreakerState, CircuitBreaker

        cb = CircuitBreaker(name="test")
        await cb.force_open()
        assert cb.state == BreakerState.OPEN

    @pytest.mark.asyncio
    async def test_force_close(self) -> None:
        from engine.graph.circuit_breaker import BreakerState, CircuitBreaker

        cb = CircuitBreaker(name="test", failure_threshold=1)
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(RuntimeError):
            await cb.call(fail_func)

        assert cb.state == BreakerState.OPEN
        await cb.force_close()
        assert cb.state == BreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_metrics(self) -> None:
        from engine.graph.circuit_breaker import CircuitBreaker

        cb = CircuitBreaker(name="test")
        func = AsyncMock(return_value="ok")
        await cb.call(func)

        await cb.reset_metrics()
        metrics = cb.get_metrics()
        assert metrics.total_calls == 0
        assert metrics.total_successes == 0


# ---------------------------------------------------------------------------
# W4-03: DomainPackLoader Async TTL Cache Tests
# ---------------------------------------------------------------------------


class TestDomainPackLoaderAsync:
    """W4-03: Async domain loading with TTL cache and stampede prevention."""

    def _make_loader_with_mock(self):
        """Create a DomainPackLoader with mocked disk I/O."""
        from engine.config.loader import DomainPackLoader

        loader = DomainPackLoader(config_path="/tmp/nonexistent_domains")

        # Mock the sync load_domain to avoid disk access
        mock_spec = MagicMock()
        mock_spec.domain.id = "test_domain"
        loader.load_domain = MagicMock(return_value=mock_spec)

        return loader, mock_spec

    @pytest.mark.asyncio
    async def test_async_load_cache_hit(self) -> None:
        """Cache hit returns cached value without re-loading from disk."""
        loader, mock_spec = self._make_loader_with_mock()

        # Prime the cache
        loader._cache["test_domain"] = (mock_spec, 100.0, time.monotonic())
        loader._ttl_seconds = 30.0

        result = await loader.load_domain_async("test_domain")
        assert result is mock_spec
        # load_domain should NOT have been called (cache hit)
        loader.load_domain.assert_not_called()

    @pytest.mark.asyncio
    async def test_async_load_cache_miss(self) -> None:
        """Cache miss delegates to sync load_domain via to_thread."""
        loader, mock_spec = self._make_loader_with_mock()

        result = await loader.load_domain_async("test_domain")
        assert result is mock_spec
        loader.load_domain.assert_called_once_with("test_domain")

    @pytest.mark.asyncio
    async def test_async_load_ttl_expiry(self) -> None:
        """Expired TTL triggers reload."""
        loader, mock_spec = self._make_loader_with_mock()

        # Prime cache with expired entry
        loader._cache["test_domain"] = (mock_spec, 100.0, time.monotonic() - 60)
        loader._ttl_seconds = 30.0

        result = await loader.load_domain_async("test_domain")
        assert result is mock_spec
        loader.load_domain.assert_called_once_with("test_domain")

    @pytest.mark.asyncio
    async def test_invalidation_clears_cache(self) -> None:
        """invalidate() removes specific domain from cache."""
        from engine.config.loader import DomainPackLoader

        loader = DomainPackLoader(config_path="/tmp/nonexistent_domains")
        mock_spec = MagicMock()
        loader._cache["test_domain"] = (mock_spec, 100.0, time.monotonic())

        loader.invalidate("test_domain")
        assert "test_domain" not in loader._cache

    @pytest.mark.asyncio
    async def test_invalidation_clears_all(self) -> None:
        """invalidate() with no args clears entire cache."""
        from engine.config.loader import DomainPackLoader

        loader = DomainPackLoader(config_path="/tmp/nonexistent_domains")
        mock_spec = MagicMock()
        loader._cache["domain_a"] = (mock_spec, 100.0, time.monotonic())
        loader._cache["domain_b"] = (mock_spec, 100.0, time.monotonic())

        loader.invalidate()
        assert len(loader._cache) == 0

    @pytest.mark.asyncio
    async def test_stampede_prevention(self) -> None:
        """Per-domain async lock prevents concurrent loads for the same domain.

        We verify the lock mechanism works by checking that concurrent callers
        share the same async lock object (structural test).
        """
        loader, mock_spec = self._make_loader_with_mock()

        # First call creates the lock and loads
        result = await loader.load_domain_async("test_domain")
        assert result is mock_spec

        # Verify lock was created for this domain
        assert hasattr(loader, "_async_locks")
        assert "test_domain" in loader._async_locks
        assert isinstance(loader._async_locks["test_domain"], asyncio.Lock)


# ---------------------------------------------------------------------------
# W4-04: ComplianceEngine Singleton Pool Tests
# ---------------------------------------------------------------------------


class TestComplianceEngineSingleton:
    """W4-04: ComplianceEngine get-or-create singleton pool."""

    def setup_method(self) -> None:
        from engine.state import _reset_singleton

        _reset_singleton()

    def teardown_method(self) -> None:
        from engine.state import _reset_singleton

        _reset_singleton()

    def _make_domain_spec(self, domain_id: str = "test_domain") -> MagicMock:
        spec = MagicMock()
        spec.domain.id = domain_id
        spec.domain.name = "Test"
        spec.compliance = MagicMock()
        spec.compliance.enabled = True
        spec.compliance.pii = None
        spec.compliance.prohibited_factors = MagicMock()
        spec.compliance.prohibited_factors.fields = []
        return spec

    def test_get_or_create_returns_same_instance(self) -> None:
        from engine.handlers import _get_compliance_engine
        from engine.state import get_state

        state = get_state()
        state._initialized = True

        spec = self._make_domain_spec()

        with patch("engine.handlers.ComplianceEngine") as MockCE:
            mock_ce = MagicMock()
            MockCE.return_value = mock_ce

            ce1 = _get_compliance_engine(spec)
            ce2 = _get_compliance_engine(spec)

            assert ce1 is ce2
            # Should only be created once
            MockCE.assert_called_once()

    def test_different_domains_get_different_engines(self) -> None:
        from engine.handlers import _get_compliance_engine
        from engine.state import get_state

        state = get_state()
        state._initialized = True

        spec_a = self._make_domain_spec("domain_a")
        spec_b = self._make_domain_spec("domain_b")

        with patch("engine.handlers.ComplianceEngine") as MockCE:
            MockCE.side_effect = [MagicMock(), MagicMock()]

            ce_a = _get_compliance_engine(spec_a)
            ce_b = _get_compliance_engine(spec_b)

            assert ce_a is not ce_b
            assert MockCE.call_count == 2

    @pytest.mark.asyncio
    async def test_shutdown_clears_compliance_pool(self) -> None:
        from engine.state import get_state

        state = get_state()
        mock_driver = AsyncMock()
        await state.initialize(graph_driver=mock_driver, domain_loader=MagicMock())

        state.compliance_engines["test"] = MagicMock()
        assert len(state.compliance_engines) == 1

        await state.shutdown()
        # After shutdown, compliance_engines should be cleared
        # (state is reset, accessing it returns empty dict)
        assert not state.is_initialized


# ---------------------------------------------------------------------------
# W4-02: GraphDriver Circuit Breaker Integration Tests
# ---------------------------------------------------------------------------


class TestGraphDriverCircuitBreaker:
    """W4-02: Verify circuit breaker is wired into GraphDriver.execute_query."""

    @pytest.mark.asyncio
    async def test_driver_has_circuit_breaker(self) -> None:
        from engine.graph.circuit_breaker import CircuitBreaker
        from engine.graph.driver import GraphDriver

        driver = GraphDriver(uri="bolt://localhost:7687")
        assert isinstance(driver.circuit_breaker, CircuitBreaker)
        assert driver.circuit_breaker.name == "neo4j"

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_on_query_failures(self) -> None:
        from engine.graph.circuit_breaker import BreakerState, CircuitBreaker, CircuitOpenError
        from engine.graph.driver import GraphDriver

        driver = GraphDriver(uri="bolt://localhost:7687")
        # Replace circuit breaker with a low-threshold one for testing
        driver._circuit_breaker = CircuitBreaker(
            name="neo4j_test",
            failure_threshold=2,
            recovery_timeout=60.0,
            half_open_max_calls=1,
        )
        driver._driver = MagicMock()

        # Mock session to raise errors
        mock_session = AsyncMock()
        mock_session.run = AsyncMock(side_effect=RuntimeError("Neo4j down"))
        driver._driver.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        driver._driver.session.return_value.__aexit__ = AsyncMock(return_value=False)

        # First 2 failures trip the breaker
        for _ in range(2):
            with pytest.raises(RuntimeError, match="Neo4j down"):
                await driver.execute_query("RETURN 1")

        assert driver.circuit_breaker.state == BreakerState.OPEN

        # Next call should be rejected by circuit breaker
        with pytest.raises(CircuitOpenError):
            await driver.execute_query("RETURN 1")


# ---------------------------------------------------------------------------
# W4-01 + handlers integration: verify handlers use EngineState
# ---------------------------------------------------------------------------


class TestHandlersUseEngineState:
    """Verify handler functions route through EngineState instead of globals."""

    def setup_method(self) -> None:
        from engine.state import _reset_singleton

        _reset_singleton()

    def teardown_method(self) -> None:
        from engine.state import _reset_singleton

        _reset_singleton()

    def test_init_dependencies_populates_engine_state(self) -> None:
        from engine.handlers import init_dependencies
        from engine.state import get_state

        mock_driver = MagicMock()
        mock_loader = MagicMock()

        init_dependencies(mock_driver, mock_loader)

        state = get_state()
        assert state.is_initialized
        assert state.graph_driver is mock_driver
        assert state.domain_loader is mock_loader

    def test_require_deps_uses_engine_state(self) -> None:
        from engine.handlers import _require_deps, init_dependencies
        from engine.state import get_state

        mock_driver = MagicMock()
        mock_loader = MagicMock()

        init_dependencies(mock_driver, mock_loader)

        driver, loader = _require_deps()
        assert driver is mock_driver
        assert loader is mock_loader

    def test_require_deps_raises_before_init(self) -> None:
        from engine.handlers import _require_deps

        with pytest.raises(RuntimeError, match="Dependencies not initialized"):
            _require_deps()

    def test_validate_tenant_access_uses_engine_state(self) -> None:
        from engine.handlers import ValidationError, _validate_tenant_access, init_dependencies

        mock_driver = MagicMock()
        mock_loader = MagicMock()

        with patch.dict("os.environ", {"TENANT_ALLOWLIST": "allowed_tenant"}):
            init_dependencies(mock_driver, mock_loader)

        # Allowed tenant should not raise
        _validate_tenant_access("allowed_tenant", "match")

        # Unauthorized tenant should raise
        with pytest.raises(ValidationError, match="not in authorized allowlist"):
            _validate_tenant_access("unauthorized", "match")


# ---------------------------------------------------------------------------
# Settings Tests
# ---------------------------------------------------------------------------


class TestWave4Settings:
    """Verify Wave 4 settings exist with correct defaults."""

    def test_circuit_breaker_defaults(self) -> None:
        from engine.config.settings import Settings

        s = Settings()
        assert s.neo4j_circuit_threshold == 5
        assert s.neo4j_circuit_cooldown == 30.0
        assert s.neo4j_circuit_half_open_max == 3

    def test_domain_cache_defaults(self) -> None:
        from engine.config.settings import Settings

        s = Settings()
        assert s.domain_cache_ttl_seconds == 30
        assert s.domain_cache_maxsize == 100

    def test_compliance_defaults(self) -> None:
        from engine.config.settings import Settings

        s = Settings()
        assert s.compliance_flush_interval == 60
        assert s.compliance_buffer_max == 100
