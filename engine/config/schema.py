"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [config]
tags: [config, pydantic, domain-spec]
owner: engine-team
status: active
--- /L9_META ---

Pydantic schema models for domain pack validation.
Defines the contract every spec.yaml must satisfy.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ManagedByType(StrEnum):
    """Entity lifecycle management source."""

    SYNC = "sync"
    GDS = "gds"
    STATIC = "static"
    API = "api"
    COMPUTED = "computed"
    CUSTOMAGGREGATION = "customaggregation"


class PropertyType(StrEnum):
    """Supported property data types."""

    STRING = "string"
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    DATETIME = "datetime"
    DATE = "date"
    DURATION = "duration"
    ENUM = "enum"


class EdgeDirection(StrEnum):
    """Edge directionality."""

    DIRECTED = "DIRECTED"
    UNDIRECTED = "UNDIRECTED"


class EdgeCategory(StrEnum):
    """Semantic edge classification."""

    CAPABILITY = "capability"
    TAXONOMY = "taxonomy"
    TRANSACTION = "transaction"
    EXCLUSION = "exclusion"
    PRECOMPUTED = "precomputed"
    MARKET = "market"
    CONTEXT = "context"
    REFERRAL = "referral"
    INTENT = "intent"


class GateType(StrEnum):
    """Gate type registry."""

    RANGE = "range"
    THRESHOLD = "threshold"
    BOOLEAN = "boolean"
    COMPOSITE = "composite"
    ENUMMAP = "enummap"
    EXCLUSION = "exclusion"
    SELFRANGE = "selfrange"
    FRESHNESS = "freshness"
    TEMPORALRANGE = "temporalrange"
    TRAVERSAL = "traversal"


class NullBehavior(StrEnum):
    """NULL value handling strategy."""

    PASS = "pass"
    FAIL = "fail"


class ComputationType(StrEnum):
    """Scoring computation function registry."""

    GEODECAY = "geodecay"
    LOGNORMALIZED = "lognormalized"
    COMMUNITYMATCH = "communitymatch"
    INVERSELINEAR = "inverselinear"
    CANDIDATEPROPERTY = "candidateproperty"
    WEIGHTEDRATE = "weightedrate"
    PRICEALIGNMENT = "pricealignment"
    TEMPORALPROXIMITY = "temporalproximity"
    CUSTOMCYPHER = "customcypher"
    TRAVERSALALIAS = "traversalalias"
    KGE = "kge"
    VARIANTDISCOVERY = "variantdiscovery"
    ENSEMBLECONFIDENCE = "ensembleconfidence"


class ScoringSource(StrEnum):
    """Scoring dimension data source."""

    CANDIDATEPROPERTY = "candidateproperty"
    QUERYPROPERTY = "queryproperty"
    COMPUTED = "computed"
    TRAVERSALALIAS = "traversalalias"
    EXTERNAL = "external"


class ScoringAggregation(StrEnum):
    """Score combination method."""

    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"


class SyncStrategy(StrEnum):
    """Batch sync Cypher generation strategy."""

    UNWINDMERGE = "UNWINDMERGE"
    UNWINDMATCHSET = "UNWINDMATCHSET"


class PropertySpec(BaseModel):
    """Property definition for nodes and edges."""

    name: str
    type: PropertyType
    unit: str | None = None
    required: bool = False
    nullable: bool = True
    values: list[str] | None = None  # For enum types
    managedby: ManagedByType | None = None
    description: str | None = None


class NodeSpec(BaseModel):
    """Node label specification."""

    label: str
    description: str | None = None
    managedby: ManagedByType | None = None
    candidate: bool = False
    queryentity: bool = False
    taxonomy: bool = False
    auxiliary: bool = False
    matchdirection: str | None = None
    properties: list[PropertySpec] = Field(default_factory=list)


