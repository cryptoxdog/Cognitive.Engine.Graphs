"""
tests/conftest.py — Shared fixtures for the L9 Graph Cognitive Engine test suite.
Provides Neo4j testcontainer, async driver, domain spec loading, tenant injection,
seeded graph data, and cleanup orchestration.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, List

import httpx
import pytest
import pytest_asyncio
import yaml
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from engine.api.app import create_app
from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec
from engine.graph.driver import GraphDriver
from engine.middleware import TenantResolver


# ── Event Loop ─────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Neo4j Testcontainer ───────────────────────────────────

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

        container = Neo4jContainer("neo4j:5-enterprise")
        container.with_env("NEO4J_ACCEPT_LICENSE_AGREEMENT", "yes")
        container.with_env("NEO4J_PLUGINS", '["graph-data-science"]')
        container.start()

        yield {
            "uri": container.get_connection_url(),
            "user": "neo4j",
            "password": "test",
        }
        container.stop()

    except ImportError:
        pytest.skip("testcontainers not installed and NEO4J_TEST_URI not set")


# ── Graph Driver ──────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def graph_driver(neo4j_container) -> AsyncGenerator[GraphDriver, None]:
    """Session-scoped async Neo4j driver."""
    driver = GraphDriver(
        uri=neo4j_container["uri"],
        username=neo4j_container["user"],
        password=neo4j_container["password"],
    )
    await driver.connect()
    yield driver
    await driver.close()


# ── Domain Spec Fixtures ──────────────────────────────────

@pytest.fixture(scope="session")
def domain_spec_path() -> Path:
    """Path to the PlasticOS test domain spec."""
    candidates = [
        Path("domains/plasticos/spec.yaml"),
        Path("domains/plasticos_spec.yaml"),
        Path("tests/fixtures/test_domain_spec.yaml"),
    ]
    for p in candidates:
        if p.exists():
            return p
    pytest.skip("No domain spec YAML found in expected locations")


@pytest.fixture(scope="session")
def domain_spec(domain_spec_path: Path) -> DomainSpec:
    """Loaded and validated PlasticOS DomainSpec."""
    loader = DomainPackLoader(search_paths=[domain_spec_path.parent])
    return loader.load_domain(domain_spec_path.stem.replace("_spec", "").replace("spec", "plasticos"))


@pytest.fixture
def minimal_domain_spec() -> DomainSpec:
    """Minimal in-memory domain spec for unit tests that don't need full YAML."""
    raw = {
        "domain": {"id": "test", "name": "Test Domain", "version": "0.0.1"},
        "ontology": {
            "nodes": [
                {"label": "Facility", "managed_by": "sync", "candidate": True,
                 "match_direction": "intake_to_buyer", "properties": [
                     {"name": "facility_id", "type": "int", "required": True},
                     {"name": "name", "type": "string"},
                     {"name": "lat", "type": "float"},
                     {"name": "lon", "type": "float"},
                     {"name": "credit_score", "type": "float"},
                     {"name": "min_density", "type": "float"},
                     {"name": "max_density", "type": "float"},
                 ]},
                {"label": "MaterialIntake", "managed_by": "api", "query_entity": True,
                 "match_direction": "intake_to_buyer", "properties": [
                     {"name": "intake_id", "type": "int", "required": True},
                 ]},
            ],
            "edges": [
                {"type": "EXCLUDED_FROM", "from": "Facility", "to": "Facility",
                 "direction": "DIRECTED", "category": "exclusion", "managed_by": "sync"},
            ],
        },
        "match_entities": {
            "candidate": [{"label": "Facility", "match_direction": "intake_to_buyer"}],
            "query_entity": [{"label": "MaterialIntake", "match_direction": "intake_to_buyer"}],
        },
        "query_schema": {"match_directions": ["intake_to_buyer"], "fields": []},
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
    }
    return DomainSpec(**raw)


# ── Tenant Fixtures ───────────────────────────────────────

@pytest.fixture
def test_tenant() -> str:
    """Unique tenant ID for test isolation."""
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def tenant_resolver() -> TenantResolver:
    """TenantResolver configured for testing."""
    return TenantResolver(
        known_tenants={"plasticos", "mortgageos", "test"},
        allow_unknown=True,
        default_tenant="test",
    )


# ── FastAPI Test Client ───────────────────────────────────

@pytest_asyncio.fixture
async def app() -> FastAPI:
    """FastAPI application instance."""
    return create_app()


