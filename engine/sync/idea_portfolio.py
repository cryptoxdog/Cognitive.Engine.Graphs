"""IdeaOS portfolio projection hydration for the CEG idea-portfolio domain.

IdeaOS owns canonical idea identity and lifecycle truth. This module accepts the
narrow ``IdeaGraphProjection`` contract, validates it, compiles graph-safe
facets, and applies a revision-chained hydration batch to CEG. It never parses
raw IdeaOS corpus files and never infers idea identity from filenames.

Hydration is an owner-native CEG write path. The public Constellation transport
binding can call this service later without moving semantic ownership into an
adapter.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
DOMAIN_ID = "idea-portfolio"
_STATE_ID = "canonical"
_RELATION_TYPES = ("PRODUCES", "REQUIRES", "TARGETS", "USES", "DEPENDS_ON")


class IdeaPortfolioHydrationError(ValueError):
    """Raised when a hydration batch cannot be safely admitted or applied."""


class EvidenceState(StrEnum):
    VERIFIED = "VERIFIED"
    SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"
    HYPOTHESIS = "HYPOTHESIS"
    UNKNOWN = "UNKNOWN"


class AssertionKind(StrEnum):
    CAPABILITY = "capability"
    SUBSTRATE = "substrate"
    PROOF_ASSET = "proof_asset"
    DATA_ASSET = "data_asset"
    MARKET = "market"
    CUSTOMER_TYPE = "customer_type"
    DEPENDENCY = "dependency"


class AssertionRelation(StrEnum):
    PRODUCES = "produces"
    REQUIRES = "requires"
    TARGETS = "targets"
    USES = "uses"
    DEPENDS_ON = "depends_on"


_ALLOWED_RELATIONS: dict[AssertionKind, frozenset[AssertionRelation]] = {
    AssertionKind.CAPABILITY: frozenset(
        {AssertionRelation.PRODUCES, AssertionRelation.REQUIRES, AssertionRelation.USES}
    ),
    AssertionKind.SUBSTRATE: frozenset(
        {AssertionRelation.PRODUCES, AssertionRelation.REQUIRES, AssertionRelation.USES}
    ),
    AssertionKind.PROOF_ASSET: frozenset(
        {AssertionRelation.PRODUCES, AssertionRelation.REQUIRES, AssertionRelation.USES}
    ),
    AssertionKind.DATA_ASSET: frozenset(
        {AssertionRelation.PRODUCES, AssertionRelation.REQUIRES, AssertionRelation.USES}
    ),
    AssertionKind.MARKET: frozenset({AssertionRelation.TARGETS}),
    AssertionKind.CUSTOMER_TYPE: frozenset({AssertionRelation.TARGETS}),
    AssertionKind.DEPENDENCY: frozenset({AssertionRelation.DEPENDS_ON}),
}

_EDGE_BY_RELATION: dict[AssertionRelation, str] = {
    AssertionRelation.PRODUCES: "PRODUCES",
    AssertionRelation.REQUIRES: "REQUIRES",
    AssertionRelation.TARGETS: "TARGETS",
    AssertionRelation.USES: "USES",
    AssertionRelation.DEPENDS_ON: "DEPENDS_ON",
}


class IdeaLifecycle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str = Field(min_length=1)
    decision: Literal["GO", "CONDITIONAL_GO", "HOLD", "NO_GO"] | None = None
    proof_state: str | None = None
    execution_state: str | None = None


class IdeaAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: AssertionKind
    relation: AssertionRelation
    key: str = Field(min_length=1)
    evidence_state: EvidenceState
    source_refs: list[str]

    @model_validator(mode="after")
    def validate_semantics(self) -> "IdeaAssertion":
        if self.relation not in _ALLOWED_RELATIONS[self.kind]:
            raise ValueError(
                f"relation {self.relation.value!r} is not valid for assertion kind {self.kind.value!r}"
            )
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("assertion source_refs must be unique")
        if self.evidence_state != EvidenceState.UNKNOWN and not self.source_refs:
            raise ValueError("non-UNKNOWN assertions require at least one source_ref")
        return self


class IdeaGraphProjection(BaseModel):
    """Mirror of IdeaOS ``ideaos.idea-graph-projection/v1`` at the CEG boundary."""

    model_config = ConfigDict(extra="forbid")

    schema: Literal["ideaos.idea-graph-projection/v1"]
    idea_id: str = Field(min_length=1)
    source_refs: list[str]
    source_digest: str = Field(pattern=DIGEST_PATTERN)
    lifecycle: IdeaLifecycle
    assertions: list[IdeaAssertion]
    unknowns: list[str]

    @model_validator(mode="after")
    def validate_projection(self) -> "IdeaGraphProjection":
        if not self.source_refs:
            raise ValueError("hydrated IdeaGraphProjection requires at least one source_ref")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("projection source_refs must be unique")
        if len(self.unknowns) != len(set(self.unknowns)):
            raise ValueError("projection unknowns must be unique")

        semantic_keys = [(a.kind.value, a.relation.value, _canonical_key(a.key)) for a in self.assertions]
        if len(semantic_keys) != len(set(semantic_keys)):
            raise ValueError("projection contains duplicate semantic assertions")
        return self


class IdeaPortfolioSyncRecord(BaseModel):
    """CEG persistence command around an IdeaOS projection."""

    model_config = ConfigDict(extra="forbid")

    schema: Literal["ceg.idea-portfolio-sync-record/v1"]
    operation: Literal["upsert", "tombstone"]
    projection: IdeaGraphProjection | None = None
    idea_id: str | None = None

    @model_validator(mode="after")
    def validate_operation(self) -> "IdeaPortfolioSyncRecord":
        if self.operation == "upsert":
            if self.projection is None:
                raise ValueError("upsert sync record requires projection")
            if self.idea_id is not None and self.idea_id != self.projection.idea_id:
                raise ValueError("sync record idea_id does not match projection idea_id")
        else:
            if self.idea_id is None:
                raise ValueError("tombstone sync record requires idea_id")
            if self.projection is not None:
                raise ValueError("tombstone sync record must not contain projection")
        return self

    @property
    def resolved_idea_id(self) -> str:
        if self.projection is not None:
            return self.projection.idea_id
        assert self.idea_id is not None
        return self.idea_id


class IdeaPortfolioHydrationEnvelope(BaseModel):
    """One ordered corpus delta chained to the previously committed graph revision."""

    model_config = ConfigDict(extra="forbid")

    schema: Literal["ceg.idea-portfolio-hydration/v1"]
    source_snapshot_ref: str = Field(min_length=1)
    source_snapshot_digest: str = Field(pattern=DIGEST_PATTERN)
    expected_graph_revision: str | None = Field(default=None, pattern=DIGEST_PATTERN)
    records: list[IdeaPortfolioSyncRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_records(self) -> "IdeaPortfolioHydrationEnvelope":
        idea_ids = [record.resolved_idea_id for record in self.records]
        if len(idea_ids) != len(set(idea_ids)):
            raise ValueError("hydration envelope may contain at most one record per idea_id")
        return self


class GraphWriter(Protocol):
    async def execute_write(
        self,
        transaction_function: Any = None,
        *args: Any,
        cypher: str | None = None,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | Any: ...


@dataclass(frozen=True)
class CompiledAssertion:
    assertion_id: str
    facet_id: str
    kind: str
    key: str
    relation: str
    evidence_state: str
    source_refs_json: str


@dataclass(frozen=True)
class HydrationPlan:
    envelope: IdeaPortfolioHydrationEnvelope
    batch_digest: str
    graph_revision: str


@dataclass(frozen=True)
class WriteCommand:
    cypher: str
    parameters: dict[str, Any]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_key(value: str) -> str:
    """Preserve source semantics while removing encoding/edge whitespace noise."""

    return unicodedata.normalize("NFC", value).strip()


def _facet_id(kind: AssertionKind | str, key: str) -> str:
    kind_value = kind.value if isinstance(kind, AssertionKind) else kind
    digest = hashlib.sha256(f"{kind_value}\x00{_canonical_key(key)}".encode()).hexdigest()
    return f"facet:{digest}"


def _assertion_id(idea_id: str, assertion: IdeaAssertion) -> str:
    semantic_key = (
        f"{idea_id}\x00{assertion.relation.value}\x00{assertion.kind.value}"
        f"\x00{_canonical_key(assertion.key)}"
    )
    return "assertion:" + hashlib.sha256(semantic_key.encode()).hexdigest()


def projection_digest(projection: IdeaGraphProjection) -> str:
    return _sha256_text(_canonical_json(projection.model_dump(mode="json")))


def compile_assertions(projection: IdeaGraphProjection) -> list[CompiledAssertion]:
    compiled: list[CompiledAssertion] = []
    for assertion in projection.assertions:
        compiled.append(
            CompiledAssertion(
                assertion_id=_assertion_id(projection.idea_id, assertion),
                facet_id=_facet_id(assertion.kind, assertion.key),
                kind=assertion.kind.value,
                key=_canonical_key(assertion.key),
                relation=assertion.relation.value,
                evidence_state=assertion.evidence_state.value,
                source_refs_json=_canonical_json(sorted(assertion.source_refs)),
            )
        )
    return compiled


def build_portfolio_match_query(projection: IdeaGraphProjection | dict[str, Any]) -> dict[str, Any]:
    """Compile one IdeaOS projection into the flat query shape declared by the domain pack."""

    model = projection if isinstance(projection, IdeaGraphProjection) else IdeaGraphProjection.model_validate(projection)
    compiled = compile_assertions(model)

    by_relation: dict[str, list[str]] = {relation.value: [] for relation in AssertionRelation}
    for assertion in compiled:
        by_relation[assertion.relation].append(assertion.facet_id)

    def encoded(relation: str) -> str:
        ids = sorted(set(by_relation[relation]))
        return "" if not ids else "|" + "|".join(ids) + "|"

    return {
        "idea_id": model.idea_id,
        "requires_facets": encoded(AssertionRelation.REQUIRES.value),
        "requires_count": len(set(by_relation[AssertionRelation.REQUIRES.value])),
        "produces_facets": encoded(AssertionRelation.PRODUCES.value),
        "produces_count": len(set(by_relation[AssertionRelation.PRODUCES.value])),
        "uses_facets": encoded(AssertionRelation.USES.value),
        "uses_count": len(set(by_relation[AssertionRelation.USES.value])),
        "targets_facets": encoded(AssertionRelation.TARGETS.value),
        "targets_count": len(set(by_relation[AssertionRelation.TARGETS.value])),
        "depends_on_facets": encoded(AssertionRelation.DEPENDS_ON.value),
        "self_dependency_facet_id": _facet_id(AssertionKind.DEPENDENCY, model.idea_id),
    }


def compile_hydration_plan(envelope: IdeaPortfolioHydrationEnvelope | dict[str, Any]) -> HydrationPlan:
    model = (
        envelope
        if isinstance(envelope, IdeaPortfolioHydrationEnvelope)
        else IdeaPortfolioHydrationEnvelope.model_validate(envelope)
    )
    records_payload = [record.model_dump(mode="json") for record in model.records]
    batch_digest = _sha256_text(_canonical_json(records_payload))
    parent = model.expected_graph_revision or "GENESIS"
    graph_revision = _sha256_text(
        f"ceg.idea-portfolio-graph/v1\x00{parent}\x00{model.source_snapshot_digest}\x00{batch_digest}"
    )
    return HydrationPlan(envelope=model, batch_digest=batch_digest, graph_revision=graph_revision)


def compile_upsert_command(
    projection: IdeaGraphProjection,
    *,
    graph_revision: str,
    tenant: str,
) -> WriteCommand:
    p_digest = projection_digest(projection)
    grouped: dict[str, list[dict[str, Any]]] = {relation.value: [] for relation in AssertionRelation}
    for assertion in compile_assertions(projection):
        grouped[assertion.relation].append(
            {
                "assertion_id": assertion.assertion_id,
                "facet_id": assertion.facet_id,
                "kind": assertion.kind,
                "key": assertion.key,
                "evidence_state": assertion.evidence_state,
                "source_refs_json": assertion.source_refs_json,
            }
        )

    cypher = """
