"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [intake]
tags: [intake, scanner, crm]
owner: engine-team
status: active
--- /L9_META ---

CRM field scanner — maps CRM exports against graph spec node properties.

Accepts raw CRM field names, attempts exact → normalized → fuzzy matching
against the ontology, and returns a ScanResult with coverage breakdown.
"""

from __future__ import annotations

import re

import structlog

from engine.config.schema import DomainSpec, GateSpec, NodeSpec, PropertySpec
from engine.intake.intake_schema import FieldMapping, FieldOrigin, ScanResult

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Normalisation helpers ──────────────────────────────────

_STRIP_RE = re.compile(r"[_\-\s]+")


def _normalise(name: str) -> str:
    """Lowercase and strip underscores/hyphens/spaces for fuzzy comparison."""
    return _STRIP_RE.sub("", name).lower()


def _token_overlap(a: str, b: str) -> float:
    """Token-level Jaccard similarity between two field names."""
    tokens_a = set(re.split(r"[_\-\s]+", a.lower()))
    tokens_b = set(re.split(r"[_\-\s]+", b.lower()))
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ── Gate-critical detection ────────────────────────────────


def _gate_critical_fields(gates: list[GateSpec]) -> set[str]:
    """Extract property names referenced by gates (gate-critical)."""
    critical: set[str] = set()
    for gate in gates:
        if gate.candidateprop:
            critical.add(gate.candidateprop)
        if gate.candidateprop_min:
            critical.add(gate.candidateprop_min)
        if gate.candidateprop_max:
            critical.add(gate.candidateprop_max)
    return critical


def _scoring_weight_map(spec: DomainSpec) -> dict[str, float]:
    """Map property names → scoring weights from scoring dimensions."""
    weights: dict[str, float] = {}
    for dim in spec.scoring.dimensions:
        if dim.candidateprop:
            weights[dim.candidateprop] = dim.defaultweight
    return weights


# ── Public API ─────────────────────────────────────────────


def scan_crm_fields(
    crm_fields: dict[str, str] | list[str],
    spec: DomainSpec,
    *,
    fuzzy_threshold: float = 0.6,
) -> ScanResult:
    """
    Scan CRM fields against the graph spec ontology.

    Parameters
    ----------
    crm_fields:
        Dict of ``{field_name: field_type}`` or list of field names.
    spec:
        Loaded DomainSpec to match against.
    fuzzy_threshold:
        Minimum token-overlap score for fuzzy matching (0-1).

    Returns
    -------
    ScanResult with matched/unmatched/missing breakdowns.
    """
    if isinstance(crm_fields, list):
        crm_fields = dict.fromkeys(crm_fields, "string")

    # Build lookup: canonical_name → (NodeSpec, PropertySpec)
    prop_index: dict[str, tuple[NodeSpec, PropertySpec]] = {}
    norm_index: dict[str, str] = {}  # normalised → canonical

    for node in spec.ontology.nodes:
        for prop in node.properties:
            prop_index[prop.name] = (node, prop)
            norm_index[_normalise(prop.name)] = prop.name

    gate_critical = _gate_critical_fields(spec.gates)
    scoring_weights = _scoring_weight_map(spec)

    matched: list[FieldMapping] = []
    unmatched: list[str] = []
    matched_canonical: set[str] = set()

    for crm_name in crm_fields:
        canonical: str | None = None
        node_label: str = ""

        # 1. Exact match
        if crm_name in prop_index:
            canonical = crm_name
            node_label = prop_index[crm_name][0].label

        # 2. Normalised match
        if canonical is None:
            norm = _normalise(crm_name)
            if norm in norm_index:
                canonical = norm_index[norm]
                node_label = prop_index[canonical][0].label

        # 3. Fuzzy (token overlap)
        if canonical is None:
            best_score = 0.0
            best_name: str | None = None
            for spec_name in prop_index:
                score = _token_overlap(crm_name, spec_name)
                if score > best_score:
                    best_score = score
                    best_name = spec_name
            if best_name is not None and best_score >= fuzzy_threshold:
                canonical = best_name
                node_label = prop_index[best_name][0].label
                logger.info(
                    "fuzzy_match",
                    crm_field=crm_name,
                    canonical=canonical,
                    score=round(best_score, 3),
                )

        if canonical is not None:
            matched.append(
                FieldMapping(
                    crm_field_name=crm_name,
                    canonical_name=canonical,
                    origin=FieldOrigin.CUSTOMER_PROVIDED,
                    node_label=node_label,
                    is_gate_critical=canonical in gate_critical,
                    scoring_weight=scoring_weights.get(canonical, 0.0),
                )
            )
            matched_canonical.add(canonical)
        else:
            unmatched.append(crm_name)

    # Determine missing fields
    all_spec_fields = set(prop_index.keys())
    missing = all_spec_fields - matched_canonical

    missing_critical = sorted(f for f in missing if f in gate_critical)
    missing_scoring = sorted(f for f in missing if f in scoring_weights and f not in gate_critical)

    total_spec = len(all_spec_fields)
    coverage_pct = (len(matched_canonical) / total_spec * 100.0) if total_spec > 0 else 0.0

    logger.info(
        "crm_scan_complete",
        matched=len(matched),
        unmatched=len(unmatched),
        coverage_pct=round(coverage_pct, 1),
    )

    return ScanResult(
        matched=matched,
        unmatched=unmatched,
        missing_critical=missing_critical,
        missing_scoring=missing_scoring,
        coverage_pct=round(coverage_pct, 2),
    )
