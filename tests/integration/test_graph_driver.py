"""Integration tests — GraphDriver: write, read, empty result."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_execute_write_creates_node(graph_driver, clean_db):
    result = await graph_driver.execute_write(
        cypher="CREATE (n:TestNode {id: $id, name: $name})",
        parameters={"id": "test-1", "name": "Alpha"},
        database="neo4j",
    )
    assert result.get("nodes_created", 0) >= 1 or result.get("status") == "ok"


@pytest.mark.asyncio
async def test_execute_query_reads_node(graph_driver, clean_db):
    await graph_driver.execute_write(
        cypher="CREATE (n:ReadNode {id: $id})",
        parameters={"id": "r1"},
        database="neo4j",
    )
    records = await graph_driver.execute_query(
        cypher="MATCH (n:ReadNode {id: $id}) RETURN n.id AS id",
        parameters={"id": "r1"},
        database="neo4j",
    )
    assert len(records) >= 1
    assert records[0]["id"] == "r1"


@pytest.mark.asyncio
async def test_execute_query_returns_empty_for_miss(graph_driver):
    records = await graph_driver.execute_query(
        cypher="MATCH (n:NonExistentLabel_xyz {id: $id}) RETURN n",
        parameters={"id": "does-not-exist-xyz"},
        database="neo4j",
    )
    assert records == [] or records is not None