MERGE (idea:Idea {idea_id: $idea_id})
SET idea.source_digest = $source_digest,
    idea.projection_digest = $projection_digest,
    idea.graph_revision = $graph_revision,
    idea.lifecycle_stage = $lifecycle_stage,
    idea.decision = $decision,
    idea.proof_state = $proof_state,
    idea.execution_state = $execution_state,
    idea.unknowns_json = $unknowns_json,
    idea.self_dependency_facet_id = $self_dependency_facet_id,
    idea.active = true,
    idea.hydrated_at = datetime(),
    idea.tombstoned_at = null,
    idea._tenant = $tenant
WITH idea
OPTIONAL MATCH (idea)-[old:PRODUCES|REQUIRES|TARGETS|USES|DEPENDS_ON]->(:PortfolioFacet)
DELETE old
WITH DISTINCT idea
CALL {
  WITH idea
  UNWIND $produces AS row
  MERGE (facet:PortfolioFacet {facet_id: row.facet_id})
  SET facet.kind = row.kind,
      facet.key = row.key,
      facet.last_seen_revision = $graph_revision,
      facet._tenant = $tenant
  MERGE (idea)-[rel:PRODUCES]->(facet)
  SET rel.assertion_id = row.assertion_id,
      rel.kind = row.kind,
      rel.evidence_state = row.evidence_state,
      rel.source_refs_json = row.source_refs_json,
      rel.projection_digest = $projection_digest,
      rel.graph_revision = $graph_revision
  RETURN count(row) AS produced_count
}
CALL {
  WITH idea
  UNWIND $requires AS row
  MERGE (facet:PortfolioFacet {facet_id: row.facet_id})
  SET facet.kind = row.kind,
      facet.key = row.key,
      facet.last_seen_revision = $graph_revision,
      facet._tenant = $tenant
  MERGE (idea)-[rel:REQUIRES]->(facet)
  SET rel.assertion_id = row.assertion_id,
      rel.kind = row.kind,
      rel.evidence_state = row.evidence_state,
      rel.source_refs_json = row.source_refs_json,
      rel.projection_digest = $projection_digest,
      rel.graph_revision = $graph_revision
  RETURN count(row) AS required_count
}
CALL {
  WITH idea
  UNWIND $targets AS row
  MERGE (facet:PortfolioFacet {facet_id: row.facet_id})
  SET facet.kind = row.kind,
      facet.key = row.key,
      facet.last_seen_revision = $graph_revision,
      facet._tenant = $tenant
  MERGE (idea)-[rel:TARGETS]->(facet)
  SET rel.assertion_id = row.assertion_id,
      rel.kind = row.kind,
      rel.evidence_state = row.evidence_state,
      rel.source_refs_json = row.source_refs_json,
      rel.projection_digest = $projection_digest,
      rel.graph_revision = $graph_revision
  RETURN count(row) AS target_count
}
CALL {
  WITH idea
  UNWIND $uses AS row
  MERGE (facet:PortfolioFacet {facet_id: row.facet_id})
  SET facet.kind = row.kind,
      facet.key = row.key,
      facet.last_seen_revision = $graph_revision,
      facet._tenant = $tenant
  MERGE (idea)-[rel:USES]->(facet)
  SET rel.assertion_id = row.assertion_id,
      rel.kind = row.kind,
      rel.evidence_state = row.evidence_state,
      rel.source_refs_json = row.source_refs_json,
      rel.projection_digest = $projection_digest,
      rel.graph_revision = $graph_revision
  RETURN count(row) AS use_count
}
CALL {
  WITH idea
  UNWIND $depends_on AS row
  MERGE (facet:PortfolioFacet {facet_id: row.facet_id})
  SET facet.kind = row.kind,
      facet.key = row.key,
      facet.last_seen_revision = $graph_revision,
      facet._tenant = $tenant
  MERGE (idea)-[rel:DEPENDS_ON]->(facet)
  SET rel.assertion_id = row.assertion_id,
      rel.kind = row.kind,
      rel.evidence_state = row.evidence_state,
      rel.source_refs_json = row.source_refs_json,
      rel.projection_digest = $projection_digest,
      rel.graph_revision = $graph_revision
  RETURN count(row) AS dependency_count
}
RETURN idea.idea_id AS idea_id,
       produced_count + required_count + target_count + use_count + dependency_count AS assertion_count
