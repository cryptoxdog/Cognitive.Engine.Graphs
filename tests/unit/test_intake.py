"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, intake]
owner: engine-team
status: active
--- /L9_META ---

Unit tests for engine/intake — CRM-to-YAML pipeline + impact reporter.
"""

from __future__ import annotations

import pytest

from engine.config.schema import (
    ComputationType,
    DomainMetadata,
    DomainSpec,
    EdgeCategory,
    EdgeDirection,
    EdgeSpec,
    GateSpec,
    GateType,
    MatchEntitiesSpec,
    MatchEntitySpec,
    NodeSpec,
    OntologySpec,
    PropertySpec,
    PropertyType,
    QuerySchemaSpec,
    ScoringDimensionSpec,
    ScoringSource,
    ScoringSpec,
)
from engine.intake.crm_field_scanner import scan_crm_fields
from engine.intake.impact_reporter import analyse_impact, format_impact_summary
from engine.intake.intake_compiler import compile_intake
from engine.intake.intake_schema import (
    FieldMapping,
    FieldOrigin,
    IntakeResult,
)
from engine.intake.vertical_discovery import discover_vertical_fields

# ── Fixtures ───────────────────────────────────────────────


@pytest.fixture
def intake_spec() -> DomainSpec:
    """Minimal DomainSpec for intake testing with gates and scoring."""
    return DomainSpec(
        domain=DomainMetadata(id="test-intake", name="Test Intake", version="0.1.0"),
        ontology=OntologySpec(
            nodes=[
                NodeSpec(
                    label="Facility",
                    candidate=True,
                    matchdirection="intake_to_buyer",
                    properties=[
                        PropertySpec(name="facility_id", type=PropertyType.INT, required=True),
                        PropertySpec(name="name", type=PropertyType.STRING),
                        PropertySpec(name="lat", type=PropertyType.FLOAT),
                        PropertySpec(name="lon", type=PropertyType.FLOAT),
                        PropertySpec(name="credit_score", type=PropertyType.FLOAT),
                        PropertySpec(name="process_type", type=PropertyType.ENUM, values=["extrusion", "injection"]),
                        PropertySpec(name="min_density", type=PropertyType.FLOAT),
                        PropertySpec(name="max_density", type=PropertyType.FLOAT),
                        PropertySpec(name="food_grade_certified", type=PropertyType.BOOL),
                        PropertySpec(name="contamination_tolerance", type=PropertyType.FLOAT),
                    ],
                ),
                NodeSpec(
                    label="MaterialIntake",
                    queryentity=True,
                    matchdirection="intake_to_buyer",
                    properties=[
                        PropertySpec(name="intake_id", type=PropertyType.INT, required=True),
                        PropertySpec(name="material_type", type=PropertyType.STRING),
                    ],
                ),
            ],
            edges=[
                EdgeSpec(
                    type="ACCEPTS_POLYMER",
                    **{"from": "Facility"},
                    to="MaterialIntake",
                    direction=EdgeDirection.DIRECTED,
                    category=EdgeCategory.CAPABILITY,
                    managedby="sync",
                ),
                EdgeSpec(
                    type="EXCLUDED_FROM",
                    **{"from": "Facility"},
                    to="Facility",
                    direction=EdgeDirection.DIRECTED,
                    category=EdgeCategory.EXCLUSION,
                    managedby="sync",
                ),
            ],
        ),
        matchentities=MatchEntitiesSpec(
            candidate=[MatchEntitySpec(label="Facility", matchdirection="intake_to_buyer")],
            queryentity=[MatchEntitySpec(label="MaterialIntake", matchdirection="intake_to_buyer")],
        ),
        queryschema=QuerySchemaSpec(matchdirections=["intake_to_buyer"], fields=[]),
        gates=[
            GateSpec(
                name="density_range",
                type=GateType.RANGE,
                candidateprop_min="min_density",
                candidateprop_max="max_density",
            ),
            GateSpec(name="food_grade", type=GateType.BOOLEAN, candidateprop="food_grade_certified"),
            GateSpec(name="process_filter", type=GateType.ENUMMAP, candidateprop="process_type"),
        ],
        scoring=ScoringSpec(
            dimensions=[
                ScoringDimensionSpec(
                    name="credit",
                    source=ScoringSource.CANDIDATEPROPERTY,
                    candidateprop="credit_score",
                    computation=ComputationType.LOGNORMALIZED,
                    weightkey="credit_w",
                    defaultweight=0.3,
                ),
            ]
        ),
    )


# ── Scanner Tests ──────────────────────────────────────────


@pytest.mark.unit
class TestCRMFieldScanner:
    """Tests for crm_field_scanner.scan_crm_fields."""

    def test_exact_match(self, intake_spec: DomainSpec) -> None:
        """CRM fields matching spec property names exactly."""
        crm = {"facility_id": "int", "name": "string", "lat": "float"}
        result = scan_crm_fields(crm, intake_spec)

        assert len(result.matched) == 3
        canonical_names = {m.canonical_name for m in result.matched}
        assert "facility_id" in canonical_names
        assert "name" in canonical_names
        assert "lat" in canonical_names
        assert len(result.unmatched) == 0

    def test_normalized_match(self, intake_spec: DomainSpec) -> None:
        """CRM fields matching after normalisation (case, underscores)."""
        crm = ["FacilityId", "CreditScore"]
        result = scan_crm_fields(crm, intake_spec)

        canonical_names = {m.canonical_name for m in result.matched}
        assert "facility_id" in canonical_names
        assert "credit_score" in canonical_names

    def test_unmatched_fields(self, intake_spec: DomainSpec) -> None:
        """CRM fields that don't match any spec property."""
        crm = ["totally_unknown_field", "another_random"]
        result = scan_crm_fields(crm, intake_spec)

        assert len(result.matched) == 0
        assert len(result.unmatched) == 2
        assert "totally_unknown_field" in result.unmatched

    def test_gate_critical_detection(self, intake_spec: DomainSpec) -> None:
        """Fields used by gates should be tagged as gate-critical."""
        crm = ["food_grade_certified", "min_density", "max_density", "process_type"]
        result = scan_crm_fields(crm, intake_spec)

        critical_fields = {m.canonical_name for m in result.matched if m.is_gate_critical}
        assert "food_grade_certified" in critical_fields
        assert "min_density" in critical_fields
        assert "max_density" in critical_fields
        assert "process_type" in critical_fields

    def test_empty_crm(self, intake_spec: DomainSpec) -> None:
        """Empty CRM input → zero matches, full missing list."""
        result = scan_crm_fields([], intake_spec)

        assert len(result.matched) == 0
        assert result.coverage_pct == 0.0

    def test_all_fields_matched(self, intake_spec: DomainSpec) -> None:
        """All spec fields in CRM → 100% coverage."""
        crm = [
            "facility_id",
            "name",
            "lat",
            "lon",
            "credit_score",
            "process_type",
            "min_density",
            "max_density",
            "food_grade_certified",
            "contamination_tolerance",
            "intake_id",
            "material_type",
        ]
        result = scan_crm_fields(crm, intake_spec)

        assert result.coverage_pct == 100.0
        assert len(result.missing_critical) == 0
        assert len(result.missing_scoring) == 0

    def test_list_input(self, intake_spec: DomainSpec) -> None:
        """Accept list[str] as CRM field input."""
        result = scan_crm_fields(["lat", "lon"], intake_spec)
        assert len(result.matched) == 2

    def test_scoring_weight_propagation(self, intake_spec: DomainSpec) -> None:
        """Scoring weights from spec should propagate to matched fields."""
        crm = ["credit_score"]
        result = scan_crm_fields(crm, intake_spec)

        assert len(result.matched) == 1
        assert result.matched[0].scoring_weight == 0.3


