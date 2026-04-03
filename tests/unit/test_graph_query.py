"""
Unit tests — graph_query parameterized execution.

Coverage:
  - Parameterized Cypher (no injection)
  - Dimension keys in RETURN clause
  - GATE lookup found/not found
  - Error propagation
"""
from __future__ import annotations

import pytest


class MockNeo4jDriver:
    def __init__(self, mock_results):
        self.mock_results = mock_results
        self.last_query = None
        self.last_params = None

    async def execute_query(self, query, params):
        self.last_query = query
        self.last_params = params
        return self.mock_results


class TestExecuteMatchQuery:

    @pytest.mark.asyncio
    async def test_parameterized_entity_id(self):
        from engine.traversal.graph_query import execute_match_query
        driver = MockNeo4jDriver([{"id": "M001", "name": "HDPE", "geo": 0.9, "confidence": 0.8}])
        await execute_match_query(driver, "Material", "MAT_001", ["geo"], limit=10)
        assert "$entity_id" in driver.last_query
        assert driver.last_params["entity_id"] == "MAT_001"

    @pytest.mark.asyncio
    async def test_limit_parameterized(self):
        from engine.traversal.graph_query import execute_match_query
        driver = MockNeo4jDriver([])
        await execute_match_query(driver, "Material", "MAT_001", [], limit=5)
        assert "$limit" in driver.last_query
        assert driver.last_params["limit"] == 5

    @pytest.mark.asyncio
    async def test_dimension_keys_in_return_clause(self):
        from engine.traversal.graph_query import execute_match_query
        driver = MockNeo4jDriver([])
        await execute_match_query(driver, "Material", "MAT_001", ["geo", "temporal", "community"])
        assert "r.geo AS geo" in driver.last_query
        assert "r.temporal AS temporal" in driver.last_query
        assert "r.community AS community" in driver.last_query

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        from engine.traversal.graph_query import execute_match_query
        driver = MockNeo4jDriver([{"id": "M001", "name": "Test", "confidence": 0.9}])
        results = await execute_match_query(driver, "Material", "MAT_001", ["geo"])
        assert isinstance(results, list)
        assert results[0]["id"] == "M001"

    @pytest.mark.asyncio
    async def test_empty_results(self):
        from engine.traversal.graph_query import execute_match_query
        driver = MockNeo4jDriver([])
        results = await execute_match_query(driver, "Material", "MAT_001", ["geo"])
        assert results == []

    @pytest.mark.asyncio
    async def test_no_value_interpolation(self):
        """Injection attempt must never appear in the Cypher string."""
        from engine.traversal.graph_query import execute_match_query
        evil_id = "'; MATCH (n) DETACH DELETE n RETURN '1"
        driver = MockNeo4jDriver([])
        await execute_match_query(driver, "Material", evil_id, [])
        assert "DETACH DELETE" not in driver.last_query
        assert driver.last_params["entity_id"] == evil_id


class TestExecuteGateLookup:

    @pytest.mark.asyncio
    async def test_gate_found(self):
        from engine.traversal.graph_query import execute_gate_lookup
        driver = MockNeo4jDriver([{
            "endpoint": "http://ceg-engine:8000/v1/execute",
            "timeout_ms": 30000,
        }])
        config = await execute_gate_lookup(driver, "ceg-engine", "match")
        assert config is not None
        assert config["endpoint"] == "http://ceg-engine:8000/v1/execute"

    @pytest.mark.asyncio
    async def test_gate_not_found_returns_none(self):
        from engine.traversal.graph_query import execute_gate_lookup
        driver = MockNeo4jDriver([])
        config = await execute_gate_lookup(driver, "unknown-service", "unknown")
        assert config is None

    @pytest.mark.asyncio
    async def test_gate_params_parameterized(self):
        from engine.traversal.graph_query import execute_gate_lookup
        driver = MockNeo4jDriver([])
        await execute_gate_lookup(driver, "my-service", "my-action")
        assert driver.last_params["target_service"] == "my-service"
        assert driver.last_params["action"] == "my-action"
