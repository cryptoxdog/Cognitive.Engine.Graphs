"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, engines]
tags: [health, readiness, scoring]
owner: engine-team
status: active
--- /L9_META ---

Readiness scorer v2 — 60/25/10/5 weighted formula.
Gate-critical dominant. Blocks on < 50% gate completeness.
"""

from __future__ import annotations

import logging

from engine.config.schema import DomainSpec
from engine.health.domain_field_mapper import _extract_inference_rules
from engine.health.field_health import FieldHealth, ReadinessScore

logger = logging.getLogger(__name__)

# Confidence threshold for considering a field "reliably populated"
_CONFIDENCE_THRESHOLD = 0.70

# Gate blocking threshold — below this, score caps at F
_GATE_BLOCK_THRESHOLD = 0.50


def compute_readiness_score_v2(
    field_health: list[FieldHealth],
    domain_spec: DomainSpec,
) -> ReadinessScore:
    """Compute readiness score using the v2 weighted formula.

    Weights:
      60% — Gate-Critical Completeness (BLOCKING)
      25% — Weighted Scoring Dimension Coverage
      10% — Inference Unlock Potential
       5% — Temporal Freshness (1 - staleness_penalty)
    """
    # GATE 1: Gate-Critical Completeness (BLOCKING) — 60%
    gate_fields = [f for f in field_health if f.is_gate_critical]
    if not gate_fields:
        gate_score = 1.0
    else:
        populated_gates = sum(1 for f in gate_fields if f.is_populated and (f.confidence or 0) >= _CONFIDENCE_THRESHOLD)
        gate_score = populated_gates / len(gate_fields)

    if gate_score < _GATE_BLOCK_THRESHOLD:
        return ReadinessScore(
            overall_score=gate_score * 100,
            grade="F",
            gate_completeness=gate_score,
            scoring_dimension_coverage=0.0,
            blocking_reason="gate_critical_fields_missing",
            recommended_action="enrich_gates_first",
            blocking_fields=[f.field_name for f in gate_fields if not f.is_populated],
        )

    # COMPONENT 2: Weighted Scoring Dimension Coverage — 25%
    scoring_fields = [f for f in field_health if f.scoring_weight > 0]
    weighted_coverage = sum(
        f.scoring_weight * (1.0 if f.is_populated and (f.confidence or 0) >= _CONFIDENCE_THRESHOLD else 0.0)
        for f in scoring_fields
    )
    max_possible_weight = sum(f.scoring_weight for f in scoring_fields)
    scoring_coverage = weighted_coverage / max_possible_weight if max_possible_weight > 0 else 0.5

    # COMPONENT 3: Inference Unlock Potential — 10%
    inference_unlock_score = compute_inference_potential(field_health, domain_spec)

    # COMPONENT 4: Temporal Decay — 5%
    staleness_penalty = compute_staleness_penalty(field_health)

    # FINAL SCORE
    final_score = (
        gate_score * 0.60 + scoring_coverage * 0.25 + inference_unlock_score * 0.10 + (1 - staleness_penalty) * 0.05
    )

    return ReadinessScore(
        overall_score=round(final_score * 100, 2),
        grade=get_grade(final_score),
        gate_completeness=gate_score,
        scoring_dimension_coverage=scoring_coverage,
        inference_unlock_potential=inference_unlock_score,
        staleness_penalty=staleness_penalty,
        blocking_fields=[f.field_name for f in gate_fields if not f.is_populated],
    )


def compute_inference_potential(
    field_health: list[FieldHealth],
    domain_spec: DomainSpec,
) -> float:
    """Estimate what fraction of inference rules could fire if gaps were filled.

    Returns 0.0-1.0 where 1.0 means all inference rules are already satisfiable.
    """
    inference_rules = _extract_inference_rules(domain_spec)
    if not inference_rules:
        return 0.5  # Default when no inference rules defined

    populated_fields = {f.field_name for f in field_health if f.is_populated}
    satisfiable = 0
    for rule in inference_rules:
        input_fields = rule.get("input_fields", [])
        if input_fields and all(f in populated_fields for f in input_fields):
            satisfiable += 1

    return satisfiable / len(inference_rules) if inference_rules else 0.5


def compute_staleness_penalty(field_health: list[FieldHealth]) -> float:
    """Compute aggregate staleness penalty across all fields.

    Returns 0.0 (all fresh) to 1.0 (all stale).
    Fields older than 365 days receive maximum penalty.
    """
    stale_fields = [f for f in field_health if f.staleness_days is not None]
    if not stale_fields:
        return 0.0  # No staleness data = assume fresh

    penalties = [min(f.staleness_days / 365, 1.0) for f in stale_fields if f.staleness_days is not None]
    return sum(penalties) / len(penalties) if penalties else 0.0


def get_grade(score: float) -> str:
    """Convert 0.0-1.0 score to letter grade."""
    if score >= 0.90:
        return "A"
    if score >= 0.80:
        return "B"
    if score >= 0.70:
        return "C"
    if score >= 0.60:
        return "D"
    return "F"
