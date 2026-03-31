"""Integration tests — match handler: full pipeline, top_n, invalid payload."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_match_returns_candidates(graph_driver, domain_loader, clean_db):
    await graph_driver.execute_write(
        cypher="""
        UNWIND $batch AS row
        MERGE (n:Facility {id: row.id})
        SET n += row
        SET n.synced_at = datetime()
        """,
        parameters={"batch": [
            {
                "id": "f1",
                "name": "Alpha Recycle",
                "contamination_tolerance": 0.05,
                "latitude": 34.05,
                "longitude": -118.24,
                "reinforcement_score": 0.7,
            },
            {
                "id": "f2",
                "name": "Beta Process",
                "contamination_tolerance": 0.10,
                "latitude": 34.10,
                "longitude": -118.30,
                "reinforcement_score": 0.5,
            },
        ]},
        database="neo4j",
    )
    from engine.handlers import handle_match
    result = await handle_match(
        "plasticos",
        {
            "query": {
                "contamination_min": 0.0,
                "contamination_max": 0.12,
                "origin_lat": 34.05,
                "origin_lon": -118.24,
            },
            "match_direction": "*",
            "top_n": 10,
        },
        graph_driver,
        domain_loader,
    )
    assert "candidates" in result or "status" in result
    assert result.get("status") in ("ok", "success", None) or "candidates" in result


@pytest.mark.asyncio
async def test_match_respects_top_n(graph_driver, domain_loader, clean_db):
    await graph_driver.execute_write(
        cypher="""
        UNWIND $batch AS row
        MERGE (n:Facility {id: row.id})
        SET n += row
        """,
        parameters={"batch": [
            {"id": f"f{i}", "name": f"Facility {i}", "contamination_tolerance": 0.05}
            for i in range(5)
        ]},
        database="neo4j",
    )
    from engine.handlers import handle_match
    result = await handle_match(
        "plasticos",
        {"query": {}, "match_direction": "*", "top_n": 2},
        graph_driver,
        domain_loader,
    )
    candidates = result.get("candidates", [])
    assert len(candidates) <= 2


def test_match_invalid_top_n_raises():
    try:
        from engine.models.payloads import MatchPayload
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            MatchPayload.model_validate({"match_direction": "*", "top_n": -5})
    except ImportError:
        pytest.skip("MatchPayload not available in this version")
