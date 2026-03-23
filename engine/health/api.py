"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, api]
tags: [health, api, endpoints]
owner: engine-team
status: active
--- /L9_META ---

HEALTH service API handler — integrates with chassis action routing.
Three logical endpoints routed via payload["sub_action"]:
  - assess      → single entity health assessment (tier-gated)
  - batch_assess → incremental batch scan with cost ceilings
  - report      → health report for an entity (Seed trojan horse)
"""

from __future__ import annotations

import logging
from typing import Any

from engine.config.loader import DomainPackLoader
from engine.health.domain_field_mapper import build_field_map
from engine.health.enrichment_trigger import compute_enrichment_priority, trigger_reenrichment_v2
from engine.health.field_analyzer import analyze_entity_fields
from engine.health.field_health import EntityHealth
from engine.health.gap_prioritizer import prioritize_gaps_v2
from engine.health.health_report import generate_health_report, track_conversion_event
from engine.health.health_schemas import (
    TIER_FEATURES,
    BatchHealthReport,
    EntityHealthResponse,
    HealthAssessmentRequest,
    HealthScanProfile,
)
from engine.health.readiness_scorer import compute_readiness_score_v2

logger = logging.getLogger(__name__)

# Module-level domain loader (initialized lazily)
_domain_loader: DomainPackLoader | None = None


def _get_domain_loader() -> DomainPackLoader:
    """Lazy-init domain loader."""
    global _domain_loader
    if _domain_loader is None:
        _domain_loader = DomainPackLoader()
    return _domain_loader


async def handle_health_assess(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST /assess — Single entity health assessment.

    Tier-gated: Seed gets score + gaps, Enrich+ gets enrichment targets + auto-enrich.
    Tracks conversion events for Seed tier.
    """
    request = HealthAssessmentRequest(**payload)
    tier = request.tier
    features = TIER_FEATURES.get(tier, TIER_FEATURES["seed"])

    domain_spec = _get_domain_loader().load_domain(request.domain)

    # Analyze fields
    field_health = analyze_entity_fields(
        entity=request.entity_data,
        domain_spec=domain_spec,
        node_label=request.node_label,
        field_confidences=request.field_confidences,
    )

    # Compute readiness score
    readiness = compute_readiness_score_v2(field_health, domain_spec)

    # Build field map for inference rules
    field_map = build_field_map(domain_spec, request.node_label)

    # Prioritize gaps
    enrichment_targets = prioritize_gaps_v2(field_health, domain_spec, inference_rules=field_map.inference_rules)

    # Build EntityHealth
    critical_gaps = [f.field_name for f in field_health if f.is_gate_critical and not f.is_populated]
    entity_health = EntityHealth(
        entity_id=request.entity_id,
        domain=request.domain,
        readiness_score=readiness.overall_score,
        grade=readiness.grade,
        field_health=field_health,
        critical_gaps=critical_gaps,
        enrichment_targets=enrichment_targets if features.get("enrichment_targets") else [],
        gate_completeness=readiness.gate_completeness,
        scoring_dimension_coverage=readiness.scoring_dimension_coverage,
        inference_unlock_potential=readiness.inference_unlock_potential,
        recommended_actions=_build_action_strings(critical_gaps, tier),
        next_enrichment_priority=_classify_priority(readiness.overall_score),  # type: ignore[arg-type]
    )

    # Enrichment priority for paid tiers
    enrichment_priority = None
    if features.get("enrichment_targets"):
        enrichment_priority = compute_enrichment_priority(entity_health, domain_spec)

    # Auto-enrich for paid tiers
    if features.get("auto_enrich") and enrichment_priority and enrichment_priority.recommendation == "enrich_now":
        await trigger_reenrichment_v2(entity_health, domain_spec, tenant)

    # Conversion tracking for Seed
    upgrade_prompt = None
    if tier == "seed" and features.get("conversion_tracking"):
        track_conversion_event(tenant, request.entity_id, "health_viewed")
        if critical_gaps:
            track_conversion_event(tenant, request.entity_id, "gaps_shown")
            upgrade_prompt = (
                f"You have {len(critical_gaps)} gate-critical gaps blocking matches. "
                f"Upgrade to Enrich to auto-fill them and unlock {len(enrichment_targets)} "
                f"enrichment opportunities."
            )
            track_conversion_event(
                tenant,
                request.entity_id,
                "upgrade_prompted",
                metadata={"gaps": len(critical_gaps), "targets": len(enrichment_targets)},
            )

    response = EntityHealthResponse(
        entity_health=entity_health,
        enrichment_priority=enrichment_priority,
        tier=tier,
        upgrade_prompt=upgrade_prompt,
    )

    return response.model_dump()