""".strip()

    return WriteCommand(
        cypher=cypher,
        parameters={
            "tenant": tenant,
            "idea_id": projection.idea_id,
            "source_digest": projection.source_digest,
            "projection_digest": p_digest,
            "graph_revision": graph_revision,
            "lifecycle_stage": projection.lifecycle.stage,
            "decision": projection.lifecycle.decision,
            "proof_state": projection.lifecycle.proof_state,
            "execution_state": projection.lifecycle.execution_state,
            "unknowns_json": _canonical_json(sorted(projection.unknowns)),
            "self_dependency_facet_id": _facet_id(AssertionKind.DEPENDENCY, projection.idea_id),
            "produces": grouped[AssertionRelation.PRODUCES.value],
            "requires": grouped[AssertionRelation.REQUIRES.value],
            "targets": grouped[AssertionRelation.TARGETS.value],
            "uses": grouped[AssertionRelation.USES.value],
            "depends_on": grouped[AssertionRelation.DEPENDS_ON.value],
        },
    )


def compile_tombstone_command(idea_id: str, *, graph_revision: str, tenant: str) -> WriteCommand:
    cypher = """
MERGE (idea:Idea {idea_id: $idea_id})
SET idea.active = false,
    idea.graph_revision = $graph_revision,
    idea.tombstoned_at = datetime(),
    idea._tenant = $tenant
