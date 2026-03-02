<!-- L9_TEMPLATE: true -->
# L9 Test Writing Contract

## Rule 1: Test Instantiation Must Match METHOD_SIGNATURES.md
Before writing any test, check `docs/contracts/METHOD_SIGNATURES.md` for
the exact constructor signature. Do NOT guess.

## Unit Test Pattern (Gates, Scoring, Parameter Resolution)
```python
import pytest
from engine.config.schema import DomainSpec, GateSpec, GateType

@pytest.fixture
def sample_spec() -> DomainSpec:
    """Load a real domain spec — do NOT construct manually."""
    from engine.config.loader import DomainPackLoader
    loader = DomainPackLoader(domains_dir=Path("domains"))
    return loader.load_domain("plasticos")

def test_range_gate_compilation(sample_spec: DomainSpec):
    compiler = GateCompiler(sample_spec)  # Match METHOD_SIGNATURES.md
    result = compiler.compile_gate(sample_spec.gates, "buyer_to_seller")
    assert "WHERE" not in result  # compile_gate returns clause fragment, not full WHERE
    assert "candidate." in result
```


## Integration Test Pattern (Full Pipeline)

```python
import pytest
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="module")
def neo4j():
    with Neo4jContainer("neo4j:5-enterprise") as container:
        yield container

# NEVER mock GraphDriver for integration tests
# ALWAYS use testcontainers-neo4j
```


## BANNED in Tests

```python
# ❌ No mocking Neo4j driver in integration tests
mock_driver = MagicMock(spec=GraphDriver)  # BANNED in integration/

# ❌ No manual DomainSpec construction with wrong fields
spec = DomainSpec(matchentities=...)  # WILL CRASH — wrong field name

# ❌ No importing from engine.api (doesn't exist)
from engine.api.routers.match import match_endpoint  # BANNED
```

```