async def handle_health_batch_assess(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST /batch-assess — Incremental batch scan with cost ceilings.

    Uses HealthScanProfile for delta-based targeting.
    """
    domain = payload.get("domain", tenant)
    tier = payload.get("tier", "enrich")
    features = TIER_FEATURES.get(tier, TIER_FEATURES["seed"])

    if not features.get("batch_scan"):
        return {"error": "Batch scan requires Discover tier or above", "tier": tier}

    cost_ceiling = payload.get("cost_ceiling_usd", 10.0)
    max_entities = payload.get("max_entities", 100)
    profile_data = payload.get("scan_profile")
    scan_profile = HealthScanProfile(**profile_data) if profile_data else HealthScanProfile()

    domain_spec = _get_domain_loader().load_domain(domain)

    # In production, entity_ids would come from Neo4j query filtered by scan_profile.
    # For now, process entities provided in payload.
    entities: list[dict[str, Any]] = payload.get("entities", [])
    results: list[EntityHealthResponse] = []
    total_cost = 0.0
    total_enriched = 0
    total_skipped = 0

    for entity_data in entities[:max_entities]:
        if total_cost >= cost_ceiling:
            total_skipped += len(entities) - len(results)
            break

        entity_id = entity_data.get("entity_id", "unknown")
        node_label = entity_data.get("node_label", "")

        field_health = analyze_entity_fields(
            entity=entity_data.get("data", {}),
            domain_spec=domain_spec,
            node_label=node_label,
        )
        readiness = compute_readiness_score_v2(field_health, domain_spec)
        field_map = build_field_map(domain_spec, node_label)
        enrichment_targets = prioritize_gaps_v2(field_health, domain_spec, inference_rules=field_map.inference_rules)

        critical_gaps = [f.field_name for f in field_health if f.is_gate_critical and not f.is_populated]
        entity_health = EntityHealth(
            entity_id=entity_id,
            domain=domain,
            readiness_score=readiness.overall_score,
            grade=readiness.grade,
            field_health=field_health,
            critical_gaps=critical_gaps,
            enrichment_targets=enrichment_targets,
            gate_completeness=readiness.gate_completeness,
            scoring_dimension_coverage=readiness.scoring_dimension_coverage,
        )

        priority = compute_enrichment_priority(entity_health, domain_spec)

        if priority.recommendation != "skip":
            total_cost += priority.estimated_cost_usd
            total_enriched += 1
        else:
            total_skipped += 1

        results.append(
            EntityHealthResponse(
                entity_health=entity_health,
                enrichment_priority=priority,
                tier=tier,
            )
        )

    report = BatchHealthReport(
        domain=domain,
        total_scanned=len(results),
        total_enriched=total_enriched,
        total_skipped=total_skipped,
        cost_usd=total_cost,
        entities=results,
        scan_profile=scan_profile,
    )

    return report.model_dump()


async def handle_health_report(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    """GET /report/{entity_id} — Seed tier trojan horse.

    Shows the full health report with upgrade prompts to drive conversion.
    """
    entity_id = payload.get("entity_id", "")
    domain = payload.get("domain", tenant)
    tier = payload.get("tier", "seed")

    domain_spec = _get_domain_loader().load_domain(domain)

    entity_data = payload.get("entity_data", {})
    node_label = payload.get("node_label", "")

    field_health = analyze_entity_fields(
        entity=entity_data,
        domain_spec=domain_spec,
        node_label=node_label,
    )
    readiness = compute_readiness_score_v2(field_health, domain_spec)
    field_map = build_field_map(domain_spec, node_label)
    enrichment_targets = prioritize_gaps_v2(field_health, domain_spec, inference_rules=field_map.inference_rules)

    critical_gaps = [f.field_name for f in field_health if f.is_gate_critical and not f.is_populated]
    entity_health = EntityHealth(
        entity_id=entity_id,
        domain=domain,
        readiness_score=readiness.overall_score,
        grade=readiness.grade,
        field_health=field_health,
        critical_gaps=critical_gaps,
        enrichment_targets=enrichment_targets,
        gate_completeness=readiness.gate_completeness,
        scoring_dimension_coverage=readiness.scoring_dimension_coverage,
    )

    report = generate_health_report(entity_health, tier=tier)

    # Track conversion
    if tier == "seed":
        track_conversion_event(tenant, entity_id, "health_viewed")
        if critical_gaps:
            track_conversion_event(tenant, entity_id, "gaps_shown")
            track_conversion_event(tenant, entity_id, "upgrade_prompted")

    return report.model_dump()


def _build_action_strings(critical_gaps: list[str], tier: str) -> list[str]:
    """Build human-readable action strings."""
    actions: list[str] = []
    if critical_gaps:
        actions.append(f"Fill {len(critical_gaps)} gate-critical fields: {', '.join(critical_gaps[:5])}")
    if tier == "seed":
        actions.append("Upgrade to Enrich tier for automated gap filling")
    return actions


def _classify_priority(readiness_score: float) -> str:
    """Classify enrichment priority from readiness score."""
    if readiness_score < 30:
        return "urgent"
    if readiness_score < 50:
        return "high"
    if readiness_score < 70:
        return "normal"
    return "low"
