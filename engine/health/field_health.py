"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, models]
tags: [health, field-health, readiness, enrichment]
owner: engine-team
status: active
--- /L9_META ---

Core health models: FieldHealth, ReadinessScore, EnrichmentTarget, EntityHealth,
EnrichmentPriority, MatchQualityDelta.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class FieldHealth(BaseModel):
    """Health assessment for a single entity field."""

    field_name: str
    is_populated: bool
    confidence: float | None = None
    staleness_days: int | None = None
    is_gate_critical: bool = False
    scoring_weight: float = 0.0
    impact_tier: Literal["critical", "high", "medium", "low"] = "low"


class ReadinessScore(BaseModel):
    """Composite readiness score with 60/25/10/5 weighting."""

    overall_score: float  # 0-100
    grade: str  # A-F
    gate_completeness: float
    scoring_dimension_coverage: float
    inference_unlock_potential: float = 0.0
    staleness_penalty: float = 0.0
    blocking_reason: str | None = None
    recommended_action: str | None = None
    blocking_fields: list[str] = []


class EnrichmentTarget(BaseModel):
    """A gap field ranked by enrichment priority."""

    field_name: str
    priority_score: float
    is_gate_critical: bool
    unlocks_rules: list[str] = []
    estimated_tokens: int = 0


class EntityHealth(BaseModel):
    """Full health assessment for a single entity."""

    entity_id: str
    domain: str
    readiness_score: float  # 0-100
    grade: str = "F"
    field_health: list[FieldHealth] = []
    critical_gaps: list[str] = []
    enrichment_targets: list[EnrichmentTarget] = []
    gate_completeness: float = 0.0
    scoring_dimension_coverage: float = 0.0
    inference_unlock_potential: float = 0.0
    recommended_actions: list[str] = []
    next_enrichment_priority: Literal["urgent", "high", "normal", "low"] = "normal"


class EnrichmentPriority(BaseModel):
    """ROI-based enrichment recommendation."""

    priority_score: float  # 0-100
    estimated_cost_tokens: int
    estimated_cost_usd: float
    expected_value_usd: float
    roi: float
    recommendation: Literal["enrich_now", "enrich_low_priority", "skip"]
    reasoning: str = ""


class MatchQualityDelta(BaseModel):
    """Before/after enrichment impact measurement."""

    entity_id: str
    domain: str
    readiness_score_before: float
    readiness_score_after: float
    readiness_improvement: float
    gate_pass_rate_before: float
    gate_pass_rate_after: float
    gate_pass_improvement: float
    avg_match_score_before: float | None = None
    avg_match_score_after: float | None = None
    match_score_improvement: float | None = None
    matches_before_count: int = 0
    matches_after_count: int = 0
    matches_delta: int = 0
    enrichment_cost_usd: float = 0.0
    enrichment_tokens: int = 0
    roi: float | None = None