class EdgeSpec(BaseModel):
    """Edge type specification."""

    type: str
    from_: str = Field(..., alias="from")
    to: str
    direction: EdgeDirection
    category: EdgeCategory
    managedby: ManagedByType
    properties: list[PropertySpec] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class OntologySpec(BaseModel):
    """Complete ontology (nodes + edges)."""

    nodes: list[NodeSpec]
    edges: list[EdgeSpec]

    @field_validator("nodes", mode="before")
    @classmethod
    def coerce_nodes_dict_to_list(cls, v: object) -> object:
        """Accept dict-grouped nodes (e.g. {candidates: [...], query_entities: [...]})
        in addition to the canonical flat list format."""
        if isinstance(v, dict):
            merged: list[object] = []
            for group in v.values():
                if isinstance(group, list):
                    merged.extend(group)
            return merged
        return v

    @field_validator("nodes")
    @classmethod
    def validate_unique_labels(cls, nodes: list[NodeSpec]) -> list[NodeSpec]:
        """Ensure node labels are unique."""
        labels = [n.label for n in nodes]
        if len(labels) != len(set(labels)):
            raise ValueError("Duplicate node labels detected in ontology")
        return nodes

    @field_validator("edges", mode="before")
    @classmethod
    def coerce_edges_dict_to_list(cls, v: object) -> object:
        """Accept dict-grouped edges in addition to canonical flat list format."""
        if isinstance(v, dict):
            merged: list[object] = []
            for group in v.values():
                if isinstance(group, list):
                    merged.extend(group)
            return merged
        return v

    @field_validator("edges")
    @classmethod
    def validate_unique_edge_types(cls, edges: list[EdgeSpec]) -> list[EdgeSpec]:
        """Ensure edge type + from + to tuples are unique."""
        signatures = [(e.type, e.from_, e.to) for e in edges]
        if len(signatures) != len(set(signatures)):
            raise ValueError("Duplicate edge type signatures detected")
        return edges


class MatchEntitySpec(BaseModel):
    """Match entity configuration (candidate or query)."""

    label: str
    matchdirection: str


class MatchEntitiesSpec(BaseModel):
    """Bidirectional match entity definitions."""

    candidate: list[MatchEntitySpec]
    queryentity: list[MatchEntitySpec]


class QueryFieldSpec(BaseModel):
    """Query schema field definition."""

    name: str
    type: PropertyType
    unit: str | None = None
    required: bool = False
    default: Any | None = None
    mapstotaxonomy: str | None = None  # Target taxonomy node label


class QuerySchemaSpec(BaseModel):
    """Query schema for /v1/match requests."""

    matchdirections: list[str]
    fields: list[QueryFieldSpec]


class DerivedParameterSpec(BaseModel):
    """Computed parameter from query fields."""

    name: str
    expression: str  # Simple algebraic expression
    type: PropertyType
    unit: str | None = None
    description: str | None = None


class TraversalStepSpec(BaseModel):
    """Traversal pattern declaration."""

    name: str
    description: str | None = None
    pattern: str  # Cypher pattern fragment
    required: bool = True
    matchdirections: list[str] | None = None


class TraversalSpec(BaseModel):
    """Traversal configuration."""

    steps: list[TraversalStepSpec]

    @model_validator(mode="after")
    def validate_traversal_hops(self) -> TraversalSpec:
        """W1-04: Validate traversal hop counts against hard cap.

        Ensures no variable-length path exceeds MAX_HOP_HARD_CAP.
        """
        import re

        from engine.config.settings import settings

        max_cap = settings.max_hop_hard_cap
        hop_re = re.compile(r"\*(\d+)?(?:\.\.(\d+))?")

        for step in self.steps:
            for match in hop_re.finditer(step.pattern):
                min_hops_str, max_hops_str = match.group(1), match.group(2)
                # Validate min hops
                if min_hops_str:
                    min_hops = int(min_hops_str)
                    if min_hops < 1:
                        msg = f"Traversal step '{step.name}': hop count must be >= 1, got {min_hops}"
                        raise ValueError(msg)
                # Validate max hops
                if max_hops_str:
                    max_hops = int(max_hops_str)
                elif min_hops_str:
                    max_hops = int(min_hops_str)
                else:
                    # unbounded '*' — flag it
                    max_hops = max_cap + 1
                if max_hops < 1:
                    msg = f"Traversal step '{step.name}': hop count must be >= 1, got {max_hops}"
                    raise ValueError(msg)
                if max_hops > max_cap:
                    msg = f"Traversal step '{step.name}': max hops {max_hops} exceeds hard cap {max_cap}"
                    raise ValueError(msg)

        return self


