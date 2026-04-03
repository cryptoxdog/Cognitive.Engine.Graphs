"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [intake]
tags: [intake, compiler, yaml]
owner: engine-team
status: active
--- /L9_META ---

Intake compiler — three-source hierarchy → domain_spec.yaml.

Orchestrates CRM scan, vertical discovery, and inference derivation
to produce a compiled domain spec YAML with full field provenance.

Compilation rules (adapted from L9 Spec Compiler):
1. Every field has a source tag and evidence (anti-hallucination).
2. Ambiguous CRM fields get resolved or flagged (anti-vagueness).
3. Every l9_enrichable field MUST have derived_from list.
4. Gate/scoring auto-proposal for categorical and numeric fields.
"""

from __future__ import annotations

import structlog
import yaml

from engine.config.schema import (
    DomainSpec,
    GateType,
    PropertySpec,
    PropertyType,
)
from engine.intake.crm_field_scanner import scan_crm_fields
from engine.intake.intake_schema import (
    FieldMapping,
    FieldOrigin,
    IntakeResult,
    ScanResult,
)
from engine.intake.vertical_discovery import discover_vertical_fields

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Derivation graph ───────────────────────────────────────

# Known inference chains: target field → list of source fields it can be
# derived from. This is a static registry; real derivation uses EIE.
_DERIVATION_GRAPH: dict[str, list[str]] = {
    "credit_score": ["annual_revenue", "years_in_business"],
    "contamination_tolerance": ["process_type", "facility_role"],
    "food_grade_certified": ["certifications", "process_type"],
    "community_id": ["lat", "lon"],
    "transaction_success_rate": ["transaction_count", "success_count"],
    "recency_score": ["last_transaction_date"],
}


# ── Ambiguity detection ───────────────────────────────────

_AMBIGUOUS_PATTERNS: dict[str, list[str]] = {
    "name": ["facility_name", "contact_name", "material_name"],
    "type": ["process_type", "material_type", "facility_type"],
    "id": ["facility_id", "entity_id", "material_id"],
    "status": ["facility_status", "order_status"],
    "date": ["created_date", "last_transaction_date"],
    "score": ["credit_score", "recency_score"],
}


def _check_ambiguous(field_name: str) -> list[str] | None:
    """Return possible resolutions if field name is ambiguous."""
    lower = field_name.lower().strip()
    return _AMBIGUOUS_PATTERNS.get(lower)


# ── Gate/scoring auto-proposal ─────────────────────────────


def _propose_gate_type(prop: PropertySpec) -> GateType | None:
    """Propose a gate type based on property characteristics."""
    if prop.type == PropertyType.BOOL:
        return GateType.BOOLEAN
    if prop.type == PropertyType.ENUM and prop.values:
        return GateType.ENUMMAP
    if prop.type in (PropertyType.FLOAT, PropertyType.INT):
        return GateType.RANGE
    return None


def _propose_scoring(prop: PropertySpec) -> bool:
    """Return True if property is a good scoring candidate."""
    return prop.type in (PropertyType.FLOAT, PropertyType.INT)


# ── Compiler core ──────────────────────────────────────────


def compile_intake(
    crm_fields: dict[str, str] | list[str],
    business_profile: str,
    spec: DomainSpec,
    *,
    domains_dir: str = "domains",
    fuzzy_threshold: float = 0.6,
) -> IntakeResult:
    """
    Compile CRM fields + business profile into domain_spec.yaml.

    Three-source hierarchy:
      Priority 1: CRM scan → customer_provided
      Priority 2: Vertical discovery → vertical_standard
      Priority 3: Inference derivation → l9_enrichable

    Parameters
    ----------
    crm_fields:
        Customer CRM export fields.
    business_profile:
        Free-text business description.
    spec:
        Target DomainSpec to compile against.
    domains_dir:
        Path to domains directory for vertical lookups.
    fuzzy_threshold:
        Minimum score for fuzzy field matching.

    Returns
    -------
    IntakeResult with scan, impact placeholder, YAML, and field origins.
    """
    # Phase 1: CRM scan (customer_provided)
    scan = scan_crm_fields(crm_fields, spec, fuzzy_threshold=fuzzy_threshold)
    field_origins: dict[str, str] = {}
    all_mappings: list[FieldMapping] = list(scan.matched)

    for mapping in scan.matched:
        field_origins[mapping.canonical_name] = FieldOrigin.CUSTOMER_PROVIDED

    matched_names = {m.canonical_name for m in scan.matched}

    # Phase 2: Vertical discovery (vertical_standard)
    vertical = discover_vertical_fields(business_profile, spec=spec, domains_dir=domains_dir)
    vertical_additions: list[FieldMapping] = []
    for field_name in vertical.vertical_fields:
        if field_name not in matched_names:
            # Find the node label for this field
            node_label = _find_node_label(field_name, spec)
            if node_label:
                mapping = FieldMapping(
                    crm_field_name=f"[vertical:{vertical.vertical_name}]",
                    canonical_name=field_name,
                    origin=FieldOrigin.VERTICAL_STANDARD,
                    node_label=node_label,
                )
                vertical_additions.append(mapping)
                field_origins[field_name] = FieldOrigin.VERTICAL_STANDARD
                matched_names.add(field_name)

    all_mappings.extend(vertical_additions)

    # Phase 3: Inference derivation (l9_enrichable)
    enrichable_additions: list[FieldMapping] = []
    for target, sources in _DERIVATION_GRAPH.items():
        if target not in matched_names:
            # Check if all source fields are available
            if all(s in matched_names for s in sources):
                node_label = _find_node_label(target, spec)
                if node_label:
                    mapping = FieldMapping(
                        crm_field_name=f"[derived:{'+'.join(sources)}]",
                        canonical_name=target,
                        origin=FieldOrigin.L9_ENRICHABLE,
                        node_label=node_label,
                        derived_from=sources,
                    )
                    enrichable_additions.append(mapping)
                    field_origins[target] = FieldOrigin.L9_ENRICHABLE
                    matched_names.add(target)

    all_mappings.extend(enrichable_additions)

    # Check for ambiguous CRM fields
    ambiguous_flags: list[str] = []
    for crm_name in crm_fields if isinstance(crm_fields, list) else crm_fields.keys():
        resolutions = _check_ambiguous(crm_name)
        if resolutions:
            ambiguous_flags.append(f"{crm_name} → {resolutions}")
            logger.warning(
                "ambiguous_field",
                crm_field=crm_name,
                possible_resolutions=resolutions,
            )

    # Validate l9_enrichable fields have derived_from
    for mapping in enrichable_additions:
        if not mapping.derived_from:
            logger.error(
                "enrichable_without_derivation",
                field=mapping.canonical_name,
            )

    # Auto-propose gates and scoring
    gate_proposals: list[dict[str, str]] = []
    scoring_proposals: list[str] = []
    for mapping in all_mappings:
        prop = _find_property(mapping.canonical_name, spec)
        if prop:
            gate_type = _propose_gate_type(prop)
            if gate_type and not mapping.is_gate_critical:
                gate_proposals.append({"field": mapping.canonical_name, "gate_type": gate_type.value})
            if _propose_scoring(prop) and mapping.scoring_weight == 0.0:
                scoring_proposals.append(mapping.canonical_name)

    # Build YAML output
    domain_yaml = _build_domain_yaml(all_mappings, spec, gate_proposals, scoring_proposals)

    # Build scan with updated missing_standard
    updated_scan = ScanResult(
        matched=scan.matched,
        unmatched=scan.unmatched,
        missing_critical=scan.missing_critical,
        missing_scoring=scan.missing_scoring,
        missing_standard=[f for f in vertical.vertical_fields if f not in {m.canonical_name for m in scan.matched}]
        if not vertical.discovery_suggested
        else [],
        coverage_pct=scan.coverage_pct,
    )

    logger.info(
        "intake_compiled",
        customer_fields=len(scan.matched),
        vertical_fields=len(vertical_additions),
        enrichable_fields=len(enrichable_additions),
        total_coverage=len(matched_names),
        ambiguous=len(ambiguous_flags),
    )

    # Import here to avoid circular — impact_reporter uses IntakeResult indirectly
    from engine.intake.impact_reporter import analyse_impact

    impact = analyse_impact(all_mappings, spec)

    return IntakeResult(
        scan=updated_scan,
        impact=impact,
        domain_spec_yaml=domain_yaml,
        field_origins=field_origins,
        delivery_tier=impact.tier_recommendation,
    )


# ── Helpers ────────────────────────────────────────────────


def _find_node_label(field_name: str, spec: DomainSpec) -> str | None:
    """Find which node label owns a property."""
    for node in spec.ontology.nodes:
        for prop in node.properties:
            if prop.name == field_name:
                return node.label
    return None


def _find_property(field_name: str, spec: DomainSpec) -> PropertySpec | None:
    """Find a PropertySpec by name across all nodes."""
    for node in spec.ontology.nodes:
        for prop in node.properties:
            if prop.name == field_name:
                return prop
    return None


def _build_domain_yaml(
    mappings: list[FieldMapping],
    spec: DomainSpec,
    gate_proposals: list[dict[str, str]],
    scoring_proposals: list[str],
) -> str:
    """Build a domain spec YAML string from compiled mappings."""
    nodes_by_label: dict[str, list[dict[str, object]]] = {}
    for mapping in mappings:
        label = mapping.node_label
        if label not in nodes_by_label:
            nodes_by_label[label] = []
        entry: dict[str, object] = {
            "name": mapping.canonical_name,
            "origin": mapping.origin.value,
        }
        if mapping.derived_from:
            entry["derived_from"] = mapping.derived_from
        if mapping.is_gate_critical:
            entry["gate_critical"] = True
        if mapping.scoring_weight > 0:
            entry["scoring_weight"] = mapping.scoring_weight
        nodes_by_label[label].append(entry)

    output: dict[str, object] = {
        "domain": {
            "id": spec.domain.id,
            "name": spec.domain.name,
            "version": spec.domain.version,
        },
        "intake_compilation": {
            "nodes": {label: {"fields": fields} for label, fields in nodes_by_label.items()},
        },
    }

    if gate_proposals:
        output["gate_proposals"] = gate_proposals
    if scoring_proposals:
        output["scoring_proposals"] = scoring_proposals

    return yaml.dump(output, default_flow_style=False, sort_keys=False)
