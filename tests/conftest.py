"""
tests/conftest.py

Shared pytest fixtures and configuration for L9 Graph Cognitive Engine test suite.
"""

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from faker import Faker
from neo4j import AsyncGraphDatabase

# Configure pytest
pytest_plugins = ["pytest_asyncio"]


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external dependencies)")
    config.addinivalue_line("markers", "integration: Integration tests (requires Neo4j)")
    config.addinivalue_line("markers", "compliance: Compliance tests (ECOA, HIPAA, etc.)")
    config.addinivalue_line("markers", "performance: Performance benchmarks")
    config.addinivalue_line("markers", "slow: Slow tests (> 5s execution)")


# ============================================================================
# ASYNC FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ============================================================================
# MOCK NEO4J DRIVER
# ============================================================================


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for unit tests."""
    driver = Mock()
    session = AsyncMock()
    result = AsyncMock()

    # Configure mock chain
    driver.session.return_value = session
    session.run.return_value = result
    result.data.return_value = []

    return driver


@pytest.fixture
def mock_neo4j_session():
    """Mock Neo4j async session."""
    session = AsyncMock()
    result = AsyncMock()

    session.run.return_value = result
    result.data.return_value = []

    return session


# ============================================================================
# TEST DATA GENERATORS
# ============================================================================


@pytest.fixture
def faker_instance():
    """Faker instance for generating test data."""
    return Faker()


@pytest.fixture
def sample_query_borrower() -> dict[str, Any]:
    """Sample borrower query for mortgage domain."""
    return {
        "borrowerid": "TEST_BRW_001",
        "creditscore": 720,
        "annualincomeusd": 85000.0,
        "monthlydebtusd": 1500.0,
        "loanamountusd": 350000.0,
        "propertyvalueusd": 450000.0,
        "downpaymentusd": 100000.0,
        "propertytype": "singlefamily",
        "propertystate": "NC",
        "occupancy": "owneroccupied",
        "loanpurpose": "purchase",
        "vaeligible": False,
        "firsttimebuyer": False,
    }


@pytest.fixture
def sample_query_patient() -> dict[str, Any]:
    """Sample patient query for healthcare domain."""
    return {
        "patientid": "TEST_PAT_001",
        "age": 45,
        "zipcode": "28202",
        "insuranceplan": "BCBS_PPO",
        "primarycondition": "Type2Diabetes",
        "urgency": "routine",
        "maxdistancemiles": 15.0,
    }


@pytest.fixture
def sample_candidates_loanproducts() -> list:
    """Sample loan product candidates."""
    return [
        {
            "productid": "PROD_001",
            "productname": "30-Year Fixed Conventional",
            "lenderid": "LENDER_A",
            "loancategory": "conventional",
            "mincreditscore": 680,
            "maxdtipct": 43.0,
            "maxltvpct": 80.0,
            "baseratepct": 6.5,
        },
        {
            "productid": "PROD_002",
            "productname": "15-Year Fixed Jumbo",
            "lenderid": "LENDER_B",
            "loancategory": "jumbo",
            "mincreditscore": 740,
            "maxdtipct": 36.0,
            "maxltvpct": 75.0,
            "baseratepct": 6.25,
        },
    ]


# ============================================================================
# DOMAIN SPEC FIXTURES
# ============================================================================


@pytest.fixture
def minimal_domain_spec() -> dict[str, Any]:
    """Minimal valid domain specification for testing."""
    return {
        "domain": {"id": "test-domain", "name": "Test Domain", "version": "1.0.0"},
        "ontology": {
            "nodes": [
                {
                    "label": "Candidate",
                    "managedby": "sync",
                    "candidate": True,
                    "properties": [
                        {"name": "id", "type": "string", "required": True},
                        {"name": "score", "type": "float"},
                    ],
                },
                {
                    "label": "Query",
                    "managedby": "api",
                    "queryentity": True,
                    "properties": [{"name": "queryid", "type": "string", "required": True}],
                },
            ],
            "edges": [],
        },
        "matchentities": {
            "candidate": [{"label": "Candidate", "matchdirection": "querytocandidate"}],
            "queryentity": [{"label": "Query", "matchdirection": "querytocandidate"}],
        },
        "queryschema": {
            "matchdirections": ["querytocandidate"],
            "fields": [{"name": "queryid", "type": "string", "required": True}],
        },
        "traversal": {"steps": []},
        "gates": [],
        "scoring": {"dimensions": []},
    }


@pytest.fixture
def mortgage_domain_spec() -> dict[str, Any]:
    """Mortgage domain specification for integration tests."""
    return {
        "domain": {"id": "mortgage-test", "name": "Mortgage Test Domain", "version": "1.0.0"},
        "ontology": {
            "nodes": [
                {
                    "label": "BorrowerProfile",
                    "managedby": "sync",
                    "queryentity": True,
                    "properties": [
                        {"name": "borrowerid", "type": "string", "required": True},
                        {"name": "creditscore", "type": "int", "required": True},
                        {"name": "annualincomeusd", "type": "float", "required": True},
                        {"name": "dtipct", "type": "float", "unit": "percentage"},
                    ],
                },
                {
                    "label": "LoanProduct",
                    "managedby": "sync",
                    "candidate": True,
                    "properties": [
                        {"name": "productid", "type": "string", "required": True},
                        {"name": "mincreditscore", "type": "int"},
                        {"name": "maxdtipct", "type": "float"},
                        {"name": "baseratepct", "type": "float"},
                    ],
                },
            ],
            "edges": [],
        },
        "matchentities": {
            "candidate": [{"label": "LoanProduct", "matchdirection": "borrowertoproduct"}],
            "queryentity": [{"label": "BorrowerProfile", "matchdirection": "borrowertoproduct"}],
        },
        "queryschema": {
            "matchdirections": ["borrowertoproduct"],
            "fields": [
                {"name": "borrowerid", "type": "string", "required": True},
                {"name": "creditscore", "type": "int", "required": True},
                {"name": "annualincomeusd", "type": "float", "required": True},
            ],
        },
        "derivedparameters": [
            {"name": "dtipct", "expression": "monthlydebtusd / (annualincomeusd / 12.0) * 100.0", "type": "float"}
        ],
        "traversal": {"steps": []},
        "gates": [
            {
                "name": "credit_min",
                "type": "threshold",
                "candidateprop": "mincreditscore",
                "queryparam": "creditscore",
                "operator": "<=",
                "nullbehavior": "pass",
            },
            {
                "name": "dti_max",
                "type": "threshold",
                "candidateprop": "maxdtipct",
                "queryparam": "dtipct",
                "operator": ">=",
                "nullbehavior": "pass",
            },
        ],
        "scoring": {
            "dimensions": [
                {
                    "name": "rate_score",
                    "source": "candidateproperty",
                    "candidateprop": "baseratepct",
                    "computation": "inverselinear",
                    "minvalue": 3.0,
                    "maxvalue": 8.0,
                    "weightkey": "wrate",
                    "defaultweight": 1.0,
                }
            ]
        },
        "compliance": {
            "regimes": [{"name": "ECOA"}],
            "prohibitedfactors": {
                "enabled": True,
                "blockedfields": ["race", "ethnicity", "gender"],
                "enforcement": "compiletime",
            },
        },
    }


# ============================================================================
# COMPLIANCE FIXTURES
# ============================================================================


@pytest.fixture
def ecoa_prohibited_fields() -> list:
    """ECOA prohibited factor fields."""
    return ["race", "ethnicity", "religion", "gender", "age", "maritalstatus", "nationalorigin"]


@pytest.fixture
def hipaa_prohibited_fields() -> list:
    """HIPAA prohibited factor fields."""
    return ["race", "ethnicity", "religion", "geneticinformation", "disability"]


@pytest.fixture
def hipaa_pii_fields() -> list:
    """HIPAA PII fields requiring protection."""
    return ["patientid", "ssn", "dob", "medicalrecordnumber", "name", "address", "email", "phone"]


# ============================================================================
# GATE CONFIG FIXTURES
# ============================================================================


@pytest.fixture
def threshold_gate_config() -> dict[str, Any]:
    """Sample threshold gate configuration."""
    return {
        "name": "credit_min",
        "type": "threshold",
        "candidateprop": "mincreditscore",
        "queryparam": "creditscore",
        "operator": "<=",
        "nullbehavior": "pass",
        "invertible": True,
    }


@pytest.fixture
def range_gate_config() -> dict[str, Any]:
    """Sample range gate configuration."""
    return {
        "name": "price_range",
        "type": "range",
        "candidateprop": "priceperlb",
        "queryparam_min": "minpriceperlb",
        "queryparam_max": "maxpriceperlb",
        "nullbehavior": "fail",
    }


@pytest.fixture
def boolean_gate_config() -> dict[str, Any]:
    """Sample boolean gate configuration."""
    return {
        "name": "accepts_new_patients",
        "type": "boolean",
        "candidateprop": "acceptsnewpatients",
        "queryparam": True,
        "nullbehavior": "fail",
    }


@pytest.fixture
def exclusion_gate_config() -> dict[str, Any]:
    """Sample exclusion gate configuration."""
    return {
        "name": "blacklist",
        "type": "exclusion",
        "edgetype": "BLACKLISTED",
        "fromnode": "query",
        "tonode": "candidate",
        "nullbehavior": "pass",
    }


# ============================================================================
# SCORING FIXTURES
# ============================================================================


@pytest.fixture
def scoring_dimension_geodecay() -> dict[str, Any]:
    """Sample geodecay scoring dimension."""
    return {
        "name": "distance_score",
        "source": "computed",
        "computation": "geodecay",
        "decayconstant": 50.0,
        "weightkey": "wgeo",
        "defaultweight": 0.35,
        "directionscoped": ["buyertosupplier"],
    }


@pytest.fixture
def scoring_dimension_inverselinear() -> dict[str, Any]:
    """Sample inverselinear scoring dimension."""
    return {
        "name": "price_score",
        "source": "candidateproperty",
        "candidateprop": "priceperlb",
        "computation": "inverselinear",
        "minvalue": 0.5,
        "maxvalue": 2.0,
        "weightkey": "wprice",
        "defaultweight": 0.30,
    }


# ============================================================================
# FILE PATH FIXTURES
# ============================================================================


@pytest.fixture
def test_fixtures_dir() -> Path:
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def test_domains_dir(test_fixtures_dir) -> Path:
    """Path to test domain specifications."""
    return test_fixtures_dir / "domains"


@pytest.fixture
def test_queries_dir(test_fixtures_dir) -> Path:
    """Path to test query payloads."""
    return test_fixtures_dir / "queries"


# ============================================================================
# ENVIRONMENT FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def test_env_vars(monkeypatch):
    """Set test environment variables."""
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USERNAME", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "testpassword")
    monkeypatch.setenv("DOMAINS_ROOT", "./tests/fixtures/domains")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")


# ============================================================================
# TESTCONTAINERS FIXTURES (INTEGRATION TESTS)
# ============================================================================


@pytest.fixture(scope="session")
async def neo4j_container():
    """
    Start Neo4j container for integration tests.
    Requires: pip install testcontainers[neo4j]
    """
    try:
        from testcontainers.neo4j import Neo4jContainer

        container = Neo4jContainer("neo4j:5.15")
        container.with_env("NEO4J_AUTH", "neo4j/testpassword")
        container.start()

        yield container

        container.stop()
    except ImportError:
        pytest.skip("testcontainers not installed")


@pytest.fixture
async def neo4j_driver(neo4j_container):
    """Async Neo4j driver connected to test container."""
    uri = neo4j_container.get_connection_url()
    driver = AsyncGraphDatabase.driver(uri, auth=("neo4j", "testpassword"))

    yield driver

    await driver.close()


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
async def cleanup_test_data(mock_neo4j_session):
    """Clean up test data after each test."""
    yield
    # Cleanup logic here (if needed)
    pass