WITH idea
OPTIONAL MATCH (idea)-[old:PRODUCES|REQUIRES|TARGETS|USES|DEPENDS_ON]->(:PortfolioFacet)
DELETE old
RETURN idea.idea_id AS idea_id
""".strip()
    return WriteCommand(
        cypher=cypher,
        parameters={"tenant": tenant, "idea_id": idea_id, "graph_revision": graph_revision},
    )


_ACQUIRE_HYDRATION_CYPHER = """
MERGE (state:IdeaPortfolioHydrationState {state_id: $state_id})
SET state._cas_lock = coalesce(state._cas_lock, 0) + 1
WITH state,
     state.current_revision AS current_revision,
     coalesce(state.in_progress, false) AS in_progress,
     state.target_revision AS target_revision
WHERE (current_revision = $graph_revision AND in_progress = false)
   OR (in_progress = true AND target_revision = $graph_revision)
   OR (
        in_progress = false
        AND (
          (current_revision IS NULL AND $expected_graph_revision IS NULL)
          OR current_revision = $expected_graph_revision
        )
      )
WITH state, current_revision, in_progress, target_revision,
     CASE
       WHEN current_revision = $graph_revision AND in_progress = false THEN 'reused'
       WHEN in_progress = true AND target_revision = $graph_revision THEN 'resume'
       ELSE 'start'
     END AS acquisition_status
