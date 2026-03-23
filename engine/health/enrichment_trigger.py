"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, services]
tags: [health, enrichment, roi, trigger]
owner: engine-team
status: active
--- /L9_META ---

ROI-based enrichment trigger + MatchQualityDelta feedback loop.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.config.schema import DomainSpec
from engine.health.field_health import EnrichmentPriority, EntityHealth, MatchQualityDelta

logger = logging.getLogger(__name__)


def compute_enrichment_priority(
    entity_health: EntityHealth,
    domain_spec: DomainSpec,
    historical_outcomes: list[Any] | None = None,
) -> EnrichmentPriority:
    """Compute ROI-based enrichment priority for an entity.

    Priority weights:
      40% — ROI score
      30% — Gate gap score
      20% — Historical failure score
      10% — Staleness score
    """
    missing_critical = len(entity_health.critical_gaps)
    missing_scoring = len([f for f in entity_health.field_health if not f.is_populated and f.scoring_weight > 0])

    variation_count = min(3 + (missing_critical * 0.5), 5)
    estimated_cost = ((missing_critical * 800) + (missing_scoring * 400)) * variation_count
    cost_usd = (estimated_cost / 1_000_000) * 5

    # Value estimation
    current_match_prob = estimate_match_probability(entity_health.readiness_score, historical_outcomes)
    projected_score = project_post_enrichment_score(entity_health, domain_spec)
    projected_match_prob = estimate_match_probability(projected_score, historical_outcomes)
    match_prob_delta = projected_match_prob - current_match_prob

    avg_deal_value = get_avg_deal_value_from_domain(domain_spec)
    expected_value = match_prob_delta * avg_deal_value

    roi = (expected_value - cost_usd) / cost_usd if cost_usd > 0 else 0

    roi_score = min(roi / 10, 1.0)
    gate_gap_score = 1 - entity_health.gate_completeness
    failure_score = min(
        len([o for o in (historical_outcomes or []) if getattr(o, "outcome", "") == "rejected"]) / 5,
        1.0,
    )
    staleness_score: float = getattr(entity_health, "staleness_penalty", 0.0)

    priority_score = (roi_score * 0.40 + gate_gap_score * 0.30 + failure_score * 0.20 + staleness_score * 0.10) * 100

    if priority_score >= 70 and roi > 2.0:
        rec = "enrich_now"
    elif priority_score >= 40 and roi > 0.5:
        rec = "enrich_low_priority"
    else:
        rec = "skip"

    return EnrichmentPriority(
        priority_score=round(priority_score, 2),
        estimated_cost_tokens=int(estimated_cost),
        estimated_cost_usd=round(cost_usd, 2),
        expected_value_usd=round(expected_value, 2),
        roi=round(roi, 2),
        recommendation=rec,  # type: ignore[arg-type]
        reasoning=f"ROI={roi:.1f}x, gate_gap={gate_gap_score:.2f}, failures={failure_score:.2f}",
    )


def estimate_match_probability(
    readiness_score: float,
    historical_outcomes: list[Any] | None = None,
) -> float:
    """Estimate match probability from readiness score.

    Uses historical outcomes if available, otherwise applies sigmoid approximation.
    """
    if historical_outcomes:
        successful = sum(1 for o in historical_outcomes if getattr(o, "outcome", "") == "matched")
        total = len(historical_outcomes)
        if total > 0:
            base_rate = successful / total
            # Adjust by readiness score relative to 100
            return min(base_rate * (readiness_score / 100), 1.0)

    # Sigmoid approximation: score of 80 → ~0.73, score of 50 → ~0.27
    import math

    x = (readiness_score - 60) / 15
    return 1 / (1 + math.exp(-x))


def project_post_enrichment_score(
    entity_health: EntityHealth,
    domain_spec: DomainSpec,
) -> float:
    """Project what the readiness score would be after enrichment.

    Assumes all critical gaps and top scoring gaps get filled.
    """
    current = entity_health.readiness_score

    # Gate improvement: assume all critical gaps get filled
    if entity_health.gate_completeness < 1.0:
        gate_improvement = (1.0 - entity_health.gate_completeness) * 60  # 60% weight
        current += gate_improvement

    # Scoring improvement: assume top scoring gaps get filled
    if entity_health.scoring_dimension_coverage < 1.0:
        scoring_improvement = (1.0 - entity_health.scoring_dimension_coverage) * 25  # 25% weight
        current += scoring_improvement

    return min(current, 100.0)