class GateSpec(BaseModel):
    """Gate definition."""

    name: str
    description: str | None = None
    type: GateType
    candidateprop: str | None = None
    queryparam: str | None = None

    @field_validator("queryparam", mode="before")
    @classmethod
    def coerce_queryparam_to_str(cls, v: object) -> object:
        """YAML parses unquoted booleans/numbers as native types; coerce to str."""
        if v is not None and not isinstance(v, str):
            return str(v)
        return v

    operator: str | None = None

    @field_validator("operator", mode="before")
    @classmethod
    def validate_operator(cls, v: object) -> object:
        """W1-03: Validate gate operator is a known safe value."""
        if v is None:
            return v
        allowed = {">=", "<=", ">", "<", "=", "!=", "<>", "IN", "CONTAINS", "STARTS WITH", "ENDS WITH"}
        if str(v) not in allowed:
            msg = f"Gate operator '{v}' is not in the allowed set: {sorted(allowed)}"
            raise ValueError(msg)
        return v

    logic: str | None = None  # For composite gates: "AND" / "OR"
    nullbehavior: NullBehavior = NullBehavior.PASS
    roleexempt: list[str] | None = None
    relaxedpenalty: float = 0.0
    matchdirections: list[str] | None = None
    invertible: bool = False
    strictwhen: str | None = None  # Conditional strictness expression
    cypheroverride: str | None = None  # Custom Cypher for complex gates
    # Type-specific fields
    subgates: list[str] | None = None  # For composite
    mapping: dict[str, list[str]] | None = None  # For enummap
    edgetype: str | None = None  # For exclusion
    fromnode: str | None = None
    tonode: str | None = None
    maxagedays: int | None = None  # For freshness
    candidateprop_min: str | None = None  # For selfrange, temporalrange
    candidateprop_max: str | None = None
    queryparam_min: str | None = None  # For range, temporalrange
    queryparam_max: str | None = None
    queryparam_start: str | None = None  # For temporalrange
    queryparam_end: str | None = None
    candidateprop_start: str | None = None
    candidateprop_end: str | None = None
    pattern: str | None = None  # For traversal gate
    condition: str | None = None


class ScoringDimensionSpec(BaseModel):
    """Scoring dimension definition."""

    name: str
    description: str | None = None
    source: ScoringSource
    candidateprop: str | None = None
    queryprop: str | None = None
    alias: str | None = None  # Traversal alias reference
    computation: ComputationType
    expression: str | None = None  # For customcypher
    normalization: str | None = None
    minvalue: float | None = None
    maxvalue: float | None = None
    defaultwhennull: float = 0.0
    decayconstant: float | None = None  # For geodecay: distance k in meters
    bias: float | None = None  # For communitymatch: multiplicative boost
    weightkey: str
    defaultweight: float
    aggregation: ScoringAggregation = ScoringAggregation.ADDITIVE
    matchdirections: list[str] | None = None


class ScoringSpec(BaseModel):
    """Scoring configuration."""

    dimensions: list[ScoringDimensionSpec]


class SoftSignalSpec(BaseModel):
    """Soft signal bonus/penalty."""

    name: str
    bonus: float
    candidateprop: str | None = None
    queryparam: str | None = None
    threshold: Any | None = None
    matchtype: str | None = None  # equals, lessthan, greaterthan, between
    condition: str | None = None
    matchdirections: list[str] | None = None


class TaxonomyEdgeSpec(BaseModel):
    """Taxonomy edge for sync auto-linking."""

    field: str
    edgetype: str
    targetlabel: str
    targetid: str


class ChildSyncSpec(BaseModel):
    """Nested child entity sync."""

    field: str  # JSON field containing child array
    targetnode: str
    targetid: str
    edgetype: str
    edgedirection: str  # parenttochild, childtoparent


class SyncEndpointSpec(BaseModel):
    """Sync endpoint definition."""

    path: str
    method: str = "POST"
    targetnode: str | None = None
    targetedge: str | None = None
    fromnode: str | None = None
    tonode: str | None = None
    idproperty: str | None = None
    batchstrategy: SyncStrategy
    taxonomyedges: list[TaxonomyEdgeSpec] | None = None
    childsync: list[ChildSyncSpec] | None = None
    fieldsupdated: list[str] | None = None  # For PATCH operations


class SyncSpec(BaseModel):
    """Sync configuration."""

    endpoints: list[SyncEndpointSpec]


class GDSJobScheduleSpec(BaseModel):
    """GDS job schedule."""

    type: str  # cron, manual
    cron: str | None = None


class GDSProjectionSpec(BaseModel):
    """GDS graph projection."""

    nodelabels: list[str]
    edgetypes: list[str]


class GDSJobSpec(BaseModel):
    """GDS job definition."""

    name: str
    algorithm: str
    schedule: GDSJobScheduleSpec
    projection: GDSProjectionSpec
    writeproperty: str | None = None
    writeto: str | None = None  # Target node label
    writeedge: str | None = None
    writeproperties: list[dict[str, Any]] | None = None
    sourceedge: str | None = None
    filter: str | None = None
    aggregate: str | None = None
    ratenumeratorfilter: str | None = None
    ratedenominatorfilter: str | None = None
    recencydecay: bool = False
    recencyhalflifedays: int | None = None


