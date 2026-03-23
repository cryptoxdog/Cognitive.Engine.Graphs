"""
Invariant regression tests — Trust boundary violations (T1-xx findings).

Each test recreates the condition that would trigger the original defect
and asserts the fix prevents it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.mark.finding("T1-01")
class TestT101ExecSandbox:
    """T1-01: safe_exec sandbox must not allow unrestricted eval/exec."""

    def test_no_bare_exec_in_engine(self):
        """Engine code (except safe_eval.py) must not use exec()."""
        engine_dir = ROOT / "engine"
        for f in engine_dir.rglob("*.py"):
            if f.name == "safe_eval.py":
                continue
            content = f.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                assert not re.search(r"\bexec\s*\(", stripped), (
                    f"T1-01: bare exec() found in {f.relative_to(ROOT)}:{line_no}"
                )

    def test_no_bare_eval_in_engine(self):
        """Engine code (except safe_eval.py) must not use eval()."""
        engine_dir = ROOT / "engine"
        for f in engine_dir.rglob("*.py"):
            if f.name == "safe_eval.py":
                continue
            content = f.read_text(encoding="utf-8")
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                assert not re.search(r"\beval\s*\(", stripped), (
                    f"T1-01: bare eval() found in {f.relative_to(ROOT)}:{line_no}"
                )

    def test_no_pickle_in_engine(self):
        """No pickle usage in engine/ (deserialization attack vector)."""
        engine_dir = ROOT / "engine"
        for f in engine_dir.rglob("*.py"):
            content = f.read_text(encoding="utf-8")
            assert "pickle.load" not in content, f"T1-01: pickle.load in {f.relative_to(ROOT)}"


@pytest.mark.finding("T1-03")
class TestT103TenantIsolation:
    """T1-03: Tenant isolation must be enforced — allowlist check."""

    def test_tenant_allowlist_rejects_unauthorized(self):
        """_validate_tenant_access raises for tenants not in allowlist."""
        from engine.handlers import ValidationError, _validate_tenant_access

        # Simulate an allowlist
        import engine.handlers as h

        original = h._tenant_allowlist
        try:
            h._tenant_allowlist = {"tenant_a", "tenant_b"}
            with pytest.raises(ValidationError):
                _validate_tenant_access("evil_tenant", "match")
        finally:
            h._tenant_allowlist = original

    def test_tenant_allowlist_allows_authorized(self):
        """Authorized tenants pass the check."""
        from engine.handlers import _validate_tenant_access

        import engine.handlers as h

        original = h._tenant_allowlist
        try:
            h._tenant_allowlist = {"tenant_a"}
            # Should not raise
            _validate_tenant_access("tenant_a", "match")
        finally:
            h._tenant_allowlist = original

    def test_no_allowlist_permits_all(self):
        """When allowlist is None (dev mode), all tenants allowed."""
        from engine.handlers import _validate_tenant_access

        import engine.handlers as h

        original = h._tenant_allowlist
        try:
            h._tenant_allowlist = None
            _validate_tenant_access("any_tenant", "match")
        finally:
            h._tenant_allowlist = original


@pytest.mark.finding("T1-05")
class TestT105ParameterResolution:
    """T1-05: ParameterResolver must not silently swallow errors."""

    def test_strict_mode_raises_on_bad_expression(self):
        """With param_strict_mode, failed derived params raise ParameterResolutionError."""
        from engine.config.schema import DerivedParameterSpec, PropertyType
        from engine.traversal.resolver import ParameterResolutionError, ParameterResolver

        # Build a minimal spec with a bad derived parameter
        spec = _build_minimal_spec_for_resolver(
            derived=[
                DerivedParameterSpec(
                    name="bad_param",
                    expression="1 / 0",  # Division by zero
                    type=PropertyType.FLOAT,
                ),
            ]
        )
        resolver = ParameterResolver(spec)
        with patch("engine.config.settings.settings") as mock_settings:
            mock_settings.param_strict_mode = True
            with pytest.raises(ParameterResolutionError):
                resolver.resolve_parameters({"x": 1})


def _build_minimal_spec_for_resolver(derived=None):
    """Build a minimal DomainSpec for ParameterResolver tests."""
    from engine.config.schema import (
        DomainMetadata,
        DomainSpec,
        EdgeCategory,
        EdgeDirection,
        EdgeSpec,
        ManagedByType,
        MatchEntitiesSpec,
        MatchEntitySpec,
        NodeSpec,
        OntologySpec,
        PropertySpec,
        PropertyType,
        QueryFieldSpec,
        QuerySchemaSpec,
        ScoringSpec,
    )

    return DomainSpec(
        domain=DomainMetadata(id="test", name="Test", version="1.0.0"),
        ontology=OntologySpec(
            nodes=[
                NodeSpec(label="N", candidate=True, properties=[PropertySpec(name="x", type=PropertyType.FLOAT)]),
                NodeSpec(label="Q", queryentity=True),
            ],
            edges=[
                EdgeSpec(
                    type="R", **{"from": "N"}, to="Q",
                    direction=EdgeDirection.DIRECTED,
                    category=EdgeCategory.CAPABILITY,
                    managedby=ManagedByType.SYNC,
                ),
            ],
        ),
        matchentities=MatchEntitiesSpec(
            candidate=[MatchEntitySpec(label="N", matchdirection="fwd")],
            queryentity=[MatchEntitySpec(label="Q", matchdirection="fwd")],
        ),
        queryschema=QuerySchemaSpec(
            matchdirections=["fwd"],
            fields=[QueryFieldSpec(name="x", type=PropertyType.FLOAT)],
        ),
        gates=[],
        scoring=ScoringSpec(dimensions=[]),
        derivedparameters=derived or [],
    )


@pytest.mark.finding("T1-06")
class TestT106UnboundedScores:
    """T1-06: Score clamping must prevent unbounded scores."""

    def test_score_clamp_enabled(self):
        """W1-02 clamp setting exists and is True by default."""
        from engine.config.settings import Settings

        s = Settings()
        assert s.score_clamp_enabled is True

    def test_clamp_expression_format(self):
        """ScoringAssembler._clamp_expression wraps correctly."""
        from engine.scoring.assembler import ScoringAssembler

        result = ScoringAssembler._clamp_expression("some_expr")
        assert "CASE" in result
        assert "< 0.0 THEN 0.0" in result
        assert "> 1.0 THEN 1.0" in result