@pytest_asyncio.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    """
    Async HTTP test client using ASGITransport (httpx >=0.28).
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ── Seed Data ─────────────────────────────────────────────

SEED_FACILITIES = [
    {"facility_id": 1, "name": "Alpha Recycling", "lat": 34.05, "lon": -118.24,
     "process_type": "extrusion", "facility_role": "processor",
     "min_density": 0.90, "max_density": 0.97, "min_mfi": 2.0, "max_mfi": 25.0,
     "contamination_tolerance": 0.03, "pvc_tolerant": False, "food_grade_certified": True,
     "has_extruder": True, "has_wash_line": True, "handles_regrind": True, "handles_flake": True,
     "gate_mode": "strict"},
    {"facility_id": 2, "name": "Beta Compounding", "lat": 33.77, "lon": -118.19,
     "process_type": "injection", "facility_role": "compounder",
     "min_density": 0.85, "max_density": 1.05, "min_mfi": 5.0, "max_mfi": 50.0,
     "contamination_tolerance": 0.05, "pvc_tolerant": True, "food_grade_certified": False,
     "has_granulator": True, "has_extruder": True, "handles_regrind": True, "handles_flake": False,
     "gate_mode": "strict"},
    {"facility_id": 3, "name": "Gamma MRF", "lat": 40.71, "lon": -74.01,
     "process_type": "sorting", "facility_role": "mrf",
     "min_density": 0.80, "max_density": 1.20, "min_mfi": 0.5, "max_mfi": 100.0,
     "contamination_tolerance": 0.10, "pvc_tolerant": True, "food_grade_certified": False,
     "has_sorting_line": True, "has_shredder": True, "handles_regrind": True,
     "handles_flake": True, "handles_rollstock": True, "gate_mode": "relaxed"},
]


@pytest_asyncio.fixture
async def seeded_graph(graph_driver: GraphDriver, test_tenant: str) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Seed deterministic test data into Neo4j. Returns metadata about what was seeded.
    Cleans up after test completes.
    """
    db = "neo4j"

    # Seed facilities
    await graph_driver.execute_query(
        """
        UNWIND $batch AS row
        MERGE (f:Facility {facility_id: row.facility_id})
        SET f += row, f.tenant = $tenant, f.updated_at = datetime()
        """,
        parameters={"batch": SEED_FACILITIES, "tenant": test_tenant},
        database=db,
    )

    # Seed taxonomy
    for polymer in ["HDPE", "PP", "PET", "LDPE"]:
        await graph_driver.execute_query(
            "MERGE (p:PolymerFamily {code: $code})",
            parameters={"code": polymer},
            database=db,
        )

    for form in ["regrind", "flake", "pellet", "bale", "rollstock"]:
        await graph_driver.execute_query(
            "MERGE (f:MaterialForm {code: $code})",
            parameters={"code": form},
            database=db,
        )

    # Seed capability edges
    await graph_driver.execute_query(
        """
        MATCH (f:Facility {facility_id: 1})
        MATCH (p:PolymerFamily {code: 'HDPE'})
        MERGE (f)-[:ACCEPTS_POLYMER]->(p)
        """,
        database=db,
    )

    # Seed exclusion edge for testing
    await graph_driver.execute_query(
        """
        MATCH (a:Facility {facility_id: 1}), (b:Facility {facility_id: 2})
        MERGE (a)-[:EXCLUDED_FROM]->(b)
        """,
        database=db,
    )

    yield {
        "tenant": test_tenant,
        "facility_ids": [f["facility_id"] for f in SEED_FACILITIES],
        "polymers": ["HDPE", "PP", "PET", "LDPE"],
        "forms": ["regrind", "flake", "pellet", "bale", "rollstock"],
        "database": db,
    }

    # Cleanup: remove all test data for this tenant
    await graph_driver.execute_query(
        "MATCH (n {tenant: $tenant}) DETACH DELETE n",
        parameters={"tenant": test_tenant},
        database=db,
    )
    # Cleanup taxonomy nodes created during test
    await graph_driver.execute_query(
        "MATCH (n) WHERE n:PolymerFamily OR n:MaterialForm DETACH DELETE n",
        database=db,
    )


# ── Helpers ───────────────────────────────────────────────

@pytest.fixture
def make_headers(test_tenant: str):
    """Factory for request headers with tenant injection."""
    def _make(tenant: str = None, extra: dict = None) -> dict:
        headers = {
            "Content-Type": "application/json",
            "X-Domain-Key": tenant or test_tenant,
        }
        if extra:
            headers.update(extra)
        return headers
    return _make
