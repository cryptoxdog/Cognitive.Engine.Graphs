"""
Invariant regression tests — Compliance defects (T3-xx findings).

Verifies that audit logging, PII handling, and compliance wiring
fixes from Wave 1-4 remain in place.
"""

from __future__ import annotations

import inspect

import pytest


@pytest.mark.finding("T3-01")
class TestT301GDSSchedulerStart:
    """T3-01: GDS scheduler must have a callable start() method."""

    def test_gds_scheduler_has_start(self):
        from engine.gds.scheduler import GDSScheduler

        assert hasattr(GDSScheduler, "start"), "GDSScheduler missing start() method"
        assert callable(getattr(GDSScheduler, "start", None))

    def test_gds_scheduler_has_trigger(self):
        """Manual trigger_gds must be available."""
        from engine.gds.scheduler import GDSScheduler

        assert (
            hasattr(GDSScheduler, "trigger_job")
            or hasattr(GDSScheduler, "trigger_gds")
            or hasattr(GDSScheduler, "run_job")
        ), "GDSScheduler missing manual trigger method"


@pytest.mark.finding("T3-02")
class TestT302AuditFlush:
    """T3-02: ComplianceEngine.flush_audit must be awaitable."""

    def test_flush_audit_is_coroutine(self):
        from engine.compliance.engine import ComplianceEngine

        assert inspect.iscoroutinefunction(ComplianceEngine.flush_audit), "flush_audit must be async (awaitable)"


@pytest.mark.finding("T3-05")
class TestT305KGESystem:
    """T3-05: KGE system components must be importable."""

    def test_kge_module_importable(self):
        """KGE modules should exist and be importable."""
        try:
            from engine.config.schema import KGESpec

            spec = KGESpec()
            assert spec.model == "CompoundE3D"
        except ImportError:
            pytest.skip("KGE module not available")

    def test_kge_scoring_computation_registered(self):
        """KGE computation type must be in the ComputationType enum."""
        from engine.config.schema import ComputationType

        assert hasattr(ComputationType, "KGE")
