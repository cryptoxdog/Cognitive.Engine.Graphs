"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, compliance]
owner: engine-team
status: active
--- /L9_META ---

Tests for ComplianceEngine orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from engine.compliance.engine import ComplianceEngine


@dataclass
class _MockProhibitedFactors:
    enabled: bool = True
    blockedfields: list[str] = field(default_factory=lambda: ["race", "religion"])


@dataclass
class _MockPII:
    enabled: bool = True


@dataclass
class _MockAudit:
    enabled: bool = True


@dataclass
class _MockCompliance:
    prohibitedfactors: _MockProhibitedFactors = field(default_factory=_MockProhibitedFactors)
    pii: _MockPII = field(default_factory=_MockPII)
    audit: _MockAudit = field(default_factory=_MockAudit)


@dataclass
class _MockDomainSpec:
    compliance: _MockCompliance | None = field(default_factory=_MockCompliance)


def _spec(*, enabled: bool = True, blocked: list[str] | None = None) -> _MockDomainSpec:
    """Typed compliance/domain spec fixture for ComplianceEngine tests."""
    return _MockDomainSpec(
        compliance=_MockCompliance(
            prohibitedfactors=_MockProhibitedFactors(
                enabled=enabled,
                blockedfields=blocked or ["race", "religion"],
            ),
            pii=_MockPII(enabled=enabled),
            audit=_MockAudit(enabled=enabled),
        )
    )


def test_enabled_when_configured() -> None:
    assert ComplianceEngine(_spec()).enabled is True


def test_enabled_by_default_when_no_compliance() -> None:
    """Compliance defaults to enabled for SOC2/HIPAA safety even without explicit config."""
    s = _MockDomainSpec(compliance=None)
    assert ComplianceEngine(s).enabled is True


@dataclass
class _MockComplianceDisabled:
    """Compliance config with enabled=False."""

    enabled: bool = False
    prohibitedfactors: _MockProhibitedFactors = field(default_factory=_MockProhibitedFactors)
    pii: _MockPII = field(default_factory=_MockPII)
    audit: _MockAudit = field(default_factory=_MockAudit)


def test_disabled_when_explicitly_false() -> None:
    """Compliance only disabled when explicitly set to False."""
    s = _MockDomainSpec(compliance=_MockComplianceDisabled(enabled=False))
    assert ComplianceEngine(s).enabled is False


@dataclass
class _MockGate:
    """Typed gate fixture for ComplianceEngine tests."""

    candidateprop: str
    queryparam: str
    name: str


def test_validate_gates_clean() -> None:
    gate = _MockGate(candidateprop="grade", queryparam="min_grade", name="g")
    ComplianceEngine(_spec()).validate_gates([gate])


def test_validate_gates_blocked() -> None:
    gate = _MockGate(candidateprop="race", queryparam="x", name="bad")
    with pytest.raises(ValueError, match="prohibited"):
        ComplianceEngine(_spec()).validate_gates([gate])


def test_redact_passthrough_when_disabled() -> None:
    s = _MockDomainSpec(compliance=None)
    data = {"candidates": [{"ssn": "123"}]}
    assert ComplianceEngine(s).redact_response(data, "t") == data
