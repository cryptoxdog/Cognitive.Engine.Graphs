# Testing — Cognitive Engine Graphs (CEG)

> Agent reference: read before writing any test code. All test decisions flow from this document.

---

## Test Suite Structure

```
tests/
  unit/           Pure function tests. No Neo4j. No I/O. Fast (<100ms total).
  integration/    Full pipeline via testcontainers-neo4j. Requires Docker.
  compliance/     Prohibited factor enforcement. Gate compile-time blocking.
  contracts/      All 24 behavioral contracts (via verify_contracts.py).
  invariants/     Engine invariants: score bounds, weight sums, determinism.
  property/       Hypothesis-based property tests for scoring math.
```

---

## Commands

```bash
make test              # Full suite: unit + integration + compliance + contracts
make test-unit         # Gate compilation, scoring math, parameter resolution only
make test-integration  # testcontainers-neo4j — requires Docker running
make test-contracts    # Verify all 24 contracts pass (fast, no Neo4j)
make test-property     # Hypothesis property tests (scoring, gate logic)
```

---

## Coverage Thresholds

| Layer | Minimum Coverage |
|-------|-----------------|
| `engine/gates/` | 95% |
| `engine/scoring/` | 95% |
| `engine/config/` | 90% |
| `engine/feedback/` | 85% |
| `engine/causal/` | 85% |
| `engine/resolution/` | 85% |
| `chassis/` | 70% |

CI fails if thresholds are not met. Run `make coverage` to check locally.

---

## Unit Test Patterns

### Gate Compiler Tests
```python
# tests/unit/gates/test_proximity_gate.py
def test_proximity_gate_compiles_sanitized_label():
    spec = GateSpec(type="proximity", candidateprop="distance", threshold=50)
    domain = make_domain_spec(targetnode="Contact")
    gate = ProximityGate()
    clause = gate.compile_where(spec, domain)
    assert "$max_distance" in clause          # parameterized
    assert "Contact" not in clause            # label not in WHERE
    assert "distance" in clause               # prop name present
```

### Scoring Math Tests
```python
# tests/unit/scoring/test_signal_weights.py
def test_lift_formula_clamps_to_bounds():
    calc = SignalWeightCalculator(min_weight=0.1, max_weight=2.0)
    weight = calc.compute(positive_count=5, total_count=5, base_rate=0.5)
    assert 0.1 <= weight <= 2.0

def test_confidence_dampening_reduces_uncertain_weights():
    weight_small_sample = calc.compute(positive_count=2, total_count=3, base_rate=0.5)
    weight_large_sample = calc.compute(positive_count=200, total_count=300, base_rate=0.5)
    assert abs(weight_small_sample - 1.0) < abs(weight_large_sample - 1.0)
```

### Domain Spec Validation Tests
```python
# tests/unit/config/test_schema.py
def test_domain_spec_rejects_unknown_gate_type():
    with pytest.raises(ValidationError):
        DomainSpec.model_validate({"gates": [{"type": "nonexistent_gate"}]})
```

---

## Integration Test Patterns

```python
# tests/integration/test_match_pipeline.py
@pytest.mark.integration
async def test_full_match_pipeline(neo4j_container):
    driver = await GraphDriver.create(neo4j_container.get_connection_url())
    spec = load_domain_spec("domains/test_domain_spec.yaml")
    result = await handle_match(
        tenant=TenantContext(id="test"),
        payload=MatchRequest(query_id="q1", limit=10),
        driver=driver,
        spec=spec,
    )
    assert result["status"] == "ok"
    assert isinstance(result["matches"], list)
    assert all(0.0 <= m["score"] <= 1.0 for m in result["matches"])
```

---

## Compliance Test Patterns

```python
# tests/compliance/test_prohibited_factors.py
def test_age_gate_rejected_at_compile_time():
    spec = GateSpec(type="range", candidateprop="age")
    with pytest.raises(ProhibitedFactorError, match="age"):
        gate_compiler.compile(spec, domain)

def test_gender_scoring_dimension_blocked():
    spec = ScoringDimension(field="gender")
    with pytest.raises(ProhibitedFactorError, match="gender"):
        scoring_assembler.compile(spec, domain)
```

---

## Contract Tests

All 24 contracts are verified via:
```bash
python tools/verify_contracts.py
```

Contracts are documented in `docs/contracts/` and `.claude/rules/contracts.md`.  
Contract C-001 through C-024 must all pass before any merge.

---

## Property Tests (Hypothesis)

```python
# tests/property/test_score_bounds.py
from hypothesis import given, strategies as st

@given(st.floats(min_value=-1000, max_value=1000))
def test_score_always_clamped(raw_score):
    result = clamp_score(raw_score)
    assert 0.0 <= result <= 1.0

@given(st.dictionaries(st.text(), st.floats(0, 1), min_size=1))
def test_weight_sum_assertion(weights):
    assume(sum(weights.values()) <= 1.0)
    assert validate_weights(weights) is None
```

---

## Fixtures

Root `conftest.py` provides:
- `neo4j_container` — testcontainers-managed Neo4j instance (integration only)
- `make_domain_spec()` — factory for minimal valid DomainSpec
- `make_tenant_context()` — factory for TenantContext with test defaults
- `mock_driver` — AsyncMock GraphDriver for unit tests

---

## Test Naming Convention

```
tests/{layer}/{subsystem}/test_{module_name}.py
tests/unit/gates/test_proximity_gate.py
tests/unit/scoring/test_signal_weights.py
tests/integration/test_match_pipeline.py
tests/compliance/test_prohibited_factors.py
```

Functions: `test_{what}_{condition}_{expected_outcome}`
```python
def test_gate_compiler_rejects_unsanitized_label_injection(): ...
def test_score_clamped_to_unit_interval_when_raw_exceeds_1(): ...
```