def get_avg_deal_value_from_domain(domain_spec: DomainSpec) -> float:
    """Extract average deal value from domain metadata.

    Falls back to a conservative default if not specified.
    """
    # Check domain metadata for deal value hints
    if hasattr(domain_spec.domain, "description") and domain_spec.domain.description:
        desc = domain_spec.domain.description.lower()
        if "enterprise" in desc:
            return 50000.0
        if "marketplace" in desc:
            return 5000.0
    return 1000.0  # Conservative default


def measure_health_impact(
    entity_id: str,
    domain: str,
    health_before: EntityHealth,
    health_after: EntityHealth,
    enrichment_cost_usd: float = 0.0,
    enrichment_tokens: int = 0,
    match_outcomes_before: list[Any] | None = None,
    match_outcomes_after: list[Any] | None = None,
) -> MatchQualityDelta:
    """Measure the impact of enrichment on an entity's health and match quality."""
    avg_before = None
    avg_after = None
    improvement = None
    matches_before = len(match_outcomes_before) if match_outcomes_before else 0
    matches_after = len(match_outcomes_after) if match_outcomes_after else 0

    if match_outcomes_before:
        scores = [getattr(o, "score", 0) for o in match_outcomes_before]
        avg_before = sum(scores) / len(scores) if scores else None

    if match_outcomes_after:
        scores = [getattr(o, "score", 0) for o in match_outcomes_after]
        avg_after = sum(scores) / len(scores) if scores else None

    if avg_before is not None and avg_after is not None:
        improvement = avg_after - avg_before

    readiness_improvement = health_after.readiness_score - health_before.readiness_score
    gate_improvement = health_after.gate_completeness - health_before.gate_completeness

    roi = None
    if enrichment_cost_usd > 0 and readiness_improvement > 0:
        roi = readiness_improvement / enrichment_cost_usd

    return MatchQualityDelta(
        entity_id=entity_id,
        domain=domain,
        readiness_score_before=health_before.readiness_score,
        readiness_score_after=health_after.readiness_score,
        readiness_improvement=readiness_improvement,
        gate_pass_rate_before=health_before.gate_completeness,
        gate_pass_rate_after=health_after.gate_completeness,
        gate_pass_improvement=gate_improvement,
        avg_match_score_before=avg_before,
        avg_match_score_after=avg_after,
        match_score_improvement=improvement,
        matches_before_count=matches_before,
        matches_after_count=matches_after,
        matches_delta=matches_after - matches_before,
        enrichment_cost_usd=enrichment_cost_usd,
        enrichment_tokens=enrichment_tokens,
        roi=roi,
    )


async def trigger_reenrichment_v2(
    entity_health: EntityHealth,
    domain_spec: DomainSpec,
    tenant: str,
    historical_outcomes: list[Any] | None = None,
) -> dict[str, Any]:
    """Trigger re-enrichment via PacketEnvelope if ROI justifies it.

    Returns the enrichment decision and packet metadata.
    """
    priority = compute_enrichment_priority(entity_health, domain_spec, historical_outcomes)

    if priority.recommendation == "skip":
        return {
            "triggered": False,
            "reason": priority.reasoning,
            "priority": priority.model_dump(),
        }

    # Build enrichment packet payload
    enrichment_payload = {
        "entity_id": entity_health.entity_id,
        "domain": entity_health.domain,
        "target_fields": [t.field_name for t in entity_health.enrichment_targets[:10]],
        "priority": priority.recommendation,
        "estimated_cost_tokens": priority.estimated_cost_tokens,
        "roi": priority.roi,
    }

    logger.info(
        "Triggering re-enrichment for entity=%s domain=%s recommendation=%s roi=%.1f",
        entity_health.entity_id,
        entity_health.domain,
        priority.recommendation,
        priority.roi,
    )

    return {
        "triggered": True,
        "recommendation": priority.recommendation,
        "priority": priority.model_dump(),
        "enrichment_payload": enrichment_payload,
    }
