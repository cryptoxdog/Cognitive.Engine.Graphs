"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [intake]
tags: [intake, schema, pydantic]
owner: engine-team
status: active
--- /L9_META ---

Pydantic models for the intake pipeline.

Defines field mapping, scan results, impact analysis, and the
composite IntakeResult returned by the compiler.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class FieldOrigin(StrEnum):
    """Source provenance for a mapped field."""

    CUSTOMER_PROVIDED = "customer_provided"
    VERTICAL_STANDARD = "vertical_standard"
    L9_DISCOVERED = "l9_discovered"
    L9_ENRICHABLE = "l9_enrichable"


class FieldMapping(BaseModel):
    """Single CRM-to-spec field mapping with provenance metadata."""

    crm_field_name: str
    canonical_name: str
    origin: FieldOrigin
    node_label: str
    is_gate_critical: bool = False
    scoring_weight: float = 0.0
    derived_from: list[str] = Field(default_factory=list)


class ScanResult(BaseModel):
    """Result of scanning CRM fields against the graph spec."""

    matched: list[FieldMapping]
    unmatched: list[str]
    missing_critical: list[str]
    missing_scoring: list[str]
    missing_standard: list[str] = Field(default_factory=list)
    coverage_pct: float


class CriticalGap(BaseModel):
    """A single critical gap blocking a gate or degrading scoring."""

    field: str
    gate_impact: str
    priority: str
    message: str


class ImpactAnalysis(BaseModel):
    """Impact scoring of compiled spec against gates and edge taxonomy."""

    current_field_count: int
    total_spec_fields: int
    coverage_before: float
    coverage_after_enrich: float
    coverage_after_discover: float
    ai_readiness_before: float
    ai_readiness_after_enrich: float
    ai_readiness_after_discover: float
    gates_passable_before: int
    gates_passable_after: int
    total_gates: int
    edges_unlocked_before: int
    edges_unlocked_after: int
    total_edge_types: int
    critical_gaps: list[CriticalGap] = Field(default_factory=list)
    tier_recommendation: str


class IntakeResult(BaseModel):
    """Complete intake pipeline output."""

    scan: ScanResult
    impact: ImpactAnalysis
    domain_spec_yaml: str
    field_origins: dict[str, str]
    delivery_tier: str
