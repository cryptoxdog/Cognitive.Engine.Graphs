"""
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [test]
tags: [L9_TEMPLATE, test, fixtures]
owner: platform
status: active
--- /L9_META ---

tests/conftest.py — Shared pytest fixtures.

RULE 9 (L9 Contract): paths MUST be absolute, repo-rooted, never relative to __file__ dir.
RULE 7 (L9 Contract): DomainPackLoader is instantiated with
    DomainPackLoader(domains_dir=DOMAINS_DIR)
    matching the EXACT signature in L9_CONTRACT_SPECIFICATIONS.md §2.

DOMAINS_DIR uses Path(__file__).parent.parent to resolve
from tests/ → repo root → domains/.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# ── RULE 9: absolute, repo-rooted path — never relative to __file__ dir ───────
DOMAINS_DIR: Path = Path(__file__).parent.parent / "domains"


# ── Event Loop ─────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Neo4j Testcontainer ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def neo4j_container():
    """
    Session-scoped Neo4j testcontainer.
    Falls back to NEO4J_TEST_URI env var if testcontainers unavailable.
    """
    uri = os.getenv("NEO4J_TEST_URI")
    user = os.getenv("NEO4J_TEST_USER", "neo4j")
    password = os.getenv("NEO4J_TEST_PASSWORD", "l9-test-password")

    if uri:
        yield {"uri": uri, "user": user, "password": password}
        return

    try:
        from testcontainers.neo4j import Neo4jContainer

        container = Neo4jContainer(image="neo4j:5.18-enterprise")
        container.with_env("NEO4J_ACCEPT_LICENSE_AGREEMENT", "yes")
        container.with_env("NEO4JLABS_PLUGINS", '["graph-data-science"]')
        container.start()

        yield {
            "uri": container.get_connection_url(),
            "user": "neo4j",
            "password": "password",
        }
        container.stop()

    except ImportError:
        pytest.skip("testcontainers not installed and NEO4J_TEST_URI not set")


# ── Graph Driver ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
async def graph_driver(neo4j_container) -> AsyncGenerator:
    """
    Session-scoped async Neo4j driver.

    Includes a smoke write that proves the driver is live before any test runs.
    If this fails the entire session fails immediately — no false coverage.
    """
    from engine.graph.driver import GraphDriver

    driver = GraphDriver(
        uri=neo4j_container["uri"],
        username=neo4j_container["user"],
        password=neo4j_container["password"],
    )
    await driver.connect()

    # ── Smoke write: proves driver is live before any test runs ────────────────
    result = await driver.execute_write(
        cypher="CREATE (n:_SmokeTest {id: $id}) RETURN n",
        parameters={"id": "smoke-probe"},
        database="neo4j",
    )
    assert result.get("nodes_created", 0) == 1, f"Smoke write failed — Neo4j driver not live. Result: {result}"
    # Clean up smoke node
    await driver.execute_write(
        cypher="MATCH (n:_SmokeTest) DETACH DELETE n",
        parameters={},
        database="neo4j",
    )

    yield driver
    await driver.close()


# ── DomainPackLoader ───────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def domain_loader():
    """Session-scoped domain loader — RULE 7: exact signature."""
    from engine.config.loader import DomainPackLoader

    return DomainPackLoader(domains_dir=DOMAINS_DIR)


# ── Domain Spec ────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def domain_spec(domain_loader):
    """Loaded and validated PlasticOS DomainSpec."""
    return domain_loader.load_domain("plasticos")


@pytest.fixture
def minimal_domain_spec():
    """Minimal in-memory domain spec for unit tests that don't need full YAML."""
    from engine.config.schema import DomainSpec

    raw = {
        "domain": {"id": "test", "name": "Test Domain", "version": "0.0.1"},
        "ontology": {
            "nodes": [
                {
                    "label": "Facility",
                    "managedby": "sync",
                    "candidate": True,
                    "matchdirection": "intake_to_buyer",
                    "properties": [
                        {"name": "facility_id", "type": "int", "required": True},
                        {"name": "name", "type": "string"},
                    ],
                },
            ],
            "edges": [],
        },
        "matchentities": {
            "candidate": [{"label": "Facility", "matchdirection": "intake_to_buyer"}],
        },
        "queryschema": {"matchdirections": ["intake_to_buyer"], "fields": []},
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
    }
    return DomainSpec(**raw)


# ── Test Isolation ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(autouse=False)
async def clean_db(graph_driver) -> AsyncGenerator[None, None]:
    """Wipe all nodes after each integration test that opts in."""
    yield
    await graph_driver.execute_write(
        cypher="MATCH (n) DETACH DELETE n",
        parameters={},
        database="neo4j",  # RULE 7: explicit database — no implicit default fallback
    )


# ── Tenant Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def test_tenant() -> str:
    """Unique tenant ID for test isolation."""
    return f"test-{uuid.uuid4().hex[:8]}"


# ── Seed Data ──────────────────────────────────────────────────────────────────

SEED_FACILITIES = [
    {
        "facility_id": 1,
        "name": "Alpha Recycling",
        "contamination_tolerance": 0.03,
        "latitude": 34.05,
        "longitude": -118.24,
        "reinforcement_score": 0.7,
    },
    {
        "facility_id": 2,
        "name": "Beta Compounding",
        "contamination_tolerance": 0.05,
        "latitude": 33.77,
        "longitude": -118.19,
        "reinforcement_score": 0.5,
    },
    {
        "facility_id": 3,
        "name": "Gamma MRF",
        "contamination_tolerance": 0.10,
        "latitude": 40.71,
        "longitude": -74.01,
        "reinforcement_score": 0.3,
    },
]


@pytest_asyncio.fixture
async def seeded_graph(graph_driver, test_tenant: str) -> AsyncGenerator[dict[str, Any], None]:
    """Seed deterministic test data into Neo4j. Cleans up after test."""
    db = "neo4j"

    await graph_driver.execute_query(
        """
        UNWIND $batch AS row
        MERGE (f:Facility {facility_id: row.facility_id})
        SET f += row, f.tenant = $tenant, f.updated_at = datetime()
        """,
        parameters={"batch": SEED_FACILITIES, "tenant": test_tenant},
        database=db,
    )

    yield {
        "tenant": test_tenant,
        "facility_ids": [f["facility_id"] for f in SEED_FACILITIES],
        "database": db,
    }

    await graph_driver.execute_query(
        "MATCH (n {tenant: $tenant}) DETACH DELETE n",
        parameters={"tenant": test_tenant},
        database=db,
    )
