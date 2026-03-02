# tests/test_compliance_engine.py
"""Tests for ComplianceEngine orchestrator."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from engine.compliance.engine import ComplianceEngine


def _spec(*, enabled: bool = True, blocked: list[str] | None = None) -> MagicMock:
    s = MagicMock()
    s.compliance.prohibitedfactors.enabled = enabled
    s.compliance.prohibitedfactors.blockedfields = blocked or ["race", "religion"]
    s.compliance.pii.enabled = enabled
    s.compliance.audit.enabled = enabled
    return s


def test_enabled_when_configured() -> None:
    assert ComplianceEngine(_spec()).enabled is True


def test_disabled_when_no_compliance() -> None:
    s = MagicMock()
    s.compliance = None
    assert ComplianceEngine(s).enabled is False


def test_validate_gates_clean() -> None:
    gate = MagicMock(candidateprop="grade", queryparam="min_grade", name="g")
    ComplianceEngine(_spec()).validate_gates([gate])


def test_validate_gates_blocked() -> None:
    gate = MagicMock(candidateprop="race", queryparam="x", name="bad")
    with pytest.raises(ValueError, match="prohibited"):
        ComplianceEngine(_spec()).validate_gates([gate])


def test_redact_passthrough_when_disabled() -> None:
    s = MagicMock()
    s.compliance = None
    data = {"candidates": [{"ssn": "123"}]}
    assert ComplianceEngine(s).redact_response(data, "t") == data
