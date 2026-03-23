"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, engines]
tags: [health, field-analyzer]
owner: engine-team
status: active
--- /L9_META ---

Analyzes entity fields against domain spec to produce FieldHealth assessments.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from engine.config.schema import DomainSpec, PropertySpec
from engine.health.domain_field_mapper import build_field_map, get_node_definition
from engine.health.field_health import FieldHealth

logger = logging.getLogger(__name__)


def analyze_entity_fields(
    entity: dict[str, Any],
    domain_spec: DomainSpec,
    node_label: str,
    field_confidences: dict[str, float] | None = None,
) -> list[FieldHealth]:
    """Analyze all fields of an entity against the domain spec.

    Returns a FieldHealth for each property defined in the node spec.
    """
    node_def = get_node_definition(domain_spec, node_label)
    field_map = build_field_map(domain_spec, node_label)
    results: list[FieldHealth] = []

    for prop in node_def.properties:
        field_value = entity.get(prop.name)
        confidence = field_confidences.get(prop.name) if field_confidences else None
        meta = field_map.fields.get(prop.name)

        health = FieldHealth(
            field_name=prop.name,
            is_populated=(field_value is not None),
            confidence=confidence,
            staleness_days=compute_staleness(entity, prop.name),
            is_gate_critical=meta.gate_critical if meta else False,
            scoring_weight=meta.scoring_weight if meta else 0.0,
            impact_tier=meta.impact_tier if meta else determine_impact_tier(prop),  # type: ignore[arg-type]
        )
        results.append(health)

    return results


def compute_staleness(entity: dict[str, Any], field_name: str) -> int | None:
    """Compute staleness in days from entity metadata.

    Looks for `_updated_at` or `{field_name}_updated_at` timestamps.
    Returns None if no timestamp metadata is available.
    """
    ts_key = f"{field_name}_updated_at"
    ts_value = entity.get(ts_key) or entity.get("_updated_at")

    if ts_value is None:
        return None

    try:
        if isinstance(ts_value, str):
            updated = datetime.fromisoformat(ts_value)
        elif isinstance(ts_value, (int, float)):
            updated = datetime.fromtimestamp(ts_value, tz=UTC)
        else:
            return None

        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=UTC)

        delta = datetime.now(UTC) - updated
        return max(0, delta.days)
    except (ValueError, OSError):
        return None


def determine_impact_tier(prop: PropertySpec) -> str:
    """Determine impact tier from property spec alone (fallback).

    Returns a value compatible with FieldHealth.impact_tier Literal type.
    """
    if prop.required:
        return "high"
    return "low"
