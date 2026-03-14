"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, jobs]
tags: [health, nightly-scan, batch, incremental]
owner: engine-team
status: active
--- /L9_META ---

Nightly incremental health scan job.
Profile-based entity selection, cost ceiling enforcement,
ROI-sorted enrichment queue (top 100).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from engine.config.loader import DomainPackLoader
from engine.health.domain_field_mapper import build_field_map
from engine.health.enrichment_trigger import compute_enrichment_priority
from engine.health.field_analyzer import analyze_entity_fields
from engine.health.field_health import EntityHealth
from engine.health.gap_prioritizer import prioritize_gaps_v2
from engine.health.health_schemas import HealthScanProfile
from engine.health.readiness_scorer import compute_readiness_score_v2

logger = logging.getLogger(__name__)

# Track scanned entities to prevent re-scan within same run
_scanned_this_run: set[str] = set()

# Default cost ceiling per nightly run (USD)
DEFAULT_COST_CEILING_USD = 50.0

# Maximum entities to enrich per run
MAX_ENRICHMENT_QUEUE = 100


async def run_nightly_health_scan(
    domain: str,
    scan_profile: HealthScanProfile | None = None,
    cost_ceiling_usd: float = DEFAULT_COST_CEILING_USD,
    entity_loader: Any | None = None,
) -> dict[str, Any]:
    """Run incremental nightly health scan for a domain.

    Selection profile (delta-based targeting):
      - Entities not scanned in last N days (staleness)
      - Entities with readiness < threshold
      - Entities with recent failed matches
      - Entities never enriched

    Produces ROI-sorted enrichment queue (top 100).
    Enforces cost ceiling.
    """
    _scanned_this_run.clear()
    profile = scan_profile or HealthScanProfile()

    domain_loader = DomainPackLoader()
    domain_spec = domain_loader.load_domain(domain)

    # Load candidate entities — in production, query Neo4j with profile filters
    entities = await _load_candidate_entities(
        domain=domain,
        profile=profile,
        entity_loader=entity_loader,
    )

    logger.info(
        "Nightly scan: domain=%s candidates=%d ceiling=$%.2f",
        domain,
        len(entities),
        cost_ceiling_usd,
    )

    # Assess all candidates
    assessments: list[tuple[EntityHealth, float]] = []  # (health, priority_score)

    for entity_data in entities:
        entity_id = entity_data.get("entity_id", "unknown")

        if entity_id in _scanned_this_run:
            continue
        if entity_id in profile.exclude_entity_ids:
            continue

        _scanned_this_run.add(entity_id)
        node_label = entity_data.get("node_label", "")

        try:
            field_health = analyze_entity_fields(
                entity=entity_data.get("data", {}),
                domain_spec=domain_spec,
                node_label=node_label,
            )
            readiness = compute_readiness_score_v2(field_health, domain_spec)
            field_map = build_field_map(domain_spec, node_label)
            enrichment_targets = prioritize_gaps_v2(
                field_health, domain_spec, inference_rules=field_map.inference_rules
            )

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
            assessments.append((entity_health, priority.priority_score))

        except Exception:
            logger.exception("Failed to assess entity %s", entity_id)
            continue

    # Sort by ROI priority (highest first)
    assessments.sort(key=lambda x: x[1], reverse=True)

    # Build enrichment queue with cost ceiling
    enrichment_queue: list[dict[str, Any]] = []
    total_cost = 0.0
    total_enriched = 0
    total_skipped = 0

    for entity_health, priority_score in assessments[:MAX_ENRICHMENT_QUEUE]:
        priority = compute_enrichment_priority(entity_health, domain_spec)

        if priority.recommendation == "skip":
            total_skipped += 1
            continue

        if total_cost + priority.estimated_cost_usd > cost_ceiling_usd:
            total_skipped += len(assessments) - total_enriched - total_skipped
            logger.info(
                "Cost ceiling reached: $%.2f / $%.2f",
                total_cost,
                cost_ceiling_usd,
            )
            break

        enrichment_queue.append(
            {
                "entity_id": entity_health.entity_id,
                "domain": entity_health.domain,
                "readiness_score": entity_health.readiness_score,
                "grade": entity_health.grade,
                "priority_score": priority_score,
                "estimated_cost_usd": priority.estimated_cost_usd,
                "recommendation": priority.recommendation,
                "critical_gaps": entity_health.critical_gaps,
                "target_fields": [t.field_name for t in entity_health.enrichment_targets[:10]],
            }
        )

        total_cost += priority.estimated_cost_usd
        total_enriched += 1

    scan_result = {
        "domain": domain,
        "scan_timestamp": datetime.now(UTC).isoformat(),
        "total_candidates": len(entities),
        "total_assessed": len(assessments),
        "total_enriched": total_enriched,
        "total_skipped": total_skipped,
        "total_cost_usd": round(total_cost, 2),
        "cost_ceiling_usd": cost_ceiling_usd,
        "enrichment_queue": enrichment_queue,
    }

    logger.info(
        "Nightly scan complete: assessed=%d enrich=%d skip=%d cost=$%.2f",
        len(assessments),
        total_enriched,
        total_skipped,
        total_cost,
    )

    return scan_result


async def _load_candidate_entities(
    domain: str,
    profile: HealthScanProfile,
    entity_loader: Any | None = None,
) -> list[dict[str, Any]]:
    """Load candidate entities for health scanning.

    In production, this queries Neo4j with filters:
      - staleness > profile.min_staleness_days
      - readiness < profile.max_readiness_score
      - recent failed matches (if profile.include_failed_matches)
      - never enriched (if profile.include_never_enriched)

    For now, delegates to optional entity_loader callback.
    """
    if entity_loader and callable(entity_loader):
        result: list[dict[str, Any]] = await entity_loader(domain, profile)
        return result

    logger.warning(
        "No entity_loader provided for domain=%s — returning empty candidate list",
        domain,
    )
    return []
