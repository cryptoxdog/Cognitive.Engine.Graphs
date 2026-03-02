# tests/test_compliance_engine.py
"""Tests for ComplianceEngine orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

import pytest

from engine.compliance.engine import ComplianceEngine

# ── Type-safe test fixtures ──────────────────────────────────


@dataclass
class MockProhibitedFactors:
    enabled: bool = True
    blockedfields: list[str] = field(default_factory=lambda: ["race", "religion"])


@dataclass
class MockPII:
    enabled: bool = True
    additional_fields: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass
class MockAudit:
    enabled: bool = True


@dataclass
class MockCompliance:
    prohibitedfactors: MockProhibitedFactors = field(default_factory=MockProhibitedFactors)
    pii: MockPII = field(default_factory=MockPII)
    audit: MockAudit = field(default_factory=MockAudit)


@dataclass
class MockDomainSpec:
    compliance: MockCompliance | None = field(default_factory=MockCompliance)


def _spec(*, enabled: bool = True, blocked: list[str] | None = None) -> MockDomainSpec:
    """Create mock DomainSpec with proper structure."""
    return MockDomainSpec(
        compliance=MockCompliance(
            prohibitedfactors=MockProhibitedFactors(
                enabled=enabled,
                blockedfields=blocked or ["race", "religion"],
            ),
            pii=MockPII(enabled=enabled),
            audit=MockAudit(enabled=enabled),
        )
    )


def test_enabled_when_configured() -> None:
    assert ComplianceEngine(_spec()).enabled is True


def test_disabled_when_no_compliance() -> None:
    s = MockDomainSpec(compliance=None)
    assert ComplianceEngine(s).enabled is False


def test_validate_gates_clean() -> None:
    gate = MagicMock(candidateprop="grade", queryparam="min_grade", name="g")
    ComplianceEngine(_spec()).validate_gates([gate])


def test_validate_gates_blocked() -> None:
    gate = MagicMock(candidateprop="race", queryparam="x", name="bad")
    with pytest.raises(ValueError, match="prohibited"):
        ComplianceEngine(_spec()).validate_gates([gate])


def test_redact_passthrough_when_disabled() -> None:
    s = MockDomainSpec(compliance=None)
    data = {"candidates": [{"ssn": "123"}]}
    assert ComplianceEngine(s).redact_response(data, "t") == data