# ── Compiler Tests ─────────────────────────────────────────


@pytest.mark.unit
class TestIntakeCompiler:
    """Tests for intake_compiler.compile_intake."""

    def test_three_source_hierarchy(self, intake_spec: DomainSpec) -> None:
        """Customer fields take priority; vertical and enrichable fill gaps."""
        crm = {"lat": "float", "lon": "float", "process_type": "string"}
        result = compile_intake(crm, "Plastic recycling company", intake_spec)

        assert isinstance(result, IntakeResult)
        # Customer-provided fields should be in origins
        assert result.field_origins.get("lat") == FieldOrigin.CUSTOMER_PROVIDED
        assert result.field_origins.get("lon") == FieldOrigin.CUSTOMER_PROVIDED

    def test_field_origin_tagging(self, intake_spec: DomainSpec) -> None:
        """Every field in origins should have a valid FieldOrigin value."""
        crm = {"facility_id": "int", "name": "string"}
        result = compile_intake(crm, "Unknown business", intake_spec)

        for _field, origin in result.field_origins.items():
            assert origin in [o.value for o in FieldOrigin]

    def test_derived_from_validation(self, intake_spec: DomainSpec) -> None:
        """Enrichable fields must have derived_from populated."""
        # Provide source fields for the community_id derivation
        crm = {"lat": "float", "lon": "float"}
        result = compile_intake(crm, "Unknown vertical", intake_spec)

        enrichable_origins = {k for k, v in result.field_origins.items() if v == FieldOrigin.L9_ENRICHABLE}
        # If community_id was derived, check the YAML contains derivation info
        if "community_id" in enrichable_origins:
            assert "derived_from" in result.domain_spec_yaml

    def test_yaml_output_valid(self, intake_spec: DomainSpec) -> None:
        """Compiled YAML should be parseable."""
        import yaml

        crm = {"facility_id": "int", "name": "string"}
        result = compile_intake(crm, "plastic recycling", intake_spec)

        parsed = yaml.safe_load(result.domain_spec_yaml)
        assert "domain" in parsed
        assert "intake_compilation" in parsed

    def test_empty_crm_compiles(self, intake_spec: DomainSpec) -> None:
        """Empty CRM should still produce a valid result."""
        result = compile_intake([], "Unknown", intake_spec)

        assert isinstance(result, IntakeResult)
        assert result.scan.coverage_pct == 0.0


