from __future__ import annotations

from engine.arbitration.schema import (
    ArbitrationInput,
    ArbitrationResult,
    DecisionPolicy,
    DecisionState,
)


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
    def _evaluate(actual: float, operator: str, expected: float) -> bool:
        if operator == "eq":
            return actual == expected
        if operator == "lt":
            return actual < expected
        if operator == "lte":
            return actual <= expected
        if operator == "gt":
            return actual > expected
        if operator == "gte":
            return actual >= expected
        raise ValueError(f"unsupported operator: {operator}")
