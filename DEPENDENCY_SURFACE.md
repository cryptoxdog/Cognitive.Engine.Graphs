<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [dependencies]
tags: [dependencies, versions, packages]
owner: platform
status: active
/L9_META -->

# DEPENDENCY_SURFACE.md — External Dependencies Inventory

**Purpose**: Complete dependency inventory with versions, constraints, and CI enforcement.

**Source**: pyproject.toml (SHA: 14d910d), ci.yml (SHA: 108781d)

**Last Verified**: SHA 358d15d (2026-04-02)

---

## Runtime Dependencies (pyproject.toml [tool.poetry.dependencies])

| Package | Version | Purpose |
|---------|---------|---------|
| python | ^3.12 | Runtime |
| fastapi | ^0.135.2 | Chassis HTTP layer (NOT imported in engine/) |
| uvicorn[standard] | ^0.42.0 | ASGI server (chassis only) |
| neo4j | ^5.25.0 | Graph database driver |
| pydantic | ^2.10.0 | Data validation |
| pydantic-settings | ^2.6.0 | Settings management |
| pyyaml | ^6.0 | Domain spec loading |
| redis | ^7.4.0 | Caching layer |
| apscheduler | ^3.10.0 | GDS job scheduling |
| httpx | ^0.28.0 | HTTP client (delegation protocol) |
| structlog | ^25.5.0 | Structured logging |
| prometheus-client | ^0.24.1 | Metrics export |
| numpy | ^2.4.3 | KGE embeddings (when kge_enabled=True) |

**Note**: FastAPI is in runtime deps because chassis is deployed with engine in same package.  
**Contract C-001**: Engine NEVER imports FastAPI/uvicorn despite being in runtime deps.

---

## Dev Dependencies (pyproject.toml [tool.poetry.group.dev.dependencies])

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | 9.0.2 | Test runner |
| pytest-asyncio | ^1.3.0 | Async test support |
| pytest-cov | 7.1.0 | Coverage reporting |
| pytest-mock | ^3.14.0 | Mocking utilities |
| ruff | 0.15.7 | Linter and formatter |
| mypy | 1.19.1 | Type checker |
| types-PyYAML | >=6.0 | YAML type stubs |
| faker | ^40.5.1 | Test data generation |
| testcontainers[neo4j] | ^4.8.0 | Neo4j integration test containers |
| hypothesis | ^6.100.0 | Property-based testing |

---

## CI Pinned Versions (DIFFERENT from pyproject.toml)

**Source**: .github/workflows/ci.yml lines 73-74

| Package | CI Version | Dev Version | Reason for Split |
|---------|------------|-------------|------------------|
| ruff | 0.15.5 | 0.15.7 | CI stability — pinned older version |
| mypy | 1.14.0 | 1.19.1 | CI stability — pinned older version |

**Agent Guidance**: 
- Local dev uses pyproject.toml versions (ruff 0.15.7, mypy 1.19.1)
- CI uses workflow-pinned versions (ruff 0.15.5, mypy 1.14.0)
- CI takes precedence for pass/fail determination
- If local passes but CI fails → run with CI versions locally to diagnose

**Reproduce CI environment locally**:
```bash
pip install ruff==0.15.5 mypy==1.14.0
ruff check .
mypy engine/
```

---

## Coverage Thresholds (3 Different Values)

| Source | Threshold | Scope |
|--------|-----------|-------|
| ci.yml COVERAGE_THRESHOLD | 60% | CI default (can be overridden) |
| pyproject.toml fail_under | 70% | Global minimum |
| TESTING.md layer-specific | 95% | engine/gates/, engine/scoring/ |

**Hierarchy**: Layer-specific (95%) > pyproject.toml global (70%) > CI default (60%)

**Agent Guidance**: When writing tests:
- Gates and scoring: aim for 95%+
- Other engine/ modules: aim for 70%+
- Chassis: aim for 70%+
- Tests will fail if below global 70% threshold

---

## Import Restrictions by Module

**Contract C-001 (Single Ingress)**: Engine NEVER imports FastAPI/Starlette/uvicorn

| Subsystem | Allowed Imports | Forbidden Imports |
|-----------|----------------|-------------------|
| engine/ | neo4j, pydantic, structlog, redis, numpy | fastapi, starlette, uvicorn, httpx (in most modules) |
| engine/handlers.py ONLY | chassis.router | All others |
| engine/packet/ | All above + chassis contracts | httpx |
| chassis/ | fastapi, starlette, uvicorn, all engine/ | None (chassis can import anything) |
| tests/ | All packages | None |

**Special case**: `httpx` allowed ONLY in `engine/packet/` for delegation protocol (Contract C-008).  
Forbidden elsewhere in engine/ (Contract C-008 enforcement via scanner DEL-001, DEL-002).

---

## Version Pinning Strategy

**Runtime**: Caret ranges (`^X.Y.Z`) — minor version updates allowed, major locked
- Example: `neo4j = "^5.25.0"` → allows 5.25.x, 5.26.x, ..., 5.99.x (NOT 6.0.0)

**Dev**: Mix of exact pins and caret ranges
- Exact: pytest, pytest-cov, ruff, mypy (reproducible CI)
- Caret: pytest-asyncio, faker, hypothesis (flexibility)

**CI**: Exact pins in workflow for linters — stability over recency

**Upgrade Workflow**:
1. Local: `poetry update {package}`
2. Test: `make test`
3. If passing: commit pyproject.toml + poetry.lock
4. If CI fails with newer version: revert or fix
5. CI pinned versions (ruff, mypy): update in both pyproject.toml AND ci.yml

---

## Transitive Dependencies

Not documented. Use `poetry show --tree` to inspect.

**Known Gaps**:
- Neo4j driver version: pyproject.toml says ^5.25.0, actual resolved version unknown
- PostgreSQL usage: ci.yml provisions postgres:16 service, but no Python pg driver in deps
  - **Likely explanation**: CI template artifact, not actually used by CEG

---

## License Information

Not documented. Would require manual inspection of each dependency's LICENSE file.

**Agent Action**: If license compliance is required, request license audit from Founder.

---

## Related Documents

- **Source**: pyproject.toml (runtime + dev deps, tool config)
- **Source**: .github/workflows/ci.yml (CI-pinned versions)
- **Coverage details**: TESTING.md (layer-specific thresholds)
- **Import boundaries**: GUARDRAILS.md §2, INVARIANTS.md C-001
