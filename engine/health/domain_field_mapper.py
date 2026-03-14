"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [health, services]
tags: [health, domain-mapper, field-metadata]
owner: engine-team
status: active
--- /L9_META ---

Maps domain YAML ontology properties to FieldHealth metadata.
Extracts gate_critical, scoring_weight, required from property definitions
and domain-level gates/scoring configuration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from engine.config.schema import DomainSpec, NodeSpec

logger = logging.getLogger(__name__)


@dataclass
class FieldMetadata:
    """Enriched metadata for a single field derived from domain spec."""

    name: str
    required: bool = False
    gate_critical: bool = False
    scoring_weight: float = 0.0
    impact_tier: str = "low"


@dataclass
class DomainFieldMap:
    """Structured mapping of all fields for a node label within a domain."""

    domain_id: str
    node_label: str
    fields: dict[str, FieldMetadata] = field(default_factory=dict)
    inference_rules: list[dict[str, Any]] = field(default_factory=list)


def get_node_definition(domain_spec: DomainSpec, node_label: str) -> NodeSpec:
    """Resolve a NodeSpec by label from the domain ontology."""
    for node in domain_spec.ontology.nodes:
        if node.label == node_label:
            return node
    msg = f"Node label '{node_label}' not found in domain '{domain_spec.domain.id}'"
    raise ValueError(msg)


def build_field_map(domain_spec: DomainSpec, node_label: str) -> DomainFieldMap:
    """Build a DomainFieldMap by cross-referencing ontology, gates, and scoring."""
    node_def = get_node_definition(domain_spec, node_label)

    # Collect gate-critical fields from domain gates
    gate_critical_fields: set[str] = set()
    for gate in domain_spec.gates:
        if gate.candidateprop:
            gate_critical_fields.add(gate.candidateprop)

    # Collect scoring weights from domain scoring dimensions
    scoring_weights: dict[str, float] = {}
    if domain_spec.scoring and domain_spec.scoring.dimensions:
        for dim in domain_spec.scoring.dimensions:
            prop_name = dim.candidateprop or ""
            if prop_name:
                scoring_weights[prop_name] = dim.defaultweight

    field_map = DomainFieldMap(
        domain_id=domain_spec.domain.id,
        node_label=node_label,
    )

    for prop in node_def.properties:
        is_gate = prop.name in gate_critical_fields
        weight = scoring_weights.get(prop.name, 0.0)
        tier = _compute_impact_tier(is_gate, weight, prop.required)

        field_map.fields[prop.name] = FieldMetadata(
            name=prop.name,
            required=prop.required,
            gate_critical=is_gate,
            scoring_weight=weight,
            impact_tier=tier,
        )

    # Load inference rules if plugins.inference_rules exists
    field_map.inference_rules = _extract_inference_rules(domain_spec)

    return field_map


def _compute_impact_tier(is_gate: bool, scoring_weight: float, required: bool) -> str:
    """Determine impact tier from field characteristics."""
    if is_gate:
        return "critical"
    if scoring_weight >= 0.15:
        return "high"
    if scoring_weight > 0 or required:
        return "medium"
    return "low"


def _extract_inference_rules(domain_spec: DomainSpec) -> list[dict[str, Any]]:
    """Extract inference rules from domain spec plugins if defined."""
    if not domain_spec.plugins:
        return []
    # Inference rules may be stored in plugins as custom config
    plugins_dict = domain_spec.plugins.model_dump() if hasattr(domain_spec.plugins, "model_dump") else {}
    result: list[dict[str, Any]] = plugins_dict.get("inference_rules", [])
    return result
