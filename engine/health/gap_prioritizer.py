"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, engines]
tags: [health, gap-prioritizer, enrichment]
owner: engine-team
status: active
--- /L9_META ---

Gap prioritizer v2 — inference-unlock-aware gap ranking.
Gate-critical fields ranked first, then inference unlock potential,
then scoring weight, then freshness.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.config.schema import DomainSpec
from engine.health.field_health import EnrichmentTarget, FieldHealth

logger = logging.getLogger(__name__)


def prioritize_gaps_v2(
    field_health: list[FieldHealth],
    domain_spec: DomainSpec,
    inference_rules: list[dict[str, Any]] | None = None,
) -> list[EnrichmentTarget]:
    """Rank unpopulated fields by enrichment priority.

    Priority scoring:
      +1000  if gate-critical
      +unlock_score * 100  for inference rules unlocked
      +scoring_weight * 50  for scoring dimension contribution
      +freshness_bonus      for temporal relevance
    """
    gaps = [f for f in field_health if not f.is_populated]
    targets: list[EnrichmentTarget] = []

    for gap in gaps:
        unlocked_rules: list[dict[str, Any]] = []
        unlock_score = 0.0

        if inference_rules:
            unlocked_rules = [
                rule
                for rule in inference_rules
                if gap.field_name in rule.get("input_fields", [])
                and all(
                    is_field_populated(f, field_health) for f in rule.get("input_fields", []) if f != gap.field_name
                )
            ]
            unlock_score = sum(
                get_field_importance(rule.get("output_field", ""), domain_spec) for rule in unlocked_rules
            )

        priority = (
            (1000 if gap.is_gate_critical else 0)
            + (unlock_score * 100)
            + (gap.scoring_weight * 50)
            + ((365 - (gap.staleness_days or 0)) / 365 * 10)
        )

        targets.append(
            EnrichmentTarget(
                field_name=gap.field_name,
                priority_score=priority,
                is_gate_critical=gap.is_gate_critical,
                unlocks_rules=[r.get("rule_id", "") for r in unlocked_rules],
                estimated_tokens=estimate_research_cost(gap, domain_spec),
            )
        )

    return sorted(targets, key=lambda t: t.priority_score, reverse=True)


def is_field_populated(field_name: str, field_health: list[FieldHealth]) -> bool:
    """Check if a field is populated in the current health assessment."""
    for fh in field_health:
        if fh.field_name == field_name:
            return fh.is_populated
    return False


def get_field_importance(field_name: str, domain_spec: DomainSpec) -> float:
    """Get the importance score for a field from the domain spec.

    Cross-references gates and scoring dimensions.
    """
    importance = 0.0

    # Check if field is gate-critical
    for gate in domain_spec.gates:
        if gate.candidateprop == field_name:
            importance += 1.0

    # Check scoring weight
    if domain_spec.scoring and domain_spec.scoring.dimensions:
        for dim in domain_spec.scoring.dimensions:
            prop_name = dim.candidateprop or ""
            if prop_name == field_name:
                importance += dim.defaultweight

    return importance


def estimate_research_cost(gap: FieldHealth, domain_spec: DomainSpec) -> int:
    """Estimate token cost to research/enrich a missing field.

    Gate-critical fields typically require more thorough research.
    """
    base_cost = 400  # Base research cost per field
    if gap.is_gate_critical:
        base_cost = 800  # Gate-critical fields need deeper research

    # Add complexity factor based on scoring weight
    complexity_factor = 1.0 + (gap.scoring_weight * 2)
    return int(base_cost * complexity_factor)
