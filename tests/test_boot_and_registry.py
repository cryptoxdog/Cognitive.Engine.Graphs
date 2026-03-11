"""
Tests for engine/boot.py and engine/gates/registry.py.
Ensures module imports succeed and core classes/methods exist.
"""

from __future__ import annotations

import pytest


class TestBootModule:
    """Smoke tests for engine.boot module."""

    def test_import(self):
        """Module imports without errors."""
        import engine.boot  # noqa: F401

    def test_graph_lifecycle_class_exists(self):
        """GraphLifecycle class is exported from engine.boot."""
        from engine.boot import GraphLifecycle

        assert GraphLifecycle is not None

    def test_graph_lifecycle_instantiation(self):
        """GraphLifecycle can be instantiated with no args."""
        from engine.boot import GraphLifecycle

        lifecycle = GraphLifecycle()
        assert lifecycle is not None
        assert lifecycle._graph_driver is None
        assert lifecycle._domain_loader is None

    def test_graph_lifecycle_has_startup(self):
        """GraphLifecycle has a startup coroutine."""
        from engine.boot import GraphLifecycle
        import inspect

        lifecycle = GraphLifecycle()
        assert hasattr(lifecycle, "startup")
        assert inspect.iscoroutinefunction(lifecycle.startup)

    def test_graph_lifecycle_has_shutdown(self):
        """GraphLifecycle has a shutdown coroutine."""
        from engine.boot import GraphLifecycle
        import inspect

        lifecycle = GraphLifecycle()
        assert hasattr(lifecycle, "shutdown")
        assert inspect.iscoroutinefunction(lifecycle.shutdown)

    def test_graph_lifecycle_has_execute(self):
        """GraphLifecycle has an execute coroutine."""
        from engine.boot import GraphLifecycle
        import inspect

        lifecycle = GraphLifecycle()
        assert hasattr(lifecycle, "execute")
        assert inspect.iscoroutinefunction(lifecycle.execute)

    @pytest.mark.asyncio
    async def test_shutdown_noop_when_no_driver(self):
        """Shutdown is a no-op when _graph_driver is None."""
        from engine.boot import GraphLifecycle

        lifecycle = GraphLifecycle()
        # Should not raise
        await lifecycle.shutdown()


class TestGateRegistry:
    """Tests for engine.gates.registry.GateRegistry."""

    def test_import(self):
        """Module imports without errors."""
        import engine.gates.registry  # noqa: F401

    def test_gate_registry_class_exists(self):
        """GateRegistry class is accessible."""
        from engine.gates.registry import GateRegistry

        assert GateRegistry is not None

    def test_registry_has_all_gate_types(self):
        """GateRegistry has entries for all expected GateType values."""
        from engine.config.schema import GateType
        from engine.gates.registry import GateRegistry

        expected = {
            GateType.RANGE,
            GateType.THRESHOLD,
            GateType.BOOLEAN,
            GateType.COMPOSITE,
            GateType.ENUMMAP,
            GateType.EXCLUSION,
            GateType.SELFRANGE,
            GateType.FRESHNESS,
            GateType.TEMPORALRANGE,
            GateType.TRAVERSAL,
        }
        for gate_type in expected:
            cls = GateRegistry.get_gate_class(gate_type)
            assert cls is not None, f"Missing gate class for {gate_type}"

    def test_get_gate_class_returns_base_gate_subclass(self):
        """All registered gate classes are subclasses of BaseGate."""
        from engine.config.schema import GateType
        from engine.gates.registry import GateRegistry
        from engine.gates.types.all_gates import BaseGate

        for gate_type in GateType:
            try:
                cls = GateRegistry.get_gate_class(gate_type)
                assert issubclass(cls, BaseGate), f"{cls} is not a BaseGate subclass"
            except ValueError:
                pass  # BOOLEAN_LOOKUP or future types not yet registered — OK

    def test_get_gate_class_raises_for_unknown_type(self):
        """get_gate_class raises ValueError for an unregistered gate type."""
        from engine.config.schema import GateType
        from engine.gates.registry import GateRegistry

        # Monkey-patch a fake gate_type not in registry
        registry_copy = dict(GateRegistry._REGISTRY)
        GateRegistry._REGISTRY.clear()
        try:
            with pytest.raises(ValueError, match="No gate implementation"):
                GateRegistry.get_gate_class(GateType.RANGE)
        finally:
            GateRegistry._REGISTRY.update(registry_copy)
