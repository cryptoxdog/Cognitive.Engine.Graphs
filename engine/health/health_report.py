"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, services]
tags: [health, report, conversion]
owner: engine-team
status: active
--- /L9_META ---

Health report generation + conversion funnel tracking for Seed→Enrich upsell.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from engine.health.field_health import EntityHealth
from engine.health.health_schemas import (
    TIER_FEATURES,
    ConversionEvent,
    ConversionFunnelMetrics,
    HealthAction,
    HealthReport,
)

logger = logging.getLogger(__name__)

# In-memory conversion event store (replace with persistent store in production)
_conversion_events: list[ConversionEvent] = []


def generate_health_report(
    entity_health: EntityHealth,
    tier: str = "seed",
) -> HealthReport:
    """Generate a structured health report from an EntityHealth assessment."""
    actions = _build_recommended_actions(entity_health, tier)
    upgrade_recs = _build_upgrade_recommendations(entity_health, tier)

    return HealthReport(
        entity_id=entity_health.entity_id,
        domain=entity_health.domain,
        grade=entity_health.grade,
        readiness_score=entity_health.readiness_score,
        gate_completeness=entity_health.gate_completeness,
        scoring_dimension_coverage=entity_health.scoring_dimension_coverage,
        critical_gaps=entity_health.critical_gaps,
        enrichment_targets_count=len(entity_health.enrichment_targets),
        recommended_actions=[a.reason for a in actions],
        upgrade_recommendations=upgrade_recs,
    )


def _build_recommended_actions(
    entity_health: EntityHealth,
    tier: str,
) -> list[HealthAction]:
    """Build actionable recommendations based on health assessment."""
    actions: list[HealthAction] = []
    features = TIER_FEATURES.get(tier, TIER_FEATURES["seed"])

    # Gate-critical gaps are always urgent
    for gap in entity_health.critical_gaps:
        actions.append(
            HealthAction(
                action_type="enrich_field",
                field_name=gap,
                reason=f"Gate-critical field '{gap}' is missing — blocks matching",
                priority="urgent",
                estimated_cost_tokens=800,
            )
        )

    # Enrichment targets for paid tiers
    if features.get("enrichment_targets"):
        for target in entity_health.enrichment_targets[:5]:
            if not target.is_gate_critical:  # Already covered above
                actions.append(
                    HealthAction(
                        action_type="enrich_field",
                        field_name=target.field_name,
                        reason=f"Enriching '{target.field_name}' improves scoring (weight={target.priority_score:.0f})",
                        priority="high" if target.priority_score > 500 else "normal",
                        estimated_cost_tokens=target.estimated_tokens,
                    )
                )

    # Staleness-based refresh recommendations
    stale_fields = [f for f in entity_health.field_health if f.staleness_days is not None and f.staleness_days > 90]
    for field in stale_fields[:3]:
        actions.append(
            HealthAction(
                action_type="refresh_field",
                field_name=field.field_name,
                reason=f"Field '{field.field_name}' is {field.staleness_days} days old — may be outdated",
                priority="normal",
                estimated_cost_tokens=400,
            )
        )

    return actions


def _build_upgrade_recommendations(
    entity_health: EntityHealth,
    tier: str,
) -> list[str]:
    """Build tier upgrade recommendations (Seed→Enrich conversion engine)."""
    recs: list[str] = []

    if tier == "seed":
        if entity_health.critical_gaps:
            recs.append(
                f"Upgrade to Enrich to auto-fill {len(entity_health.critical_gaps)} "
                f"gate-critical gaps blocking your matches"
            )
        if entity_health.enrichment_targets:
            recs.append(
                f"Upgrade to Enrich to see {len(entity_health.enrichment_targets)} "
                f"enrichment opportunities ranked by ROI"
            )
        if entity_health.readiness_score < 70:
            recs.append(
                "Your readiness score is below 70% — Enrich tier customers average 2.3x more matches after enrichment"
            )

    elif tier == "enrich":
        if len(entity_health.enrichment_targets) > 10:
            recs.append("Upgrade to Discover for batch scanning across all entities — find and fix gaps automatically")

    return recs


def track_conversion_event(
    tenant: str,
    entity_id: str,
    event_type: str,
    tier_from: str = "seed",
    tier_to: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ConversionEvent:
    """Track a conversion funnel event."""
    event = ConversionEvent(
        tenant=tenant,
        entity_id=entity_id,
        event_type=event_type,  # type: ignore[arg-type]
        tier_from=tier_from,
        tier_to=tier_to,
        timestamp=datetime.now(UTC),
        metadata=metadata or {},
    )
    _conversion_events.append(event)
    logger.info(
        "Conversion event: tenant=%s entity=%s type=%s",
        tenant,
        entity_id,
        event_type,
    )
    return event


def analyze_conversion_funnel(
    tenant: str | None = None,
) -> ConversionFunnelMetrics:
    """Analyze conversion funnel metrics, optionally filtered by tenant."""
    events = _conversion_events
    if tenant:
        events = [e for e in events if e.tenant == tenant]

    views = sum(1 for e in events if e.event_type == "health_viewed")
    gaps = sum(1 for e in events if e.event_type == "gaps_shown")
    prompts = sum(1 for e in events if e.event_type == "upgrade_prompted")
    clicks = sum(1 for e in events if e.event_type == "upgrade_clicked")
    completions = sum(1 for e in events if e.event_type == "upgrade_completed")

    return ConversionFunnelMetrics(
        total_health_views=views,
        total_gaps_shown=gaps,
        total_upgrade_prompts=prompts,
        total_upgrade_clicks=clicks,
        total_upgrade_completions=completions,
        view_to_prompt_rate=prompts / views if views > 0 else 0.0,
        prompt_to_click_rate=clicks / prompts if prompts > 0 else 0.0,
        click_to_complete_rate=completions / clicks if clicks > 0 else 0.0,
        overall_conversion_rate=completions / views if views > 0 else 0.0,
    )
