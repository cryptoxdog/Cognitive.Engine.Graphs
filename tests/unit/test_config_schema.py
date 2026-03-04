# ============================================================================
# tests/unit/test_config_schema.py
# ============================================================================
"""
Unit tests for engine/config/schema.py — all Pydantic models.
Target Coverage: 85%+
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from engine.config.schema import (
    AuditSpec,
    ComplianceRegimeSpec,
    ComplianceSpec,
    ComputationType,
    DerivedParameterSpec,
    DomainMetadata,
    DomainSpec,
    EdgeCategory,
    EdgeDirection,
    EdgeSpec,
    GateSpec,
    GateType,
    GDSJobScheduleSpec,
    GDSJobSpec,
    GDSProjectionSpec,
    GDSSpec,
    KGEBeamSearchSpec,
    KGEEnsembleSpec,
    KGESpec,
    KGEVectorIndexSpec,
    ManagedByType,
    MatchEntitiesSpec,
    MatchEntitySpec,
    NodeSpec,
    NullBehavior,
    OntologySpec,
    PIISpec,
    PluginsSpec,
    ProhibitedFactorsSpec,
    PropertySpec,
    PropertyType,
    QueryFieldSpec,
    QuerySchemaSpec,
    RetentionSpec,
    ScoringAggregation,
    ScoringDimensionSpec,
    ScoringSource,
    ScoringSpec,
    SoftSignalSpec,
    SyncEndpointSpec,
    SyncSpec,
    SyncStrategy,
    TaxonomyEdgeSpec,
    TraversalSpec,
    TraversalStepSpec,
)


# ============================================================================
# HELPERS
# ============================================================================

def _minimal_domain_raw() -> dict:
    """Return minimal valid raw dict for DomainSpec."""
    return {
        "domain": {"id": "test", "name": "Test", "version": "0.0.1"},
        "ontology": {
            "nodes": [
                {"label": "Facility", "managedby": "sync", "candidate": True, "properties": [
                    {"name": "fid", "type": "int", "required": True},
                ]},
                {"label": "Intake", "managedby": "api", "queryentity": True, "properties": []},
            ],
            "edges": [
                {"type": "EXCLUDED_FROM", "from": "Facility", "to": "Facility",
                 "direction": "DIRECTED", "category": "exclusion", "managedby": "sync"},
            ],
        },
        "matchentities": {
            "candidate": [{"label": "Facility", "matchdirection": "intake_to_buyer"}],
            "queryentity": [{"label": "Intake", "matchdirection": "intake_to_buyer"}],
        },
        "queryschema": {"matchdirections": ["intake_to_buyer"], "fields": []},
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
    }


# ============================================================================
# TEST CLASSES
# ============================================================================


@pytest.mark.unit
class TestEnums:
    """Test enum values exist."""

    def test_managed_by_type_values(self) -> None:
        """ManagedByType has expected members."""
        assert ManagedByType.SYNC == "sync"
        assert ManagedByType.GDS == "gds"
        assert ManagedByType.STATIC == "static"
        assert ManagedByType.API == "api"

    def test_property_type_values(self) -> None:
        """PropertyType has expected members."""
        assert PropertyType.STRING == "string"
        assert PropertyType.INT == "int"
        assert PropertyType.FLOAT == "float"
        assert PropertyType.BOOL == "bool"
        assert PropertyType.DATETIME == "datetime"

    def test_gate_type_values(self) -> None:
        """GateType has all 10 gate types."""
        assert len(GateType) == 10
        assert GateType.RANGE == "range"
        assert GateType.THRESHOLD == "threshold"
        assert GateType.TRAVERSAL == "traversal"

    def test_null_behavior_has_pass_and_fail(self) -> None:
        """NullBehavior enum has PASS and FAIL."""
        assert NullBehavior.PASS == "pass"
        assert NullBehavior.FAIL == "fail"

    def test_computation_type_values(self) -> None:
        """ComputationType includes KGE."""
        assert ComputationType.KGE == "kge"
        assert ComputationType.GEODECAY == "geodecay"

    def test_scoring_aggregation_values(self) -> None:
        """ScoringAggregation has additive and multiplicative."""
        assert ScoringAggregation.ADDITIVE == "additive"
        assert ScoringAggregation.MULTIPLICATIVE == "multiplicative"

    def test_edge_direction_values(self) -> None:
        """EdgeDirection has DIRECTED and UNDIRECTED."""
        assert EdgeDirection.DIRECTED == "DIRECTED"
        assert EdgeDirection.UNDIRECTED == "UNDIRECTED"

    def test_edge_category_values(self) -> None:
        """EdgeCategory has expected members."""
        assert EdgeCategory.CAPABILITY == "capability"
        assert EdgeCategory.EXCLUSION == "exclusion"

    def test_sync_strategy_values(self) -> None:
        """SyncStrategy has expected values."""
        assert SyncStrategy.UNWINDMERGE == "UNWINDMERGE"
        assert SyncStrategy.UNWINDMATCHSET == "UNWINDMATCHSET"


@pytest.mark.unit
class TestPropertySpec:
    """Test PropertySpec model."""

    def test_minimal_valid(self) -> None:
        """PropertySpec with required fields only."""
        p = PropertySpec(name="field1", type=PropertyType.STRING)
        assert p.name == "field1"
        assert p.required is False
        assert p.nullable is True

    def test_full_fields(self) -> None:
        """PropertySpec with all optional fields."""
        p = PropertySpec(
            name="status", type=PropertyType.ENUM, required=True,
            nullable=False, values=["active", "inactive"],
            managedby=ManagedByType.SYNC, description="Status field",
        )
        assert p.values == ["active", "inactive"]
        assert p.managedby == ManagedByType.SYNC


@pytest.mark.unit
class TestNodeSpec:
    """Test NodeSpec model."""

    def test_minimal_valid(self) -> None:
        """NodeSpec with required fields."""
        n = NodeSpec(label="Facility", managedby=ManagedByType.SYNC)
        assert n.label == "Facility"
        assert n.candidate is False
        assert n.properties == []

    def test_candidate_node(self) -> None:
        """NodeSpec marked as candidate."""
        n = NodeSpec(label="Buyer", managedby=ManagedByType.SYNC, candidate=True)
        assert n.candidate is True


@pytest.mark.unit
class TestEdgeSpec:
    """Test EdgeSpec model."""

    def test_valid_edge(self) -> None:
        """EdgeSpec validates with alias from_ -> from."""
        e = EdgeSpec(
            type="EXCLUDED_FROM", **{"from": "A"}, to="B",
            direction=EdgeDirection.DIRECTED, category=EdgeCategory.EXCLUSION,
            managedby=ManagedByType.SYNC,
        )
        assert e.from_ == "A"
        assert e.to == "B"

    def test_populate_by_name(self) -> None:
        """EdgeSpec accepts from_ directly."""
        e = EdgeSpec(
            type="LINK", from_="X", to="Y",
            direction=EdgeDirection.UNDIRECTED, category=EdgeCategory.CONTEXT,
            managedby=ManagedByType.API,
        )
        assert e.from_ == "X"


@pytest.mark.unit
class TestOntologySpec:
    """Test OntologySpec validators."""

    def test_duplicate_node_labels_raises(self) -> None:
        """OntologySpec rejects duplicate node labels."""
        with pytest.raises(PydanticValidationError, match="Duplicate node labels"):
            OntologySpec(
                nodes=[
                    NodeSpec(label="A", managedby=ManagedByType.SYNC),
                    NodeSpec(label="A", managedby=ManagedByType.API),
                ],
                edges=[],
            )

    def test_duplicate_edge_signatures_raises(self) -> None:
        """OntologySpec rejects duplicate edge type+from+to tuples."""
        edge = EdgeSpec(
            type="REL", from_="A", to="B",
            direction=EdgeDirection.DIRECTED, category=EdgeCategory.CAPABILITY,
            managedby=ManagedByType.SYNC,
        )
        with pytest.raises(PydanticValidationError, match="Duplicate edge type signatures"):
            OntologySpec(
                nodes=[NodeSpec(label="A", managedby=ManagedByType.SYNC),
                       NodeSpec(label="B", managedby=ManagedByType.SYNC)],
                edges=[edge, edge],
            )

    def test_valid_ontology(self) -> None:
        """OntologySpec passes with unique labels and edges."""
        o = OntologySpec(
            nodes=[NodeSpec(label="A", managedby=ManagedByType.SYNC),
                   NodeSpec(label="B", managedby=ManagedByType.SYNC)],
            edges=[EdgeSpec(type="REL", from_="A", to="B",
                           direction=EdgeDirection.DIRECTED,
                           category=EdgeCategory.CAPABILITY,
                           managedby=ManagedByType.SYNC)],
        )
        assert len(o.nodes) == 2


@pytest.mark.unit
class TestDomainSpec:
    """Test DomainSpec model and cross-reference validator."""

    def test_minimal_valid_domain_spec(self) -> None:
        """DomainSpec validates minimal valid input."""
        raw = _minimal_domain_raw()
        spec = DomainSpec.model_validate(raw)
        assert spec.domain.id == "test"
        assert spec.domain.version == "0.0.1"

    def test_missing_required_fields_raises(self) -> None:
        """DomainSpec rejects missing required fields."""
        with pytest.raises(PydanticValidationError):
            DomainSpec.model_validate({})

    def test_candidate_label_not_in_ontology_raises(self) -> None:
        """DomainSpec rejects candidate referencing unknown label."""
        raw = _minimal_domain_raw()
        raw["matchentities"]["candidate"] = [{"label": "Unknown", "matchdirection": "x"}]
        with pytest.raises(PydanticValidationError, match="Candidate label"):
            DomainSpec.model_validate(raw)

    def test_query_entity_label_not_in_ontology_raises(self) -> None:
        """DomainSpec rejects query entity referencing unknown label."""
        raw = _minimal_domain_raw()
        raw["matchentities"]["queryentity"] = [{"label": "Missing", "matchdirection": "x"}]
        with pytest.raises(PydanticValidationError, match="Query entity label"):
            DomainSpec.model_validate(raw)

    def test_exclusion_gate_unknown_edge_type_raises(self) -> None:
        """DomainSpec rejects exclusion gate referencing unknown edge type."""
        raw = _minimal_domain_raw()
        raw["gates"] = [{
            "name": "bad_gate", "type": "exclusion",
            "edgetype": "DOES_NOT_EXIST", "fromnode": "Facility", "tonode": "Facility",
        }]
        with pytest.raises(PydanticValidationError, match="unknown edge type"):
            DomainSpec.model_validate(raw)

    def test_model_dump_roundtrip(self) -> None:
        """DomainSpec serializes and deserializes cleanly."""
        raw = _minimal_domain_raw()
        spec = DomainSpec.model_validate(raw)
        dumped = spec.model_dump(mode="json")
        assert dumped["domain"]["id"] == "test"

    def test_gds_job_unknown_node_label_raises(self) -> None:
        """DomainSpec rejects GDS job referencing unknown node label."""
        raw = _minimal_domain_raw()
        raw["gdsjobs"] = [{
            "name": "bad_job", "algorithm": "louvain",
            "schedule": {"type": "manual"},
            "projection": {"nodelabels": ["Ghost"], "edgetypes": ["EXCLUDED_FROM"]},
        }]
        with pytest.raises(PydanticValidationError, match="unknown node label"):
            DomainSpec.model_validate(raw)


@pytest.mark.unit
class TestGateSpec:
    """Test GateSpec model."""

    def test_all_gate_types_valid(self) -> None:
        """GateSpec accepts all GateType enum values."""
        for gt in GateType:
            gate = GateSpec(name=f"test_{gt.value}", type=gt)
            assert gate.type == gt

    def test_null_behavior_default(self) -> None:
        """GateSpec defaults nullbehavior to PASS."""
        gate = GateSpec(name="g1", type=GateType.THRESHOLD)
        assert gate.nullbehavior == NullBehavior.PASS


@pytest.mark.unit
class TestScoringDimensionSpec:
    """Test ScoringDimensionSpec model."""

    def test_valid_dimension(self) -> None:
        """ScoringDimensionSpec with required fields."""
        d = ScoringDimensionSpec(
            name="geo", source=ScoringSource.COMPUTED,
            computation=ComputationType.GEODECAY,
            weightkey="w_geo", defaultweight=0.25,
        )
        assert d.defaultwhennull == 0.0
        assert d.aggregation == ScoringAggregation.ADDITIVE


@pytest.mark.unit
class TestKGEModels:
    """Test KGE-related Pydantic models."""

    def test_kge_beam_search_spec_defaults(self) -> None:
        """KGEBeamSearchSpec has sensible defaults."""
        s = KGEBeamSearchSpec()
        assert s.beamwidth == 10
        assert s.maxdepth == 3

    def test_kge_ensemble_spec(self) -> None:
        """KGEEnsembleSpec stores strategy and weights."""
        e = KGEEnsembleSpec(strategy="weightedaverage")
        assert e.cypherweight == 0.6
        assert e.kgeweight == 0.4

    def test_kge_spec_defaults(self) -> None:
        """KGESpec has CompoundE3D as default model."""
        k = KGESpec()
        assert k.model == "CompoundE3D"
        assert k.embeddingdim == 256


@pytest.mark.unit
class TestComplianceModels:
    """Test compliance-related Pydantic models."""

    def test_audit_spec_defaults(self) -> None:
        """AuditSpec has sensible defaults."""
        a = AuditSpec()
        assert a.enabled is True
        assert a.retentiondays == 90

    def test_pii_spec_defaults(self) -> None:
        """PIISpec defaults to disabled."""
        p = PIISpec()
        assert p.enabled is False
        assert p.handling == "hash"

    def test_compliance_spec_empty(self) -> None:
        """ComplianceSpec can be created with defaults."""
        c = ComplianceSpec()
        assert c.regimes == []


@pytest.mark.unit
class TestSyncModels:
    """Test sync-related models."""

    def test_sync_endpoint_spec(self) -> None:
        """SyncEndpointSpec validates required fields."""
        s = SyncEndpointSpec(path="/sync/facilities", targetnode="Facility",
                            batchstrategy=SyncStrategy.UNWINDMERGE)
        assert s.method == "POST"

    def test_gds_spec_alias(self) -> None:
        """GDSSpec accepts gdsjobs alias."""
        g = GDSSpec(gdsjobs=[])
        assert g.jobs == []


@pytest.mark.unit
class TestDomainMetadata:
    """Test DomainMetadata model."""

    def test_valid_metadata(self) -> None:
        """DomainMetadata with required fields."""
        m = DomainMetadata(id="plasticos", name="PlasticOS", version="1.0.0")
        assert m.alternatedomains == []

    def test_alternate_domains(self) -> None:
        """DomainMetadata stores alternate domains."""
        m = DomainMetadata(id="p", name="P", version="1", alternatedomains=["alt1"])
        assert m.alternatedomains == ["alt1"]
