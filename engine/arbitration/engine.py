"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [arbitration]
tags: [arbitration, engine]
owner: engine-team
status: active
--- /L9_META ---
"""

from __future__ import annotations

from typing import Literal, Protocol

from engine.arbitration.schema import ArbitrationInput, ArbitrationResult

DecisionState = Literal["approve", "reject", "defer", "escalate"]
ConstraintOperator = Literal["eq", "lt", "lte", "gt", "gte"]


class ConstraintPolicy(Protocol):
    metric: str
    operator: ConstraintOperator
    value: object


class PolicyWeights(Protocol):
    revenue: float
    margin: float
    risk: float
    capacity: float


class PolicyThresholds(Protocol):
    approve_threshold: float
    reject_threshold: float
    conflict_tolerance: float


class DecisionPolicy(Protocol):
    version: str
    hard_constraints: list[ConstraintPolicy]
    weights: PolicyWeights
    thresholds: PolicyThresholds


class ArbitrationEngine:
    def resolve(self, policy: DecisionPolicy, data: ArbitrationInput) -> ArbitrationResult:
        for constraint in policy.hard_constraints:
            actual = getattr(data, constraint.metric)
            passed = self._evaluate(actual, constraint.operator, constraint.value)
            if not passed:
                return ArbitrationResult(
                    final_decision="reject",
                    composite_score=0.0,
                    decision_reason=f"hard constraint failed: {constraint.metric} {constraint.operator} {constraint.value}",
                    policy_version=policy.version,
                )

        weights = policy.weights
        composite = (
            (data.revenue * weights.revenue)
            + (data.margin * weights.margin)
            - (data.risk * weights.risk)
            + (data.capacity * weights.capacity)
        )
        spread = max(data.revenue, data.margin, data.risk, data.capacity) - min(
            data.revenue, data.margin, data.risk, data.capacity
        )

        state: DecisionState
        if composite >= policy.thresholds.approve_threshold:
            state = "approve"
            reason = "composite score met approve threshold"
        elif composite < policy.thresholds.reject_threshold:
            state = "reject"
            reason = "composite score below reject threshold"
        elif spread > policy.thresholds.conflict_tolerance:
            state = "escalate"
            reason = "conflicting signals exceeded conflict tolerance"
        else:
            state = "defer"
            reason = "composite score fell in review band"

        return ArbitrationResult(
            final_decision=state,
            composite_score=round(composite, 6),
            decision_reason=reason,
            policy_version=policy.version,
        )

    @staticmethod
    def _evaluate(actual: object, operator: ConstraintOperator, expected: object) -> bool:
        if operator == "eq":
            return actual == expected

        if isinstance(actual, bool) or isinstance(expected, bool):
            msg = f"operator {operator!r} requires numeric operands"
            raise ValueError(msg)

        if not isinstance(actual, int | float) or not isinstance(expected, int | float):
            msg = f"operator {operator!r} requires numeric operands"
            raise ValueError(msg)

        try:
            actual_value = float(actual)
            expected_value = float(expected)
        except (TypeError, ValueError) as exc:
            msg = f"operator {operator!r} requires numeric operands"
            raise ValueError(msg) from exc

        if operator == "lt":
            return actual_value < expected_value
        if operator == "lte":
            return actual_value <= expected_value
        if operator == "gt":
            return actual_value > expected_value
        if operator == "gte":
            return actual_value >= expected_value
        raise ValueError(f"unsupported operator: {operator}")