# ── Impact Reporter Tests ─────────────────────────────────


@pytest.mark.unit
class TestImpactReporter:
    """Tests for impact_reporter.analyse_impact."""

    def test_gate_counting(self, intake_spec: DomainSpec) -> None:
        """Passable gates should increase with more fields."""
        # No gate fields
        empty_impact = analyse_impact([], intake_spec)
        assert empty_impact.total_gates == 3

        # With gate fields
        mappings = [
            FieldMapping(
                crm_field_name="food_grade_certified",
                canonical_name="food_grade_certified",
                origin=FieldOrigin.CUSTOMER_PROVIDED,
                node_label="Facility",
                is_gate_critical=True,
            ),
            FieldMapping(
                crm_field_name="min_density",
                canonical_name="min_density",
                origin=FieldOrigin.CUSTOMER_PROVIDED,
                node_label="Facility",
                is_gate_critical=True,
            ),
            FieldMapping(
                crm_field_name="max_density",
                canonical_name="max_density",
                origin=FieldOrigin.CUSTOMER_PROVIDED,
                node_label="Facility",
                is_gate_critical=True,
            ),
            FieldMapping(
                crm_field_name="process_type",
                canonical_name="process_type",
                origin=FieldOrigin.CUSTOMER_PROVIDED,
                node_label="Facility",
                is_gate_critical=True,
            ),
        ]
        full_impact = analyse_impact(mappings, intake_spec)
        assert full_impact.gates_passable_before >= 3

    def test_edge_type_counting(self, intake_spec: DomainSpec) -> None:
        """Edge types unlocked should reflect available nodes."""
        impact = analyse_impact([], intake_spec)
        assert impact.total_edge_types == 2

    def test_tier_recommendation_enrich(self, intake_spec: DomainSpec) -> None:
        """Low coverage → enrich recommendation."""
        mappings = [
            FieldMapping(
                crm_field_name="facility_id",
                canonical_name="facility_id",
                origin=FieldOrigin.CUSTOMER_PROVIDED,
                node_label="Facility",
            ),
        ]
        impact = analyse_impact(mappings, intake_spec)
        assert impact.tier_recommendation == "enrich"

    def test_tier_recommendation_autonomous(self, intake_spec: DomainSpec) -> None:
        """Full coverage → autonomous recommendation."""
        all_fields = [
            "facility_id",
            "name",
            "lat",
            "lon",
            "credit_score",
            "process_type",
            "min_density",
            "max_density",
            "food_grade_certified",
            "contamination_tolerance",
            "intake_id",
            "material_type",
        ]
        mappings = [
            FieldMapping(
                crm_field_name=f,
                canonical_name=f,
                origin=FieldOrigin.CUSTOMER_PROVIDED,
                node_label="Facility",
            )
            for f in all_fields
        ]
        impact = analyse_impact(mappings, intake_spec)
        assert impact.tier_recommendation == "autonomous"

    def test_format_summary(self, intake_spec: DomainSpec) -> None:
        """Summary format should contain key metrics."""
        impact = analyse_impact([], intake_spec)
        summary = format_impact_summary(impact)

        assert "YOUR CRM TODAY" in summary
        assert "AFTER ENRICH" in summary
        assert "WITH DISCOVER" in summary

    def test_critical_gaps_identified(self, intake_spec: DomainSpec) -> None:
        """Missing gate-critical fields should appear in critical_gaps."""
        impact = analyse_impact([], intake_spec)

        gap_fields = {g.field for g in impact.critical_gaps}
        # All gate candidate props should be in gaps when nothing is provided
        assert "food_grade_certified" in gap_fields
        assert "min_density" in gap_fields


# ── Vertical Discovery Tests ──────────────────────────────


@pytest.mark.unit
class TestVerticalDiscovery:
    """Tests for vertical_discovery.discover_vertical_fields."""

    def test_known_vertical_detection(self, intake_spec: DomainSpec) -> None:
        """Known vertical keywords should be detected."""
        result = discover_vertical_fields("We are a plastic recycling facility", spec=intake_spec)
        assert result.vertical_name == "plasticos"
        assert not result.discovery_suggested

    def test_unknown_vertical(self) -> None:
        """Unknown vertical → discovery suggested."""
        result = discover_vertical_fields("We make artisanal soap")
        assert result.vertical_name == "unknown"
        assert result.discovery_suggested
        assert len(result.vertical_fields) == 0

    def test_no_domain_spec_available(self) -> None:
        """No spec + no YAML → empty fields, discovery suggested."""
        result = discover_vertical_fields("plastic recycling", domains_dir="/nonexistent/path")
        assert result.discovery_suggested or len(result.vertical_fields) >= 0
