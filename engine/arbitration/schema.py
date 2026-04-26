from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DecisionState = Literal["approve", "reject", "defer", "escalate"]


class ArbitrationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revenue: float
    margin: float
    risk: float
    capacity: float
    compliance_pass: bool

    @model_validator(mode="after")
    def validate_ranges(self) -> ArbitrationInput:
        for field_name in ("revenue", "margin", "risk", "capacity"):
            value = getattr(self, field_name)
            if value < 0.0 or value > 1.0:
                raise ValueError(f"{field_name} must be in [0, 1]")
        return self


class ArbitrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_decision: DecisionState
    composite_score: float
    decision_reason: str
    policy_version: str


class HardConstraint(BaseModel):
    metric: str
    operator: Literal["eq", "lt", "lte", "gt", "gte"]
    value: float


class PolicyWeights(BaseModel):
    revenue: float = 0.25
    margin: float = 0.25
    risk: float = 0.25
    capacity: float = 0.25


class PolicyThresholds(BaseModel):
    approve_threshold: float = 0.7
    reject_threshold: float = 0.3
    conflict_tolerance: float = 0.4


class DecisionPolicy(BaseModel):
    version: str
    hard_constraints: list[HardConstraint] = Field(default_factory=list)
    weights: PolicyWeights = Field(default_factory=PolicyWeights)
    thresholds: PolicyThresholds = Field(default_factory=PolicyThresholds)