class GDSSpec(BaseModel):
    """GDS jobs configuration."""

    jobs: list[GDSJobSpec] = Field(default_factory=list, alias="gdsjobs")

    class Config:
        populate_by_name = True


class KGEBeamSearchSpec(BaseModel):
    """KGE beam search configuration."""

    beamwidth: int = 10
    maxdepth: int = 3


class KGEEnsembleSpec(BaseModel):
    """KGE ensemble strategy."""

    strategy: str  # weightedaverage, rankaggregation, mixtureofexperts
    cypherweight: float = 0.6
    kgeweight: float = 0.4


class KGEVectorIndexSpec(BaseModel):
    """Vector index for KGE embeddings."""

    name: str
    dimension: int = 256
    similarityfunction: str = "cosine"


class KGESpec(BaseModel):
    """Knowledge graph embedding configuration."""

    model: str = "CompoundE3D"
    embeddingdim: int = 256
    trainingrelations: list[str] = Field(default_factory=list)
    beamsearch: KGEBeamSearchSpec | None = None
    ensemble: KGEEnsembleSpec | None = None
    vectorindex: KGEVectorIndexSpec | None = None


class CalibrationPair(BaseModel):
    """A labeled calibration pair defining expected score range for two entities."""

    node_a: str
    node_b: str
    expected_score_min: float = Field(ge=0.0, le=1.0)
    expected_score_max: float = Field(ge=0.0, le=1.0)
    label: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> CalibrationPair:
        """Ensure min <= max."""
        if self.expected_score_min > self.expected_score_max:
            msg = f"Calibration pair: expected_score_min ({self.expected_score_min}) > expected_score_max ({self.expected_score_max})"
            raise ValueError(msg)
        return self


class CalibrationSpec(BaseModel):
    """Calibration configuration for forward simulation verification."""

    pairs: list[CalibrationPair] = Field(default_factory=list)
    weight_set: str | None = None


class ComplianceRegimeSpec(BaseModel):
    """Compliance regime identifier."""

    name: str
    description: str | None = None


class ProhibitedFactorsSpec(BaseModel):
    """Prohibited factors enforcement."""

    enabled: bool = True
    blockedfields: list[str] = Field(default_factory=list)
    enforcement: str = "compiletime"  # compiletime, runtime, compiletimeandruntime
    auditonviolation: bool = True


class AuditSpec(BaseModel):
    """Audit logging configuration."""

    enabled: bool = True
    logmatchrequests: bool = True
    logmatchresults: bool = True
    logsyncoperations: bool = True
    logadminoperations: bool = True
    retentiondays: int = 90


class PIISpec(BaseModel):
    """PII handling configuration."""

    enabled: bool = False
    fields: list[str] = Field(default_factory=list)
    candidatefields: list[str] = Field(default_factory=list)
    handling: str = "hash"  # hash, encrypt, redact, tokenize
    encryptionkeysource: str = "env"  # env, vault, kms


class RetentionSpec(BaseModel):
    """Data retention policies."""

    transactionttldays: int | None = None
    auditttldays: int | None = None
    piittldays: int | None = None


class ComplianceSpec(BaseModel):
    """Compliance and governance configuration."""

    regimes: list[ComplianceRegimeSpec] = Field(default_factory=list)
    prohibitedfactors: ProhibitedFactorsSpec | None = None
    audit: AuditSpec | None = None
    pii: PIISpec | None = None
    retention: RetentionSpec | None = None


class PluginsSpec(BaseModel):
    """Plugin extension points."""

    customgatetypes: list[str] = Field(default_factory=list)
    customcomputationtypes: list[str] = Field(default_factory=list)
    prematchhooks: list[str] = Field(default_factory=list)
    postmatchhooks: list[str] = Field(default_factory=list)
    syncvalidators: list[str] = Field(default_factory=list)


class DomainMetadata(BaseModel):
    """Domain pack metadata."""

    id: str
    name: str
    description: str | None = None
    version: str
    alternatedomains: list[str] = Field(default_factory=list)


