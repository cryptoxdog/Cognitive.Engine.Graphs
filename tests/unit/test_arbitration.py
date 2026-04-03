from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

from engine.arbitration.engine import ArbitrationEngine
from engine.arbitration.schema import ArbitrationInput

SPEC_PATH = Path("domains/plasticos/spec.yaml")


@dataclass(frozen=True)
class _Constraint:
    metric: str
    operator: str
    value: object


@dataclass(frozen=True)
class _Weights:
    revenue: float
    margin: float
    risk: float
    capacity: float


@dataclass(frozen=True)
class _Thresholds:
    approve_threshold: float
    reject_threshold: float
    conflict_tolerance: float


@dataclass(frozen=True)
class _DecisionPolicy:
    version: str
    hard_constraints: list[_Constraint]
    weights: _Weights
    thresholds: _Thresholds


def _load_policy() -> _DecisionPolicy:
    raw = yaml.safe_load(SPEC_PATH.read_text())["decision_policy"]
    return _DecisionPolicy(
        version=str(raw["version"]),
        hard_constraints=[_Constraint(**item) for item in raw["hard_constraints"]],
        weights=_Weights(**raw["weights"]),
        thresholds=_Thresholds(**raw["thresholds"]),
    )


def test_arbitration_rejects_on_hard_constraint() -> None:
    engine = ArbitrationEngine()
    result = engine.resolve(
        _load_policy(),
        ArbitrationInput(revenue=0.9, margin=0.8, risk=0.9, capacity=0.7, compliance_pass=True),
    )
    assert result.final_decision == "reject"


def test_arbitration_approves_on_high_composite() -> None:
    engine = ArbitrationEngine()
    result = engine.resolve(
        _load_policy(),
        ArbitrationInput(revenue=0.9, margin=0.8, risk=0.2, capacity=0.9, compliance_pass=True),
    )
    assert result.final_decision == "approve"
    assert result.composite_score >= 0.5


def test_arbitration_input_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        ArbitrationInput(revenue=1.2, margin=0.0, risk=0.0, capacity=0.0, compliance_pass=True)
