"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, schemas]
tags: [health, api, schemas]
owner: engine-team
status: active
--- /L9_META ---

Request/response schemas for HEALTH service API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from engine.health.field_health import EnrichmentPriority, EntityHealth, MatchQualityDelta

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  TIER FEATURES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TIER_FEATURES: dict[str, dict[str, Any]] = {
    "seed": {
        "readiness_score": True,
        "field_gaps": True,
        "enrichment_targets": False,
        "auto_enrich": False,
        "batch_scan": False,
        "conversion_tracking": True,
        "max_entities_per_request": 1,
    },
    "enrich": {
        "readiness_score": True,
        "field_gaps": True,
        "enrichment_targets": True,
        "auto_enrich": True,
        "batch_scan": False,
        "conversion_tracking": False,
        "max_entities_per_request": 10,
    },
    "discover": {
        "readiness_score": True,
        "field_gaps": True,
        "enrichment_targets": True,
        "auto_enrich": True,
        "batch_scan": True,
        "conversion_tracking": False,
        "max_entities_per_request": 100,
    },
    "autonomous": {
        "readiness_score": True,
        "field_gaps": True,
        "enrichment_targets": True,
        "auto_enrich": True,
        "batch_scan": True,
        "conversion_tracking": False,
        "max_entities_per_request": 1000,
    },
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REQUEST SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class HealthAssessmentRequest(BaseModel):
    """Single entity health assessment request."""

    entity_id: str
    domain: str
    node_label: str
    entity_data: dict[str, Any] = Field(default_factory=dict)
    field_confidences: dict[str, float] | None = None
    tier: Literal["seed", "enrich", "discover", "autonomous"] = "seed"


class BatchHealthRequest(BaseModel):
    """Batch health assessment request."""

    domain: str
    tier: Literal["seed", "enrich", "discover", "autonomous"] = "enrich"
    scan_profile: HealthScanProfile | None = None
    cost_ceiling_usd: float = 10.0
    max_entities: int = 100


class HealthScanProfile(BaseModel):
    """Profile for incremental batch scanning."""

    min_staleness_days: int = 30
    max_readiness_score: float = 70.0
    include_failed_matches: bool = True
    include_never_enriched: bool = True
    exclude_entity_ids: list[str] = Field(default_factory=list)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RESPONSE SCHEMAS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class EntityHealthResponse(BaseModel):
    """Full health assessment response."""

    entity_health: EntityHealth
    enrichment_priority: EnrichmentPriority | None = None
    match_quality_delta: MatchQualityDelta | None = None
    tier: str = "seed"
    upgrade_prompt: str | None = None


class HealthReport(BaseModel):
    """Structured health report for an entity."""

    entity_id: str
    domain: str
    grade: str  # A-F
    readiness_score: float
    gate_completeness: float
    scoring_dimension_coverage: float
    critical_gaps: list[str] = []
    enrichment_targets_count: int = 0
    recommended_actions: list[str] = []
    upgrade_recommendations: list[str] = []
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class BatchHealthReport(BaseModel):
    """Batch scan results."""

    domain: str
    total_scanned: int = 0
    total_enriched: int = 0
    total_skipped: int = 0
    cost_usd: float = 0.0
    entities: list[EntityHealthResponse] = []
    scan_profile: HealthScanProfile | None = None


class HealthAction(BaseModel):
    """A recommended action from health assessment."""

    action_type: Literal["enrich_field", "refresh_field", "upgrade_tier", "skip"]
    field_name: str | None = None
    reason: str = ""
    estimated_cost_tokens: int = 0
    priority: Literal["urgent", "high", "normal", "low"] = "normal"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONVERSION TRACKING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ConversionEvent(BaseModel):
    """Tracks Seed→Enrich conversion funnel events."""

    tenant: str
    entity_id: str
    event_type: Literal[
        "health_viewed",
        "gaps_shown",
        "upgrade_prompted",
        "upgrade_clicked",
        "upgrade_completed",
    ]
    tier_from: str = "seed"
    tier_to: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversionFunnelMetrics(BaseModel):
    """Aggregate conversion funnel metrics."""

    total_health_views: int = 0
    total_gaps_shown: int = 0
    total_upgrade_prompts: int = 0
    total_upgrade_clicks: int = 0
    total_upgrade_completions: int = 0
    view_to_prompt_rate: float = 0.0
    prompt_to_click_rate: float = 0.0
    click_to_complete_rate: float = 0.0
    overall_conversion_rate: float = 0.0
