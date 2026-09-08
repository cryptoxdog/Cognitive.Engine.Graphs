from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from engine.config.loader import DomainPackLoader
from engine.gates.compiler import GateCompiler
from engine.scoring.assembler import ScoringAssembler
from engine.sync.idea_portfolio import (
    IdeaGraphProjection,
    IdeaPortfolioHydrationError,
    IdeaPortfolioHydrator,
    build_portfolio_match_query,
    compile_hydration_plan,
    compile_upsert_command,
    projection_digest,
)

ROOT = Path(__file__).resolve().parents[2]


def _digest(char: str = "a") -> str:
    return "sha256:" + char * 64


def _projection(idea_id: str = "idea-alpha") -> dict[str, Any]:
    return {
        "schema": "ideaos.idea-graph-projection/v1",
        "idea_id": idea_id,
        "source_refs": [f"Ideas/{idea_id}.md"],
        "source_digest": _digest("a"),
        "lifecycle": {
            "stage": "expanded",
            "decision": None,
            "proof_state": "P1",
            "execution_state": None,
        },
        "assertions": [
            {
                "kind": "capability",
                "relation": "produces",
                "key": "shared-capability",
                "evidence_state": "VERIFIED",
                "source_refs": [f"Ideas/{idea_id}.md#capability"],
            },
            {
                "kind": "capability",
                "relation": "requires",
                "key": "required-capability",
                "evidence_state": "SUPPORTED_INFERENCE",
                "source_refs": [f"Ideas/{idea_id}.md#requirement"],
            },
            {
                "kind": "substrate",
                "relation": "uses",
                "key": "shared-substrate",
                "evidence_state": "VERIFIED",
                "source_refs": [f"Ideas/{idea_id}.md#substrate"],
            },
            {
                "kind": "market",
                "relation": "targets",
                "key": "industrial-ai",
                "evidence_state": "HYPOTHESIS",
                "source_refs": [f"Ideas/{idea_id}.md#market"],
            },
            {
                "kind": "dependency",
                "relation": "depends_on",
                "key": "idea-foundation",
                "evidence_state": "VERIFIED",
                "source_refs": [f"Ideas/{idea_id}.md#dependency"],
            },
        ],
        "unknowns": ["external demand not yet proven"],
    }


def _envelope(*, expected: str | None = None) -> dict[str, Any]:
    return {
        "schema": "ceg.idea-portfolio-hydration/v1",
        "source_snapshot_ref": "Quantum-L9/IdeaOS@deadbeef",
        "source_snapshot_digest": _digest("b"),
        "expected_graph_revision": expected,
        "records": [
            {
                "schema": "ceg.idea-portfolio-sync-record/v1",
                "operation": "upsert",
                "projection": _projection(),
            }
        ],
    }


@pytest.mark.unit
class TestIdeaPortfolioDomain:
    def test_domain_loads_and_compilers_accept_it(self) -> None:
        loader = DomainPackLoader(config_path=str(ROOT / "domains"))
        spec = loader.load_domain("idea-portfolio")

        assert spec.domain.id == "idea-portfolio"
        assert {node.label for node in spec.ontology.nodes} == {"Idea", "IdeaQuery", "PortfolioFacet"}
        assert {edge.type for edge in spec.ontology.edges} == {
            "PRODUCES",
            "REQUIRES",
            "TARGETS",
            "USES",
            "DEPENDS_ON",
        }
        assert sum(d.defaultweight for d in spec.scoring.dimensions) == pytest.approx(1.0)

        gate_clause = GateCompiler(spec).compile_all_gates("portfolio_context_for_idea")
        assert "candidate.active" in gate_clause
        assert "candidate.idea_id != $idea_id" in gate_clause

        score_clause, _ = ScoringAssembler(spec).assemble_scoring_clause(
            "portfolio_context_for_idea", {}
        )
        assert "PRODUCES" in score_clause
        assert "REQUIRES" in score_clause
        assert "PortfolioFacet" in score_clause


