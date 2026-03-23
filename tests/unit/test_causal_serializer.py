"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [test]
tags: [test, unit, causal, serializer, bfs]
owner: engine-team
status: active
--- /L9_META ---

Tests for engine.causal.serializer — CausalSubgraphSerializer.

Covers:
- BFS traversal returns serialized string
- Empty neighborhood returns empty result
- Correct node/edge counting
- Error handling on query failure
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from engine.causal.serializer import CausalSubgraphSerializer
from engine.config.schema import (
    CausalEdgeSpec,
    CausalSubgraphSpec,
    DomainSpec,
)


def _spec_with_causal(enabled: bool = True) -> DomainSpec:
    return DomainSpec(
        domain={"id": "test", "name": "Test", "version": "0.0.1"},
        ontology={
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "facility_id", "type": "int", "required": True}],
                },
                {
                    "label": "Query",
                    "managedby": "api",
                    "queryentity": True,
                    "matchdirection": "d1",
                    "properties": [{"name": "query_id", "type": "int", "required": True}],
                },
                {
                    "label": "TransactionOutcome",
                    "managedby": "api",
                    "auxiliary": True,
                    "properties": [{"name": "outcome_id", "type": "string"}],
                },
            ],
            "edges": [
                {
                    "type": "TRANSACTED_WITH",
                    "from": "Facility",
                    "to": "Facility",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "sync",
                },
                {
                    "type": "RESULTED_IN",
                    "from": "Facility",
                    "to": "TransactionOutcome",
                    "direction": "DIRECTED",
                    "category": "transaction",
                    "managedby": "api",
                },
            ],
        },
        matchentities={
            "candidate": [{"label": "Facility", "matchdirection": "d1"}],
            "queryentity": [{"label": "Query", "matchdirection": "d1"}],
        },
        queryschema={"matchdirections": ["d1"], "fields": []},
        gates=[],
        scoring={"dimensions": []},
        causal=CausalSubgraphSpec(
            enabled=enabled,
            causal_edges=[
                CausalEdgeSpec(
                    edge_type="RESULTED_IN",
                    source_label="Facility",
                    target_label="TransactionOutcome",
                ),
            ],
            chain_depth_limit=3,
        ),
    )


class TestCausalSubgraphSerializer:
    """Tests for BFS serialization."""

    @pytest.mark.asyncio
    async def test_serialize_returns_path_string(self) -> None:
        spec = _spec_with_causal()
        driver = AsyncMock()
        serializer = CausalSubgraphSerializer(driver, spec)

        driver.execute_query = AsyncMock(
            return_value=[
                {
                    "path_nodes": [
                        {"id": "F-1", "label": "Facility", "name": "Plant A"},
                        {"id": "TO-1", "label": "TransactionOutcome", "name": "TO-1"},
                    ],
                    "path_rels": [
                        {"type": "RESULTED_IN", "confidence": 0.9},
                    ],
                    "depth": 1,
                }
            ]
        )

        result = await serializer.serialize_neighborhood("F-1", "Facility")
        assert result["nodes_visited"] == 2
        assert "RESULTED_IN" in result["edges_traversed"]
        assert result["depth_reached"] == 1
        assert "Facility[Plant A]" in result["serialized"]
        assert "RESULTED_IN" in result["serialized"]

    @pytest.mark.asyncio
    async def test_empty_neighborhood(self) -> None:
        spec = _spec_with_causal()
        driver = AsyncMock()
        serializer = CausalSubgraphSerializer(driver, spec)

        driver.execute_query = AsyncMock(return_value=[])

        result = await serializer.serialize_neighborhood("F-999", "Facility")
        assert result["serialized"] == ""
        assert result["nodes_visited"] == 0
        assert result["edges_traversed"] == []
        assert result["depth_reached"] == 0

    @pytest.mark.asyncio
    async def test_query_failure_returns_empty(self) -> None:
        spec = _spec_with_causal()
        driver = AsyncMock()
        serializer = CausalSubgraphSerializer(driver, spec)

        driver.execute_query = AsyncMock(side_effect=Exception("Neo4j connection lost"))

        result = await serializer.serialize_neighborhood("F-1", "Facility")
        assert result["serialized"] == ""
        assert result["nodes_visited"] == 0

    @pytest.mark.asyncio
    async def test_multi_hop_path(self) -> None:
        spec = _spec_with_causal()
        driver = AsyncMock()
        serializer = CausalSubgraphSerializer(driver, spec)

        driver.execute_query = AsyncMock(
            return_value=[
                {
                    "path_nodes": [
                        {"id": "F-1", "label": "Facility", "name": "Plant A"},
                        {"id": "TO-1", "label": "TransactionOutcome", "name": "TO-1"},
                    ],
                    "path_rels": [{"type": "RESULTED_IN", "confidence": 0.9}],
                    "depth": 1,
                },
                {
                    "path_nodes": [
                        {"id": "F-1", "label": "Facility", "name": "Plant A"},
                        {"id": "F-2", "label": "Facility", "name": "Plant B"},
                    ],
                    "path_rels": [{"type": "RESULTED_IN", "confidence": 0.7}],
                    "depth": 1,
                },
            ]
        )

        result = await serializer.serialize_neighborhood("F-1", "Facility", max_depth=2)
        assert result["nodes_visited"] >= 2
        assert result["depth_reached"] == 1
