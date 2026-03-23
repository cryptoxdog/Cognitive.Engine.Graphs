"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, handlers]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine/handlers.py - all 6 action handlers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from engine.handlers import (
    ValidationError,
    handle_admin,
    handle_health,
    handle_match,
    handle_outcomes,
    handle_resolve,
    handle_sync,
    init_dependencies,
)


def _make_domain_spec() -> MagicMock:
    spec = MagicMock()
    spec.domain.id = "test_domain"
    spec.domain.name = "Test"
    spec.domain.version = "1.0"

    gate = MagicMock()
    gate.matchdirections = None
    gate.candidateprop = "grade"
    gate.queryparam = "min_grade"
    gate.name = "grade_gate"
    spec.gates = [gate]

    candidate = MagicMock()
    candidate.label = "Facility"
    candidate.matchdirection = "buyer_to_seller"
    spec.matchentities.candidate = [candidate]

    step = MagicMock()
    step.matchdirections = None
    step.required = True
    step.pattern = "(candidate)-[:ACCEPTS]->(mat)"
    step.name = "taxonomy"
    spec.traversal.steps = [step]

    dim = MagicMock()
    dim.matchdirections = None
    dim.name = "structural"
    dim.weightkey = "structural"
    dim.defaultweight = 0.4
    spec.scoring.dimensions = [dim]

    spec.derivedparameters = []
    spec.compliance = None

    endpoint = MagicMock()
    endpoint.path = "/v1/sync/facility"
    endpoint.batchstrategy = "UNWINDMERGE"
    endpoint.targetnode = "Facility"
    endpoint.idproperty = "facility_id"
    endpoint.taxonomyedges = []
    endpoint.childsync = []
    spec.sync.endpoints = [endpoint]

    spec.gdsjobs = []

    node = MagicMock()
    node.label = "Facility"
    prop = MagicMock()
    prop.name = "facility_id"
    prop.required = True
    node.properties = [prop]
    spec.ontology.nodes = [node]

    return spec


@pytest.fixture(autouse=True)
def _inject_deps() -> None:
    mock_driver = AsyncMock()
    mock_driver.execute_query = AsyncMock(return_value=[])
    mock_loader = MagicMock()
    mock_loader.load_domain = MagicMock(return_value=_make_domain_spec())
    mock_loader.list_domains = MagicMock(return_value=["plasticos", "mortgage"])
    init_dependencies(mock_driver, mock_loader)


@pytest.mark.asyncio
async def test_match_returns_structure() -> None:
    result = await handle_match(
        "t",
        {
            "query": {"polymer": "HDPE"},
            "match_direction": "buyer_to_seller",
        },
    )
    assert "candidates" in result
    assert "query_id" in result
    assert isinstance(result["execution_time_ms"], float)


@pytest.mark.asyncio
async def test_match_missing_query() -> None:
    with pytest.raises(ValidationError, match="query"):
        await handle_match("t", {"match_direction": "buyer_to_seller"})


@pytest.mark.asyncio
async def test_match_missing_direction() -> None:
    with pytest.raises(ValidationError, match="match_direction"):
        await handle_match("t", {"query": {}})


@pytest.mark.asyncio
async def test_match_bad_direction() -> None:
    with pytest.raises(ValidationError, match="No candidate entity"):
        await handle_match("t", {"query": {}, "match_direction": "nonexistent"})


@pytest.mark.asyncio
async def test_sync_success() -> None:
    result = await handle_sync(
        "t",
        {
            "entity_type": "facility",
            "batch": [{"facility_id": "F1"}],
        },
    )
    assert result["status"] == "success"
    assert result["synced_count"] == 1


@pytest.mark.asyncio
async def test_sync_empty_batch() -> None:
    with pytest.raises(ValidationError, match="non-empty"):
        await handle_sync("t", {"entity_type": "facility", "batch": []})


@pytest.mark.asyncio
async def test_sync_unknown_entity() -> None:
    with pytest.raises(ValidationError, match="No sync endpoint"):
        await handle_sync("t", {"entity_type": "bogus", "batch": [{"id": 1}]})


@pytest.mark.asyncio
async def test_admin_list_domains() -> None:
    result = await handle_admin("t", {"subaction": "list_domains"})
    assert "plasticos" in result["domains"]


