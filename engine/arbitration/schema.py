"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [arbitration]
tags: [arbitration, schema]
owner: engine-team
status: active
--- /L9_META ---
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

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