@pytest.mark.unit
class TestProjectionBoundary:
    def test_projection_compiles_to_flat_match_query(self) -> None:
        projection = IdeaGraphProjection.model_validate(_projection())
        query = build_portfolio_match_query(projection)

        assert query["idea_id"] == "idea-alpha"
        assert query["requires_count"] == 1
        assert query["produces_count"] == 1
        assert query["uses_count"] == 1
        assert query["targets_count"] == 1
        assert query["depends_on_facets"].startswith("|facet:")
        assert query["self_dependency_facet_id"].startswith("facet:")

    def test_invalid_kind_relation_is_rejected(self) -> None:
        raw = _projection()
        raw["assertions"][0]["kind"] = "market"
        raw["assertions"][0]["relation"] = "produces"

        with pytest.raises(ValueError, match="not valid for assertion kind"):
            IdeaGraphProjection.model_validate(raw)

    def test_non_unknown_assertion_requires_source_reference(self) -> None:
        raw = _projection()
        raw["assertions"][0]["source_refs"] = []

        with pytest.raises(ValueError, match="require at least one source_ref"):
            IdeaGraphProjection.model_validate(raw)

    def test_duplicate_semantic_assertion_is_rejected(self) -> None:
        raw = _projection()
        raw["assertions"].append(dict(raw["assertions"][0]))

        with pytest.raises(ValueError, match="duplicate semantic assertions"):
            IdeaGraphProjection.model_validate(raw)

    def test_upsert_replaces_source_projection_edges(self) -> None:
        projection = IdeaGraphProjection.model_validate(_projection())
        command = compile_upsert_command(projection, graph_revision=_digest("c"), tenant="idea-portfolio")

        assert "DELETE old" in command.cypher
        assert "MERGE (idea)-[rel:PRODUCES]->(facet)" in command.cypher
        assert "rel.evidence_state" in command.cypher
        assert command.parameters["projection_digest"] == projection_digest(projection)
        assert command.parameters["unknowns_json"] == '["external demand not yet proven"]'


@pytest.mark.unit
class TestHydrationRevision:
    def test_revision_is_deterministic_and_parent_linked(self) -> None:
        first = compile_hydration_plan(_envelope())
        again = compile_hydration_plan(_envelope())
        child = compile_hydration_plan(_envelope(expected=first.graph_revision))

        assert first.batch_digest == again.batch_digest
        assert first.graph_revision == again.graph_revision
        assert child.graph_revision != first.graph_revision


class _FakeWriter:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def execute_write(
        self,
        transaction_function: Any = None,
        *args: Any,
        cypher: str | None = None,
        parameters: dict[str, Any] | None = None,
        database: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append({"cypher": cypher, "parameters": parameters, "database": database})
        if not self.responses:
            return {"records": []}
        return self.responses.pop(0)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hydrator_applies_then_finalizes_revision() -> None:
    writer = _FakeWriter(
        [
            {"records": [{"status": "start", "current_revision": None}]},
            {"records": [{"idea_id": "idea-alpha", "assertion_count": 5}]},
            {"records": [{"graph_revision": _digest("d")}]},
        ]
    )
    hydrator = IdeaPortfolioHydrator(writer)

    receipt = await hydrator.apply(_envelope())

    assert receipt["status"] == "applied"
    assert receipt["applied"] == ["idea-alpha"]
    assert len(writer.calls) == 3
    assert all(call["database"] == "idea-portfolio" for call in writer.calls)
    assert "IdeaPortfolioHydrationState" in str(writer.calls[0]["cypher"])
    assert "MERGE (idea:Idea" in str(writer.calls[1]["cypher"])
    assert "state.current_revision" in str(writer.calls[2]["cypher"])


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hydrator_exact_revision_replay_is_noop() -> None:
    writer = _FakeWriter([{"records": [{"status": "reused", "current_revision": _digest("e")}] }])
    hydrator = IdeaPortfolioHydrator(writer)

    receipt = await hydrator.apply(_envelope())

    assert receipt["status"] == "reused"
    assert receipt["applied"] == []
    assert len(writer.calls) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_hydrator_rejects_revision_conflict_before_projection_write() -> None:
    writer = _FakeWriter([{"records": []}])
    hydrator = IdeaPortfolioHydrator(writer)

    with pytest.raises(IdeaPortfolioHydrationError, match="revision conflict"):
        await hydrator.apply(_envelope())

    assert len(writer.calls) == 1
