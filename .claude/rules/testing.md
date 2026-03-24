---
paths:
  - "tests/**/*.py"
---
# Testing Rules (Contract 17)

## Test Types
- **Unit** (`tests/unit/`): Pure functions — gate compilation, scoring math, param resolution. No Neo4j.
- **Integration** (`tests/integration/`): Full match pipeline with testcontainers-neo4j. Seed data → execute → verify.
- **Compliance** (`tests/compliance/`): Prohibited factors blocked at compile time.
- **Contract** (`tests/contracts/`): One test per CEG contract (20+). Exercises contract boundaries.
- **Invariant** (`tests/invariants/`): 31 regression tests. Tagged `@pytest.mark.finding("T1-03")`.
- **Scoring benchmark** (`tests/scoring/benchmark.py`): Good/bad separation. CI fails if < 0.20.
- **Property** (`tests/property/`): Hypothesis-based for GateCompiler and ScoringAssembler.

## Rules
- Every new function needs at least one test
- Run `make test-unit` before committing engine changes
- Integration tests use testcontainers-neo4j — do NOT mock the Neo4j driver
- Magic values OK in tests/ (PLR2004 ignored) but not in engine/
- Performance target: <200ms p95 match latency
- Use `@pytest.mark.finding("ID")` to tag regression tests for specific defects
