from __future__ import annotations

import pytest

from engine.arbitration.engine import ArbitrationEngine
from engine.arbitration.schema import (
    ArbitrationInput,
    DecisionPolicy,
    HardConstraint,
    PolicyThresholds,
    PolicyWeights,
)


def _policy_with_risk_cap() -> DecisionPolicy:
    return DecisionPolicy(
        version="1.0.0",
        hard_constraints=[HardConstraint(metric="risk", operator="lte", value=0.8)],
        weights=PolicyWeights(),
        thresholds=PolicyThresholds(),
    )


def _default_policy() -> DecisionPolicy:
    return DecisionPolicy(
        version="1.0.0",
        hard_constraints=[],
        weights=PolicyWeights(),
        thresholds=PolicyThresholds(),
    )


def test_arbitration_rejects_on_hard_constraint() -> None:
    engine = ArbitrationEngine()
    result = engine.resolve(
        _policy_with_risk_cap(),
        ArbitrationInput(revenue=0.9, margin=0.8, risk=0.9, capacity=0.7, compliance_pass=True),
    )
    assert result.final_decision == "reject"


def test_arbitration_approves_on_high_composite() -> None:
    engine = ArbitrationEngine()
    result = engine.resolve(
        _default_policy(),
        ArbitrationInput(revenue=1.0, margin=1.0, risk=0.0, capacity=1.0, compliance_pass=True),
    )
    assert result.final_decision == "approve"
    assert result.composite_score >= 0.5


def test_arbitration_input_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        ArbitrationInput(revenue=1.2, margin=0.0, risk=0.0, capacity=0.0, compliance_pass=True)