FOREACH (_ IN CASE WHEN acquisition_status = 'start' THEN [1] ELSE [] END |
  SET state.in_progress = true,
      state.target_revision = $graph_revision,
      state.source_snapshot_ref = $source_snapshot_ref,
      state.source_snapshot_digest = $source_snapshot_digest,
      state.batch_digest = $batch_digest,
      state.started_at = datetime(),
      state.completed_at = null,
      state.last_error = null,
      state._tenant = $tenant
)
RETURN acquisition_status AS status, current_revision
""".strip()

_FINALIZE_HYDRATION_CYPHER = """
MATCH (state:IdeaPortfolioHydrationState {state_id: $state_id})
SET state._cas_lock = coalesce(state._cas_lock, 0) + 1
WITH state
WHERE state.in_progress = true AND state.target_revision = $graph_revision
SET state.current_revision = $graph_revision,
    state.in_progress = false,
    state.target_revision = null,
    state.completed_at = datetime(),
    state.last_error = null
RETURN state.current_revision AS graph_revision
""".strip()

_FAIL_HYDRATION_CYPHER = """
MATCH (state:IdeaPortfolioHydrationState {state_id: $state_id})
WHERE state.in_progress = true AND state.target_revision = $graph_revision
SET state.last_error = $error,
    state.last_error_at = datetime()
