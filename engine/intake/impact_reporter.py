"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [intake]
tags: [intake, impact, scoring]
owner: engine-team
status: active
--- /L9_META ---

Impact reporter — scores compiled spec against gates and edge taxonomy.

Maps missing fields to gate blocking severity, counts passable gates
and unlocked edge types, and recommends a delivery tier.
"""

from __future__ import annotations

import structlog

from engine.config.schema import DomainSpec, GateSpec
from engine.intake.intake_schema import CriticalGap, FieldMapping, FieldOrigin, ImpactAnalysis

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Severity classification ────────────────────────────────

_SEVERITY_CRITICAL = "CRITICAL"
_SEVERITY_HIGH = "HIGH"
_SEVERITY_MEDIUM = "MEDIUM"
_SEVERITY_LOW = "LOW"

# ── Gate analysis ──────────────────────────────────────────


def _gate_required_fields(gate: GateSpec) -> set[str]:
    """Extract all property names required by a gate to fire."""
    fields: set[str] = set()
    if gate.candidateprop:
        fields.add(gate.candidateprop)
    if gate.candidateprop_min:
        fields.add(gate.candidateprop_min)
    if gate.candidateprop_max:
        fields.add(gate.candidateprop_max)
    if gate.candidateprop_start:
        fields.add(gate.candidateprop_start)
    if gate.candidateprop_end:
        fields.add(gate.candidateprop_end)
    return fields


def _count_passable_gates(
    gates: list[GateSpec],
    available_fields: set[str],
) -> int:
    """Count gates that can fire with the available fields."""
    passable = 0
    for gate in gates:
        required = _gate_required_fields(gate)
        if required and required.issubset(available_fields):
            passable += 1
        elif not required:
            # Gates with no candidate property requirements always pass
            passable += 1
    return passable


# ── Edge analysis ──────────────────────────────────────────


def _count_unlocked_edges(
    spec: DomainSpec,
    available_fields: set[str],
) -> int:
    """Count edge types that are enabled given available fields."""
    unlocked = 0
    available_nodes: set[str] = set()

    # Determine which nodes have sufficient fields
    for node in spec.ontology.nodes:
        node_fields = {p.name for p in node.properties}
        if node_fields & available_fields:
            available_nodes.add(node.label)

    # An edge is unlocked if both its source and target nodes are available
    for edge in spec.ontology.edges:
        if edge.from_ in available_nodes and edge.to in available_nodes:
            unlocked += 1

    return unlocked


# ── AI-readiness scoring ──────────────────────────────────


def _ai_readiness(
    coverage_pct: float,
    gates_passable: int,
    total_gates: int,
    edges_unlocked: int,
    total_edges: int,
) -> float:
    """
    Compute AI-readiness score (0-10).

    Weighted: 40% coverage + 30% gate ratio + 30% edge ratio.
    """
    coverage_score = (coverage_pct / 100.0) * 10.0
    gate_score = (gates_passable / total_gates * 10.0) if total_gates > 0 else 0.0
    edge_score = (edges_unlocked / total_edges * 10.0) if total_edges > 0 else 0.0
    return round(coverage_score * 0.4 + gate_score * 0.3 + edge_score * 0.3, 1)


# ── Tier recommendation ───────────────────────────────────

_TIER_THRESHOLDS = {
    "autonomous": 90.0,
    "discover": 60.0,
    "enrich": 0.0,
}


def _recommend_tier(coverage_pct: float) -> str:
    """Recommend delivery tier based on coverage."""
    if coverage_pct >= _TIER_THRESHOLDS["autonomous"]:
        return "autonomous"
    if coverage_pct >= _TIER_THRESHOLDS["discover"]:
        return "discover"
    return "enrich"


# ── Critical gap analysis ─────────────────────────────────


def _identify_gaps(
    gates: list[GateSpec],
    available_fields: set[str],
    spec: DomainSpec,
) -> list[CriticalGap]:
    """Identify critical gaps — missing fields that block gates or degrade scoring."""
    gaps: list[CriticalGap] = []

    for gate in gates:
        required = _gate_required_fields(gate)
        missing = required - available_fields
        for field in missing:
            gaps.append(
                CriticalGap(
                    field=field,
                    gate_impact=gate.name,
                    priority=_SEVERITY_CRITICAL,
                    message=f"Field '{field}' required by gate '{gate.name}' ({gate.type.value})",
                )
            )

    # Scoring gaps (HIGH priority)
    for dim in spec.scoring.dimensions:
        if dim.candidateprop and dim.candidateprop not in available_fields:
            gaps.append(
                CriticalGap(
                    field=dim.candidateprop,
                    gate_impact=f"scoring:{dim.name}",
                    priority=_SEVERITY_HIGH,
                    message=f"Scoring dimension '{dim.name}' degraded without '{dim.candidateprop}'",
                )
            )

    return gaps


# ── Public API ─────────────────────────────────────────────


def analyse_impact(
    mappings: list[FieldMapping],
    spec: DomainSpec,
) -> ImpactAnalysis:
    """
    Score compiled mappings against the graph spec gates and edge taxonomy.

    Parameters
    ----------
    mappings:
        All field mappings from the intake compiler.
    spec:
        Target DomainSpec.

    Returns
    -------
    ImpactAnalysis with coverage, gate/edge counts, and tier recommendation.
    """
    total_spec_fields = sum(len(n.properties) for n in spec.ontology.nodes)
    total_gates = len(spec.gates)
    total_edge_types = len(spec.ontology.edges)

    # Current fields (customer_provided only)
    customer_fields = {m.canonical_name for m in mappings if m.origin == FieldOrigin.CUSTOMER_PROVIDED}
    # After enrichment (customer + vertical + enrichable)
    enriched_fields = {
        m.canonical_name
        for m in mappings
        if m.origin
        in (
            FieldOrigin.CUSTOMER_PROVIDED,
            FieldOrigin.VERTICAL_STANDARD,
            FieldOrigin.L9_ENRICHABLE,
        )
    }
    # After discovery (all fields)
    all_fields = {m.canonical_name for m in mappings}
    # Projected discovery: assume 97% coverage for fields in spec
    all_spec_field_names = {p.name for n in spec.ontology.nodes for p in n.properties}
    discovered_fields = all_fields | all_spec_field_names

    # Coverage percentages
    cov_before = (len(customer_fields) / total_spec_fields * 100.0) if total_spec_fields > 0 else 0.0
    cov_enrich = (len(enriched_fields) / total_spec_fields * 100.0) if total_spec_fields > 0 else 0.0
    cov_discover = (len(discovered_fields) / total_spec_fields * 100.0) if total_spec_fields > 0 else 0.0

    # Gate counts
    gates_before = _count_passable_gates(spec.gates, customer_fields)
    gates_after = _count_passable_gates(spec.gates, enriched_fields)

    # Edge counts
    edges_before = _count_unlocked_edges(spec, customer_fields)
    edges_after = _count_unlocked_edges(spec, enriched_fields)

    # AI-readiness
    ai_before = _ai_readiness(cov_before, gates_before, total_gates, edges_before, total_edge_types)
    ai_enrich = _ai_readiness(cov_enrich, gates_after, total_gates, edges_after, total_edge_types)
    ai_discover = _ai_readiness(cov_discover, total_gates, total_gates, total_edge_types, total_edge_types)

    # Gaps
    gaps = _identify_gaps(spec.gates, customer_fields, spec)

    # Tier recommendation based on enriched coverage
    tier = _recommend_tier(cov_enrich)

    logger.info(
        "impact_analysis_complete",
        coverage_before=round(cov_before, 1),
        coverage_after_enrich=round(cov_enrich, 1),
        coverage_after_discover=round(cov_discover, 1),
        gates_before=gates_before,
        gates_after=gates_after,
        tier=tier,
    )

    return ImpactAnalysis(
        current_field_count=len(customer_fields),
        total_spec_fields=total_spec_fields,
        coverage_before=round(cov_before, 2),
        coverage_after_enrich=round(cov_enrich, 2),
        coverage_after_discover=round(min(cov_discover, 100.0), 2),
        ai_readiness_before=ai_before,
        ai_readiness_after_enrich=ai_enrich,
        ai_readiness_after_discover=ai_discover,
        gates_passable_before=gates_before,
        gates_passable_after=gates_after,
        total_gates=total_gates,
        edges_unlocked_before=edges_before,
        edges_unlocked_after=edges_after,
        total_edge_types=total_edge_types,
        critical_gaps=gaps,
        tier_recommendation=tier,
    )


def format_impact_summary(impact: ImpactAnalysis) -> str:
    """Format impact analysis as human-readable summary."""
    lines = [
        f"YOUR CRM TODAY: {impact.current_field_count} fields, "
        f"{impact.coverage_before:.0f}% coverage, "
        f"AI-readiness {impact.ai_readiness_before}/10, "
        f"{impact.gates_passable_before}/{impact.total_gates} gates",
        f"AFTER ENRICH: {impact.coverage_after_enrich:.0f}% coverage, "
        f"{impact.ai_readiness_after_enrich}/10, "
        f"{impact.gates_passable_after}/{impact.total_gates} gates",
        f"WITH DISCOVER: {impact.coverage_after_discover:.0f}% coverage, "
        f"{impact.ai_readiness_after_discover}/10, "
        f"{impact.total_gates}/{impact.total_gates} gates",
    ]
    if impact.coverage_before > 0:
        improvement = impact.coverage_after_discover / impact.coverage_before
        lines[-1] += f", {improvement:.1f}x coverage improvement"
    return "\n".join(lines)
