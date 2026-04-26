# AGENTS.md — L9 Graph Cognitive Engine

Cross-tool agent instructions for the CEG repository. Read by Claude Code, Codex, Cursor, Copilot, Jules, Aider, CodeRabbit, and all AGENTS.md-compatible tools.

## Project Overview

- **Name**: Cognitive Engine Graphs (CEG)
- **Type**: Domain-configurable graph matching and scoring engine
- **Stage**: Production (with 7 open seL4-upgrade PRs pending merge)
- **Stack**: Python 3.12+, Neo4j 5.x + GDS, Pydantic v2, FastAPI (chassis only), pytest

## Commands

```bash
make setup              # Install deps, pre-commit hooks, verify Neo4j
make dev                # docker-compose (app + Neo4j + Redis + Prometheus + Grafana)
make test               # Full pytest suite (unit + integration + compliance)
make test-unit          # Gate compilation, scoring math, parameter resolution
make test-integration   # testcontainers-neo4j full pipeline
make lint               # ruff check + mypy
make lint-fix           # ruff check --fix + ruff format .
make cypher-lint        # Scan generated Cypher for injection vectors
```

## Testing

- Run `make test-unit` before committing changes to engine code
- Run `make lint` before opening a pull request
- Unit tests: `tests/unit/` — pure functions, no Neo4j
- Integration tests: `tests/integration/` — testcontainers-neo4j
- Compliance tests: `tests/compliance/` — prohibited factors blocked at compile time
- Minimum: every new function needs at least one test
- CI pipeline: 7 phases, 15 pre-commit hooks — see `docs/CI_PIPELINE.md`

## Project Structure

```
engine/                  # Core matching logic — NEVER imports FastAPI
  handlers.py            # 8 action handlers: match, sync, admin, outcomes, resolve, health, healthcheck, enrich
  boot.py                # Lifecycle: startup/shutdown, weight-sum assertion
  config/                # DomainSpec schema, YAML loader, Settings singleton
  gates/                 # Gate → WHERE clause compiler (10 gate types)
  scoring/               # Scoring → WITH clause (13 computation types), calibration, confidence
  traversal/             # Traversal → MATCH clauses, parameter resolver
  sync/                  # UNWIND MERGE/MATCH SET Cypher generator
  gds/                   # APScheduler for GDS jobs (Louvain, co-occurrence, etc.)
  graph/                 # Neo4j AsyncDriver wrapper + circuit breaker
  compliance/            # PII, audit, prohibited factors
  health/                # AI readiness scoring, gap prioritization, re-enrichment
  intake/                # CRM-to-YAML pipeline
  personas/              # Algebraic trait vector composition
  causal/                # Causal edge compiler, attribution, counterfactual
  feedback/              # Convergence loop, signal weights, score propagation
  resolution/            # Entity resolver, similarity scoring, deduplication
  kge/                   # CompoundE3D embeddings (dormant — kge_enabled=False)
chassis/                 # Thin FastAPI adapter — engine NEVER imports from here
domains/                 # {domain_id}_domain_spec.yaml per vertical
tests/                   # unit/, integration/, compliance/, contracts/, invariants/, property/
tools/                   # contract_scanner.py, verify_contracts.py, validate_domain.py
```

## Code Style

- Python 3.12+, async/await for all I/O
- Type hints on every function signature
- Pydantic v2 BaseModel for all structured data
- `ruff format .` before commit (Black-compatible, 88-char)
- `structlog.get_logger(__name__)` for logging — never configure structlog in engine
- Exception messages: `msg = f"..."; raise ValueError(msg)` (avoids EM101)
- Nullable: `x: str | None = None` — never `Optional`
- Datetime: always `datetime.now(tz=UTC)`

## Git Workflow

- Branch format: `feat/description`, `fix/description`, `docs/description`
- Commit messages: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- PRs require passing CI (ruff + mypy + pytest + contract scanner)
- Squash merge to main

## Boundaries

### ✅ Always
- Sanitize all labels before Cypher interpolation via `sanitize_label()`
- Route all Neo4j queries through `engine/graph/driver.py` — never raw sessions
- Gate every behavioral change with a feature flag in `engine/config/settings.py`
- Validate domain spec inputs — they are untrusted
- Include tests for every new module

### ⚠️ Ask First
- Creating new top-level directories under `engine/`
- Adding new action handlers (requires `register_all()` update)
- Modifying `engine/config/schema.py` (affects all domain specs)
- Changes to `engine/boot.py` lifecycle
- Any change to `engine/handlers.py` handler signatures

### 🚫 Never
- Import FastAPI, Starlette, or uvicorn in `engine/` code
- Use `eval()`, `exec()`, `pickle.load()`, `yaml.load()` without SafeLoader
- Interpolate values into Cypher without parameterization (`$batch`, `$query`)
- Log PII values — structlog filters are set by chassis
- Create unbounded caches — use `cachetools.TTLCache` or equivalent
- Hardcode GDS algorithm scheduling — use declarative spec
- Share KGE embeddings cross-tenant
- Commit `.env` files, API keys, or secrets

## Key Architecture Rules

1. **Engine owns logic, chassis owns HTTP** — handlers receive `(tenant, payload)` → `dict`
2. **Domain spec is source of truth** — all matching behavior from YAML, never hardcoded
3. **Gate-then-score in Cypher** — no post-filtering in Python
4. **PacketEnvelope for all persisted events** — `inflate_ingress()` / `deflate_egress()`
5. **24 contracts enforced** — see `tools/contract_scanner.py` and `docs/contracts/`

## Agent Reference Docs

| Doc | Purpose | When to Load |
|-----|---------|-------------|
| `docs/TROUBLESHOOTING.md` | 10 common failure scenarios with diagnosis + resolution | Debugging errors, CI failures |
| `docs/AI_AGENT_REVIEW_CHECKLIST.md` | PR review rubric, severity scoring, comment templates | Reviewing PRs (CodeRabbit, Qodo, Claude) |
| `docs/CI_PIPELINE.md` | 7 CI phases, 15 pre-commit hooks, blocking vs advisory | CI failure diagnosis |
| `.claude/rules/contracts.md` | 24 contracts + enforcement matrix (automated vs manual) | Contract uncertainty |
