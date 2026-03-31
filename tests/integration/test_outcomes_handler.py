"""Integration tests — outcomes handler: SUCCEEDED, REJECTED, validation."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_outcome_success_recorded(graph_driver, clean_db):
    await graph_driver.execute_write(
        cypher="MERGE (a:Facility {id: $aid}) MERGE (b:Facility {id: $bid})",
        parameters={"aid": "match-001", "bid": "cand-001"},
        database="neo4j",
    )
    from engine.handlers import handle_outcomes
    result = await handle_outcomes(
        "plasticos",
        {
            "match_id": "match-001",
            "candidate_id": "cand-001",
            "was_selected": True,
            "dimension_scores": {"geo_proximity": 0.85},
        },
        graph_driver,
    )
    assert result.get("status") in ("ok", "success", "recorded")


@pytest.mark.asyncio
async def test_outcome_rejected_recorded(graph_driver, clean_db):
    await graph_driver.execute_write(
        cypher="MERGE (a:Facility {id: $aid}) MERGE (b:Facility {id: $bid})",
        parameters={"aid": "match-002", "bid": "cand-002"},
        database="neo4j",
    )
    from engine.handlers import handle_outcomes
    result = await handle_outcomes(
        "plasticos",
        {
            "match_id": "match-002",
            "candidate_id": "cand-002",
            "was_selected": False,
            "reason_code": "contamination_too_high",
        },
        graph_driver,
    )
    assert result.get("status") in ("ok", "success", "recorded")


def test_outcome_invalid_payload_raises():
    try:
        from engine.models.payloads import OutcomePayload
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            OutcomePayload.model_validate({"was_selected": "yes_please"})
    except ImportError:
        pytest.skip("OutcomePayload not available in this version")