class DomainSpec(BaseModel):
    """Complete domain pack specification."""

    domain: DomainMetadata
    ontology: OntologySpec
    matchentities: MatchEntitiesSpec
    queryschema: QuerySchemaSpec
    traversal: TraversalSpec | None = None
    gates: list[GateSpec]
    scoring: ScoringSpec
    derivedparameters: list[DerivedParameterSpec] = Field(default_factory=list)
    softsignals: list[SoftSignalSpec] = Field(default_factory=list)
    sync: SyncSpec | None = None
    gdsjobs: list[GDSJobSpec] = Field(default_factory=list)
    kge: KGESpec | None = None
    compliance: ComplianceSpec | None = None
    plugins: PluginsSpec | None = None
    calibration: CalibrationSpec | None = None

    @model_validator(mode="after")
    def validate_cross_references(self) -> DomainSpec:
        """Validate cross-references between sections.

        W1-01 (seL4-inspired): Enforces global invariants across the domain spec,
        mirroring seL4's approach of verifying system-wide consistency rather than
        checking individual objects in isolation. Gated by DOMAIN_STRICT_VALIDATION.
        """
        from engine.config.settings import settings

        # Collect all node labels
        node_labels = {n.label for n in self.ontology.nodes}

        # Collect all node properties per label
        node_props: dict[str, set[str]] = {}
        for node in self.ontology.nodes:
            node_props[node.label] = {p.name for p in node.properties}

        # Collect all edge types
        edge_types = {e.type for e in self.ontology.edges}

        # Collect all query schema field names + derived param names (valid gate params)
        query_field_names = {f.name for f in self.queryschema.fields}
        derived_param_names = {p.name for p in self.derivedparameters}
        all_param_names = query_field_names | derived_param_names

        # Validate candidate/queryentity references
        for candidate in self.matchentities.candidate:
            if candidate.label not in node_labels:
                msg = f"Candidate label '{candidate.label}' not found in ontology"
                raise ValueError(msg)

        for qe in self.matchentities.queryentity:
            if qe.label not in node_labels:
                msg = f"Query entity label '{qe.label}' not found in ontology"
                raise ValueError(msg)

        # (a) W1-01: Every edge source/target type references a declared node
        if settings.domain_strict_validation:
            for edge in self.ontology.edges:
                if edge.from_ not in node_labels:
                    msg = f"Edge '{edge.type}' source '{edge.from_}' not found in ontology nodes"
                    raise ValueError(msg)
                if edge.to not in node_labels:
                    msg = f"Edge '{edge.type}' target '{edge.to}' not found in ontology nodes"
                    raise ValueError(msg)

        # Validate gate property references
        for gate in self.gates:
            if gate.candidateprop and "." not in gate.candidateprop:
                # Check if any candidate node has this property
                found = False
                for candidate_ent in self.matchentities.candidate:
                    if candidate_ent.label in node_props and gate.candidateprop in node_props[candidate_ent.label]:
                        found = True
                        break
                if not found:
                    # Warning only, might be traversal alias
                    pass

            if gate.type == GateType.EXCLUSION and gate.edgetype:
                if gate.edgetype not in edge_types:
                    msg = f"Gate '{gate.name}' references unknown edge type '{gate.edgetype}'"
                    raise ValueError(msg)

            # (d) W1-01: No gate references an undeclared parameter
            if settings.domain_strict_validation and gate.queryparam and all_param_names:
                if gate.queryparam not in all_param_names:
                    # Allow params that look like compound refs (e.g. with _min/_max suffixes)
                    base = gate.queryparam.removesuffix("_min").removesuffix("_max")
                    base = base.removesuffix("_start").removesuffix("_end")
                    if base not in all_param_names and gate.queryparam not in all_param_names:
                        import logging

                        _logger = logging.getLogger(__name__)
                        _logger.warning(
                            "Gate '%s' references undeclared parameter '%s'",
                            gate.name,
                            gate.queryparam,
                        )

        # (c) W1-01: Scoring dimension default weights sum check
        if settings.domain_strict_validation and self.scoring and self.scoring.dimensions:
            weight_sum = sum(d.defaultweight for d in self.scoring.dimensions)
            weight_ceiling = 1.0
            tolerance = 1e-9
            if weight_sum > weight_ceiling + tolerance:
                msg = f"Scoring dimension default weights sum to {weight_sum:.4f}, exceeding {weight_ceiling}"
                raise ValueError(msg)

        # Validate GDS job references
        for job in self.gdsjobs:
            for label in job.projection.nodelabels:
                if label not in node_labels:
                    msg = f"GDS job '{job.name}' references unknown node label '{label}'"
                    raise ValueError(msg)
            for etype in job.projection.edgetypes:
                if etype not in edge_types:
                    msg = f"GDS job '{job.name}' references unknown edge type '{etype}'"
                    raise ValueError(msg)

        return self
