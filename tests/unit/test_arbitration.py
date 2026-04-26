from pathlib import Path

import pytest

from engine.arbitration.engine import ArbitrationEngine
from engine.arbitration.schema import ArbitrationInput
from engine.config.loader import DomainPackLoader

SPEC_PATH = Path("domains/plasticos/spec.yaml")


def test_arbitration_rejects_on_hard_constraint() -> None:
    loader = DomainPackLoader(config_path=str(SPEC_PATH))
    engine = ArbitrationEngine()
    result = engine.resolve(
        loader.spec.decision_policy,
        ArbitrationInput(revenue=0.9, margin=0.8, risk=0.9, capacity=0.7, compliance_pass=True),
    )
    assert result.final_decision == "reject"


def test_arbitration_approves_on_high_composite() -> None:
    loader = DomainPackLoader(config_path=str(SPEC_PATH))
    engine = ArbitrationEngine()
    result = engine.resolve(
        loader.spec.decision_policy,
        ArbitrationInput(revenue=0.9, margin=0.8, risk=0.2, capacity=0.9, compliance_pass=True),
    )
    assert result.final_decision == "approve"
    assert result.composite_score >= 0.5


def test_arbitration_input_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        ArbitrationInput(revenue=1.2, margin=0.0, risk=0.0, capacity=0.0, compliance_pass=True)