RETURN state.target_revision AS graph_revision
""".strip()


class IdeaPortfolioHydrator:
    """Apply one revision-chained IdeaOS corpus delta to the idea-portfolio graph."""

    def __init__(self, graph_writer: GraphWriter, *, tenant: str = DOMAIN_ID) -> None:
        self.graph_writer = graph_writer
        self.tenant = tenant

    async def apply(self, envelope: IdeaPortfolioHydrationEnvelope | dict[str, Any]) -> dict[str, Any]:
        plan = compile_hydration_plan(envelope)
        acquired = await self.graph_writer.execute_write(
            cypher=_ACQUIRE_HYDRATION_CYPHER,
            parameters={
                "state_id": _STATE_ID,
                "tenant": self.tenant,
                "graph_revision": plan.graph_revision,
                "expected_graph_revision": plan.envelope.expected_graph_revision,
                "source_snapshot_ref": plan.envelope.source_snapshot_ref,
                "source_snapshot_digest": plan.envelope.source_snapshot_digest,
                "batch_digest": plan.batch_digest,
            },
            database=DOMAIN_ID,
        )
        records = _write_records(acquired)
        if not records:
            raise IdeaPortfolioHydrationError(
                "hydration revision conflict or another revision is already in progress"
            )

        acquisition_status = records[0].get("status")
        if acquisition_status == "reused":
            return {
                "schema": "ceg.idea-portfolio-hydration-receipt/v1",
                "status": "reused",
                "graph_revision": plan.graph_revision,
                "batch_digest": plan.batch_digest,
                "source_snapshot_ref": plan.envelope.source_snapshot_ref,
                "source_snapshot_digest": plan.envelope.source_snapshot_digest,
                "applied": [],
                "tombstoned": [],
            }

        applied: list[str] = []
        tombstoned: list[str] = []
        try:
            for record in plan.envelope.records:
                if record.operation == "upsert":
                    assert record.projection is not None
                    command = compile_upsert_command(
                        record.projection,
                        graph_revision=plan.graph_revision,
                        tenant=self.tenant,
                    )
                    await self.graph_writer.execute_write(
                        cypher=command.cypher,
                        parameters=command.parameters,
                        database=DOMAIN_ID,
                    )
                    applied.append(record.projection.idea_id)
                else:
                    command = compile_tombstone_command(
                        record.resolved_idea_id,
                        graph_revision=plan.graph_revision,
                        tenant=self.tenant,
                    )
                    await self.graph_writer.execute_write(
                        cypher=command.cypher,
                        parameters=command.parameters,
                        database=DOMAIN_ID,
                    )
                    tombstoned.append(record.resolved_idea_id)
        except Exception as exc:
            await self.graph_writer.execute_write(
                cypher=_FAIL_HYDRATION_CYPHER,
                parameters={
                    "state_id": _STATE_ID,
                    "graph_revision": plan.graph_revision,
                    "error": type(exc).__name__,
                },
                database=DOMAIN_ID,
            )
            raise

        finalized = await self.graph_writer.execute_write(
            cypher=_FINALIZE_HYDRATION_CYPHER,
            parameters={"state_id": _STATE_ID, "graph_revision": plan.graph_revision},
            database=DOMAIN_ID,
        )
        if not _write_records(finalized):
            raise IdeaPortfolioHydrationError("hydration applied but graph revision finalization failed")

        return {
            "schema": "ceg.idea-portfolio-hydration-receipt/v1",
            "status": "applied" if acquisition_status == "start" else "resumed",
            "graph_revision": plan.graph_revision,
            "batch_digest": plan.batch_digest,
            "source_snapshot_ref": plan.envelope.source_snapshot_ref,
            "source_snapshot_digest": plan.envelope.source_snapshot_digest,
            "applied": applied,
            "tombstoned": tombstoned,
        }


def _write_records(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        records = result.get("records", [])
        return [dict(record) for record in records]
    return []


__all__ = [
    "AssertionKind",
    "AssertionRelation",
    "DOMAIN_ID",
    "EvidenceState",
    "HydrationPlan",
    "IdeaGraphProjection",
    "IdeaPortfolioHydrationEnvelope",
    "IdeaPortfolioHydrationError",
    "IdeaPortfolioHydrator",
    "IdeaPortfolioSyncRecord",
    "WriteCommand",
    "build_portfolio_match_query",
    "compile_assertions",
    "compile_hydration_plan",
    "compile_tombstone_command",
    "compile_upsert_command",
    "projection_digest",
]