@pytest.mark.asyncio
async def test_admin_get_domain() -> None:
    result = await handle_admin("t", {"subaction": "get_domain", "domain_id": "plasticos"})
    assert "domain" in result


@pytest.mark.asyncio
async def test_admin_init_schema() -> None:
    result = await handle_admin("t", {"subaction": "init_schema", "domain_id": "plasticos"})
    assert result["status"] == "schema_initialized"


@pytest.mark.asyncio
async def test_admin_unknown_subaction() -> None:
    with pytest.raises(ValidationError, match="Unknown admin subaction"):
        await handle_admin("t", {"subaction": "drop_everything"})


@pytest.mark.asyncio
async def test_outcomes_success() -> None:
    result = await handle_outcomes(
        "t",
        {
            "match_id": "q_abc",
            "candidate_id": "F42",
            "outcome": "success",
        },
    )
    assert result["status"] == "recorded"
    assert result["outcome_id"].startswith("out_")


@pytest.mark.asyncio
async def test_outcomes_invalid_outcome() -> None:
    with pytest.raises(ValidationError, match="Invalid outcome"):
        await handle_outcomes(
            "t",
            {
                "match_id": "q_abc",
                "candidate_id": "F42",
                "outcome": "maybe",
            },
        )


@pytest.mark.asyncio
async def test_resolve_success() -> None:
    result = await handle_resolve(
        "t",
        {
            "entity_type": "MaterialProfile",
            "source_id": "MP1",
            "target_id": "MP2",
            "confidence": 0.95,
            "signal": "llm_consensus",
        },
    )
    assert result["status"] == "resolved"
    assert result["resolution_id"].startswith("res_")


@pytest.mark.asyncio
async def test_resolve_missing_field() -> None:
    with pytest.raises(ValidationError, match="source_id"):
        await handle_resolve("t", {"entity_type": "MP", "target_id": "MP2"})


@pytest.mark.asyncio
async def test_health_ok() -> None:
    result = await handle_health("t", {})
    assert result["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_degraded() -> None:
    from engine.state import get_state

    state = get_state()
    state.graph_driver.execute_query = AsyncMock(side_effect=ConnectionError("refused"))
    result = await handle_health("t", {})
    assert result["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_neo4j_ok_domain_missing_tenant_but_packs_available() -> None:
    """Health is degraded (not errored) when tenant spec is absent but other packs exist."""
    from engine.config.loader import DomainNotFoundError
    from engine.state import get_state

    state = get_state()
    state.graph_driver.execute_query = AsyncMock(return_value=None)
    state.domain_loader.load_domain = MagicMock(side_effect=DomainNotFoundError("not found"))
    state.domain_loader.list_domains = MagicMock(return_value=["plasticos"])

    result = await handle_health("unknown-tenant", {})

    assert result["status"] == "degraded"
    assert "neo4j" in result["checks"]
    assert result["checks"]["neo4j"] == "ok"
    assert "tenant not found" in result["checks"]["domain_spec"]
    assert "plasticos" in result["checks"]["domain_spec"]


@pytest.mark.asyncio
async def test_health_neo4j_ok_no_domains_at_all() -> None:
    """Health is degraded when no domain packs are configured."""
    from engine.config.loader import DomainNotFoundError
    from engine.state import get_state

    state = get_state()
    state.graph_driver.execute_query = AsyncMock(return_value=None)
    state.domain_loader.load_domain = MagicMock(side_effect=DomainNotFoundError("not found"))
    state.domain_loader.list_domains = MagicMock(return_value=[])

    result = await handle_health("plasticos", {})

    assert result["status"] == "degraded"
    assert result["checks"]["domain_spec"] == "error: no_domains_found"


@pytest.mark.asyncio
async def test_health_neo4j_connection_failed() -> None:
    """Neo4j unreachable reports degraded with connection_failed check."""
    from engine.state import get_state

    state = get_state()
    state.graph_driver.execute_query = AsyncMock(side_effect=OSError("refused"))

    result = await handle_health("plasticos", {})

    assert result["status"] == "degraded"
    assert result["checks"]["neo4j"] == "error: connection_failed"
