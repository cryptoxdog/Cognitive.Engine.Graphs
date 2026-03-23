<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [agent-rules]
tags: [L9_TEMPLATE, agent-rules, claude]
owner: platform
status: active
/L9_META -->

# CLAUDE.md — L9 Graph Engine Project Context

## What This Project Is

This is the **Graph Cognitive Engine** (CEG) for the L9 constellation. It performs gate-then-score graph matching across multi-domain specs (plastics recycling, mortgage brokerage, healthcare referrals, freight matching). The engine plugs into the L9 chassis (FastAPI shell that handles auth/tenant/HTTP) and exposes action handlers. The engine NEVER touches HTTP directly.

## Design Principles

These six principles generated the 24 contracts below. Use them for decisions in novel situations not covered by a specific contract.

1. **Domain spec is the single source of truth** — all behavior flows from YAML. If it's not in the spec, the engine doesn't do it. No hardcoded business logic.
2. **Gate-then-score in Cypher, not Python** — matching is a single Cypher query. No post-filtering, no iterative scoring, no Python-side candidate manipulation.
3. **Engine owns logic, chassis owns HTTP** — clean separation. Engine functions receive `(tenant, payload)` and return `dict`. No HTTP awareness.
4. **Additive by default** — new capabilities are added as new files/modules, not by modifying existing ones. Feature flags control activation.
5. **Explicit over implicit** — all state is managed (`EngineState`), all caches are bounded (`TTLCache`), all inputs are validated (Pydantic), all outputs are bounded ([0, 1] score clamping).
6. **Mechanism/policy separation** — the engine proves the mechanism works (via tests and invariants). The operator decides when to activate it (via feature flags and admin subactions).

## Tech Stack

- **Python 3.12+**, async/await throughout
- **Neo4j 5.x** with GDS plugin (Louvain, similarity, pagerank)
- **PostgreSQL + pgvector** for PacketEnvelope persistence
- **Redis** for idempotency caching (chassis-managed)
- **Pydantic v2** for all schemas (domain specs, config, models)
- **pytest + testcontainers-neo4j** for integration testing
- **cachetools** for bounded TTL caching
- **Hypothesis** for property-based testing (Wave 5)

## Directory Structure (Do Not Deviate)

```
engine/
  handlers.py              # Chassis bridge — register_all() + all handle_* action handlers
  boot.py                  # GraphLifecycle — startup/shutdown, weight-sum assertion
  state.py                 # EngineState dataclass — centralized mutable state (Wave 4)
  config/
    schema.py              # DomainSpec Pydantic model + all spec types
    loader.py              # YAML domain spec loader + TTL cache
    settings.py            # Settings singleton (all feature flags live here)
    units.py               # Unit conversion utilities
  gates/
    compiler.py            # Gate → WHERE clause compiler + validate_gates() pre-pass
    null_semantics.py      # NULL behavior handling (pass/fail per gate)
    registry.py            # Gate type registry
    types/all_gates.py     # 10 gate type implementations (Range, Threshold, Boolean, etc.)
  scoring/
    assembler.py           # Scoring → WITH clause + _clamp_expression() score bounding
    calibration.py         # Score calibration framework (seL4 W2-01)
    confidence.py          # Ensemble confidence bounds checker (seL4 W2-03)
    feedback.py            # Weight auto-tuning feedback loop (seL4 W2-02)
    pareto.py              # Multi-objective Pareto-optimal scoring
  traversal/
    assembler.py           # Traversal → MATCH clauses + validate_traversal() bounds
    resolver.py            # Parameter resolver (strict mode: W1-05)
  sync/
    generator.py           # UNWIND MERGE/MATCH SET Cypher generator
  gds/
    scheduler.py           # APScheduler for GDS jobs (Louvain, co-occurrence, etc.)
  graph/
    driver.py              # Neo4j AsyncDriver wrapper + circuit breaker (W4-02)
  compliance/
    engine.py              # ComplianceEngine singleton + periodic flush (W4-04)
    pii.py                 # PII handling + GDPR erasure (erase_subject)
    audit.py               # AuditLogger
    prohibited_factors.py  # Compile-time prohibited field blocking
  health/
    api.py                 # HEALTH service handler (assess, batch_assess, report)
    readiness_scorer.py    # AI readiness scoring
    gap_prioritizer.py     # Data gap prioritization
    enrichment_trigger.py  # ROI-based re-enrichment triggering
    field_analyzer.py      # Entity field-level analysis
    field_health.py        # EntityHealth model
    health_report.py       # Health report generation
    health_schemas.py      # Health-specific Pydantic models
    domain_field_mapper.py # Domain-to-field mapping
    nightly_health_scan.py # Scheduled health scanning
  intake/
    api.py                 # CRM-to-YAML pipeline handler (intake_scan, intake_compile, intake_report)
    crm_field_scanner.py   # Scan CRM fields
    intake_compiler.py     # Compile domain specs from CRM data
    impact_reporter.py     # Analyze and report intake impact
    intake_schema.py       # Intake-specific Pydantic models
    vertical_discovery.py  # Vertical/domain auto-discovery
  personas/
    composer.py            # Algebraic trait vector composition (add/subtract/scale)
    selector.py            # Persona selection logic
    suppression.py         # Trait suppression
    synthesis.py           # Persona synthesis
    types.py               # Persona type definitions
    constants.py           # Persona settings
  causal/
    causal_compiler.py     # CausalEdgeSpec → Cypher MERGE with temporal validation
    causal_validator.py    # Validate causal edges against ontology
    attribution.py         # Causal attribution scoring
    counterfactual.py      # Counterfactual query generation
    edge_taxonomy.py       # Classify causal vs correlational vs associative edges
  feedback/
    convergence.py         # ConvergenceLoop orchestrator
    signal_weights.py      # Signal weight recalculation
    pattern_matcher.py     # Configuration pattern matching
    score_propagator.py    # Score propagation through graph
  resolution/
    resolver.py            # EntityResolver — dedup, merge, RESOLVED_FROM edges
    similarity.py          # SimilarityScorer — configurable similarity metrics
  kge/
    compound_e3d.py        # CompoundE3D model (dormant — kge_enabled=False)
    beam_search.py         # Beam search for link prediction
    ensemble.py            # Ensemble fusion strategies
    pareto_ensemble.py     # Pareto-optimal ensemble scoring
    transformations.py     # KGE transformations
  packet/
    chassis_contract.py    # inflate_ingress, deflate_egress
    packet_envelope.py     # PacketEnvelope Pydantic model
    packet_store.py        # Packet persistence
  security/
    5_llm_security.py      # LLM security (safe_exec removed — audit T1-01)
    P2_9_llm_schemas.py    # Validated LLM client (raises FeatureNotEnabled)
  utils/
    safe_eval.py           # Safe expression evaluation
    security.py            # sanitize_label() and security utilities
chassis/
  actions.py               # Thin chassis adapter
  auth/bearer.py           # BearerAuthMiddleware + tenant authorization (W3-01)
domains/
  {domain_id}_domain_spec.yaml   # One per vertical (mortgage, plasticos, healthcare, freight)
tests/
  unit/, integration/, compliance/, performance/
  contracts/               # Contract verification tests (W5-01)
  invariants/              # 31 invariant regression tests (W5-02)
  scoring/benchmark.py     # Score quality benchmark suite (W5-03)
  property/                # Hypothesis property-based tests (W5-05)
tools/
  validate_domain.py       # Domain-spec validation CLI (W5-04)
  contract_scanner.py      # Banned pattern scanner
  verify_contracts.py      # Contract verification
  audit_harness.py         # Audit infrastructure
  l9_meta_injector.py      # L9_META header injection
docs/
  SEL4_UPGRADES.md         # Technical reference for seL4 upgrade program
  SEL4_UPGRADES_EXECUTIVE.md # Executive/sales-oriented upgrade summary
  FEATURE_GATES.md         # Feature activation runbooks (W6-04)
  contracts/               # 20 contract definition files
```

## Action Handler Registry

All actions are registered in `engine/handlers.py` via `register_all()`. Each handler follows the signature: `async def handle_*(tenant: str, payload: dict) -> dict`.

| Action | Handler | Purpose |
|--------|---------|---------|
| `match` | `handle_match` | Gate-then-score graph matching |
| `sync` | `handle_sync` | Batch entity ingestion (UNWIND MERGE) |
| `admin` | `handle_admin` | Domain management, GDS trigger, calibration, feedback |
| `outcomes` | `handle_outcomes` | Outcome feedback recording for score tuning |
| `resolve` | `handle_resolve` | Entity resolution / deduplication |
| `health` | `handle_health` | Entity field-level health assessment + readiness scoring |
| `healthcheck` | `handle_healthcheck` | Alias for health (spec compatibility) |
| `enrich` | `handle_enrich` | Re-enrichment triggering based on ROI scoring |

## Admin Subactions

The `handle_admin` handler dispatches on `payload["subaction"]`. All subactions use snake_case.

| Subaction | Purpose |
|-----------|---------|
| `list_domains` | List all loaded domain specs |
| `get_domain` | Return a specific domain spec |
| `init_schema` | Initialize Neo4j schema for a domain |
| `trigger_gds` | Manually trigger a GDS algorithm run |
| `calibration_run` | Run score calibration against expected ranges (W2-01) |
| `score_feedback` | Compute weight adjustment proposal from outcomes (W2-02) |
| `apply_weight_proposal` | Apply a previously-proposed weight change (W2-02) |

## Domain Spec Top-Level Sections

The domain spec YAML (`{domain_id}_domain_spec.yaml`) is the single source of truth for all engine behavior. Schema defined in `engine/config/schema.py`.

| Section | Schema Class | Purpose |
|---------|-------------|---------|
| `ontology` | `OntologySpec` | Node types, edge types, property declarations |
| `match_entities` | `MatchEntitiesSpec` | Source/target entity definitions for matching |
| `query_schema` | `QuerySchemaSpec` | Input parameter definitions |
| `traversal` | `TraversalSpec` | Graph path patterns and hop limits |
| `gates` | `list[GateSpec]` | Hard filter definitions (10 gate types) |
| `scoring` | `ScoringSpec` | Soft ranking dimensions (13 computation types) |
| `sync` | `SyncSpec` | Entity ingestion endpoint definitions |
| `gds_jobs` | `GDSSpec` | Graph algorithm scheduling |
| `kge` | `KGESpec` | Knowledge graph embedding configuration |
| `compliance` | `ComplianceSpec` | PII fields, prohibited factors, audit config |
| `calibration` | `CalibrationSpec` | Expected score ranges for verification (W2-01) |
| `causal_edges` | `list[CausalEdgeSpec]` | Causal relationship declarations |

## Lifecycle (engine/boot.py)

- `GraphLifecycle` implements `chassis.chassis_app.LifecycleHook`
- Env var: `L9_LIFECYCLE_HOOK=engine.boot:GraphLifecycle`
- Startup: initializes `GraphDriver`, `DomainPackLoader`, GDS scheduler, runs weight-sum assertion (W1-02)
- Shutdown: closes Neo4j driver, stops GDS scheduler
- This is the ONLY file besides `handlers.py` that imports chassis modules

## Subsystem Dependency Map

```
handlers.py (chassis bridge — registers all 8 actions)
  ├── config/loader.py → config/schema.py → config/settings.py
  ├── gates/compiler.py → gates/types/ → gates/null_semantics.py
  ├── scoring/assembler.py → scoring/calibration.py, scoring/confidence.py, scoring/pareto.py
  ├── traversal/assembler.py → traversal/resolver.py
  ├── sync/generator.py
  ├── compliance/engine.py → compliance/pii.py, compliance/prohibited_factors.py
  ├── graph/driver.py (ALL Neo4j access goes through here — circuit breaker + timeout)
  ├── health/ → config/loader.py, graph/driver.py
  ├── intake/ → config/loader.py, config/schema.py
  ├── personas/ (self-contained — no engine imports except constants)
  ├── causal/ → config/schema.py, utils/security.py
  ├── feedback/ → config/schema.py, graph/driver.py
  ├── resolution/ → config/schema.py, graph/driver.py
  └── kge/ (dormant — activated via admin subaction when kge_enabled=True)

boot.py (lifecycle — ONLY file besides handlers.py that imports chassis)
```

## Feature Flags (engine/config/settings.py)

All flags are in the `Settings` class, controllable via environment variables.

### Core Engine
| Flag | Default | Purpose |
|------|---------|---------|
| `gds_enabled` | `True` | GDS scheduler toggle |
| `kge_enabled` | `False` | KGE embedding scoring dimension |
| `pareto_enabled` | `True` | Multi-objective Pareto-optimal scoring |
| `pareto_weight_discovery_enabled` | `False` | Learned weight trade-offs from outcomes |

### Wave 1 — Invariant Hardening
| Flag | Default | Purpose |
|------|---------|---------|
| `domain_strict_validation` | `True` | Cross-reference validation at domain load |
| `score_clamp_enabled` | `True` | Clamp dimension scores to [0, 1] |
| `strict_null_gates` | `True` | Reject gates with null-resolved parameters |
| `max_hop_hard_cap` | `10` | Maximum traversal hops |
| `param_strict_mode` | `True` | Raise on derived parameter resolution failures |

### Wave 2 — Scoring Refinement
| Flag | Default | Purpose |
|------|---------|---------|
| `feedback_enabled` | `False` | Outcome feedback loop |
| `confidence_check_enabled` | `True` | Ensemble confidence bounds |
| `monoculture_threshold` | `0.70` | Single-dimension dominance cap |
| `ensemble_max_divergence` | `0.30` | GDS/KGE score divergence cap |
| `score_normalize` | `False` | Post-query min-max normalization |

### Entity Resolution
| Flag | Default | Purpose |
|------|---------|---------|
| `resolution_min_confidence` | `0.6` | Minimum similarity for dedup merge |
| `resolution_density_tolerance` | `0.05` | Density tolerance for resolution |
| `resolution_mfi_tolerance` | `5.0` | MFI tolerance for resolution |

## Existing Capability Registry (Do NOT Duplicate)

Before building any of the following, check if it already exists:

| Capability | Location | Origin |
|-----------|----------|--------|
| Score clamping to [0, 1] | `engine/scoring/assembler.py` → `_clamp_expression()` | W1-02 |
| Weight-sum validation | `engine/handlers.py` → `handle_match()` | W1-02 |
| Startup weight assertion | `engine/boot.py` → `_assert_default_weight_sum()` | W1-02 |
| Domain-spec cross-ref validation | `engine/config/schema.py` model validators | W1-01 |
| Gate null-parameter checking | `engine/gates/compiler.py` → `validate_gates()` | W1-03 |
| Traversal bounds enforcement | `engine/traversal/assembler.py` → `validate_traversal()` | W1-04 |
| Parameter strict mode | `engine/traversal/resolver.py` → `ValidationError` on failure | W1-05 |
| Score calibration | `engine/scoring/calibration.py` → `ScoreCalibration` | W2-01 |
| Confidence bounds | `engine/scoring/confidence.py` → `ConfidenceChecker` | W2-03 |
| Weight feedback loop | `engine/scoring/feedback.py` | W2-02 |
| Score normalization | `engine/handlers.py` post-query pass | W2-04 |
| Entity resolution / dedup | `engine/resolution/resolver.py` → `EntityResolver` | — |
| Causal edge compilation | `engine/causal/causal_compiler.py` → `CausalCompiler` | — |
| Persona composition | `engine/personas/composer.py` | — |
| Health / readiness scoring | `engine/health/` | — |
| CRM intake pipeline | `engine/intake/` | — |
| Pareto multi-objective scoring | `engine/scoring/pareto.py` | — |
| Convergence feedback loop | `engine/feedback/convergence.py` → `ConvergenceLoop` | — |

## Where to Put Code (Decision Tree)

| Task | Target File | Also Update |
|------|-------------|-------------|
| New gate type | `engine/gates/types/all_gates.py` (extend `BaseGate`) | `GateType` enum in `schema.py` |
| New scoring computation | `engine/scoring/assembler.py` (add `_compile_*` method) | `ComputationType` enum in `schema.py` |
| New admin subaction | `engine/handlers.py` → `handle_admin()` dispatch block | Admin Subactions table in this file |
| New action handler | `engine/handlers.py` (new `handle_*` function) | `register_all()` in same file |
| New domain spec section | `engine/config/schema.py` (new Pydantic model) | `DomainSpec` field + this file |
| New feature flag | `engine/config/settings.py` → `Settings` class | Feature Flags table in this file |
| Neo4j queries | ALWAYS through `engine/graph/driver.py` | Never raw driver sessions |
| New unit test | `tests/unit/` | Pure functions only — no Neo4j |
| New integration test | `tests/integration/` | testcontainers-neo4j |
| Compliance logic | `engine/compliance/` | Never in `chassis/` |
| Startup/shutdown logic | `engine/boot.py` → `GraphLifecycle` | — |

## Code Style

- **Type hints everywhere**: Function signatures, class attributes, variables where ambiguous.
- **Async by default**: All I/O operations (Neo4j, PostgreSQL, Redis) use `async`/`await`.
- **Pydantic models for data**: Use `BaseModel` (frozen where appropriate) for all structured data.
- **Ruff for formatting**: Run `ruff format .` before committing (Black-compatible 88-char line length).
- **structlog for logging**: JSON output, include `tenant`, `trace_id`, `action` in log context.
- **Exception messages**: Assign to variable first (`msg = f"..."; raise ValueError(msg)`) — avoids EM101/EM102.
- **Nullable params**: Explicit union (`x: str | None = None`) — never implicit `Optional`.
- **Datetime**: Always timezone-aware (`datetime.now(tz=UTC)`).

## Key Commands

```bash
# Setup
make setup              # Install deps, setup pre-commit hooks, verify Neo4j connection

# Development
make dev                # Start docker-compose (app + Neo4j + Redis + Prometheus + Grafana)
make test               # Run full pytest suite (unit + integration + compliance)
make test-unit          # Unit tests only (gates, scoring, parameter resolution)
make test-integration   # Integration tests with testcontainers-neo4j
make lint               # ruff check + mypy
make lint-fix           # ruff check --fix + ruff format .

# Cypher validation
make cypher-lint        # Check all generated Cypher for injection vectors

# GDS operations
make gds-trigger JOB=louvain DOMAIN=plasticos   # Manual GDS job trigger

# Deployment
make build              # Build Docker image
make deploy ENV=staging # Deploy to target environment (Railway/ArgoCD)
```

## Critical Gotchas (Do NOT Do These)

1. **Never import FastAPI in engine code.** The chassis owns HTTP. Engine handlers receive `(tenant, payload)` and return `dict`. No routes, no middleware, no CORS config.

2. **Always sanitize labels before Cypher interpolation.** Use `sanitize_label()` from `engine.utils.security` on any label/type from domain specs:
   ```python
   # BAD
   cypher = f"MATCH (n:{spec.targetnode})"

   # GOOD
   from engine.utils.security import sanitize_label
   sanitized = sanitize_label(spec.targetnode)
   cypher = f"MATCH (n:{sanitized})"
   ```

3. **PacketEnvelope is mandatory for persisted events.** Match results, sync events, GDS job outcomes must be wrapped via `inflate_ingress()` / `deflate_egress()` at the chassis boundary. Do NOT return plain dicts from handlers without wrapping.

4. **Tenant resolution is chassis-only.** Do NOT implement `resolve_tenant()` functions in the engine. Do NOT use FastAPI `Depends(resolve_tenant)`. Tenant comes as the first argument to handlers, resolved by chassis.

5. **Gate compilation order matters.** Traversal → Gates → Scoring. The gate WHERE clause depends on entities materialized by traversal. Scoring depends on gates having filtered the candidate set.

6. **GDS jobs must use real Cypher, not stubs.** The scheduler in `engine/gds/scheduler.py` executes actual Neo4j GDS procedures. Do NOT mock these in production code.

7. **All Neo4j access goes through GraphDriver.** Never construct raw driver sessions. `GraphDriver.execute_query()` applies circuit breaker and timeout. See Contract 24.

8. **Check the Capability Registry before building.** The table above lists capabilities that already exist. Use them — don't recreate them.

## File Import Patterns

```python
# Chassis integration (ONLY in engine/handlers.py and engine/boot.py)
from chassis.router import register_handler       # handlers.py only
from chassis.chassis_app import LifecycleHook      # boot.py only

# Domain specs
from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec, GateSpec, ScoringDimensionSpec
from engine.config.settings import settings

# Gate compilation
from engine.gates.compiler import GateCompiler
from engine.gates.types.all_gates import RangeGate, ThresholdGate, BooleanGate

# Scoring
from engine.scoring.assembler import ScoringAssembler
from engine.scoring.calibration import ScoreCalibration
from engine.scoring.confidence import ConfidenceChecker

# Traversal / Sync
from engine.traversal.assembler import TraversalAssembler
from engine.sync.generator import SyncGenerator, SyncStrategy

# GDS / Graph
from engine.gds.scheduler import GDSScheduler
from engine.graph.driver import GraphDriver

# PacketEnvelope
from engine.packet.chassis_contract import inflate_ingress, deflate_egress
from engine.packet.packet_envelope import PacketEnvelope, PacketMetadata

# Security
from engine.utils.security import sanitize_label

# Subsystems
from engine.resolution.resolver import EntityResolver
from engine.causal.causal_compiler import CausalCompiler
from engine.personas.composer import PersonaComposer  # self-contained
from engine.health.api import handle_health
from engine.intake.api import handle_intake
from engine.feedback.convergence import ConvergenceLoop
```

## Contracts (1–20)

Read these before writing engine code. Enforced by `tools/contract_scanner.py` and `tools/verify_contracts.py`.

### Layer 1 — Chassis Boundary (1–5)

| # | Contract | Rule |
|---|----------|------|
| 1 | Single Ingress | Only `POST /v1/execute` and `GET /v1/health`. Engine NEVER imports FastAPI/Starlette. |
| 2 | Handler Interface | `async def handle_*(tenant: str, payload: dict) -> dict`. Register via `chassis.router.register_handler()`. `handlers.py` is the ONLY file importing chassis modules (plus `boot.py`). |
| 3 | Tenant Isolation | Tenant resolved BY chassis. Engine receives tenant as string. Every Neo4j query scopes to tenant database. No cross-tenant reads. |
| 4 | Observability Inherited | Engine NEVER configures structlog/Prometheus/logging handlers. Uses `structlog.get_logger(__name__)` only. |
| 5 | Infrastructure is Template | Engine NEVER creates Dockerfile, docker-compose, CI pipeline, Terraform. All in `l9-template`. |

### Layer 2 — Packet Protocol (6–8)

| # | Contract | Rule |
|---|----------|------|
| 6 | PacketEnvelope Only | Every inter-service payload is a PacketEnvelope. `inflate_ingress()` at entry, `deflate_egress()` at exit. |
| 7 | Immutability + Hash | PacketEnvelope is frozen. Mutations via `.derive()`. `content_hash` (SHA-256) is UNIQUE constraint. Design for idempotency. |
| 8 | Lineage + Audit | Derived packets set `parent_id`, `root_id`, increment `generation`. `hop_trace` is append-only. Engine NEVER bypasses lineage. |

### Layer 3 — Security (9–11)

| # | Contract | Rule |
|---|----------|------|
| 9 | Cypher Injection Prevention | All labels/types pass `sanitize_label()` (regex: `^[A-Za-z_][A-Za-z0-9_]*$`). Values always parameterized (`$batch`, `$query`). |
| 10 | Prohibited Factors | Compliance fields (race, ethnicity, religion, gender, age, disability, familial_status, national_origin) blocked at compile-time. |
| 11 | PII Handling | PII fields declared in spec `compliance.pii.fields`. Handling per domain: `hash | encrypt | redact | tokenize`. Engine NEVER logs PII values. |

### Layer 4 — Engine Architecture (12–16)

| # | Contract | Rule |
|---|----------|------|
| 12 | Domain Spec is Source of Truth | All behavior from `{domain_id}_domain_spec.yaml` → `DomainConfig` (Pydantic). Never raw YAML/dicts. Specs are untrusted input — validate everything. |
| 13 | Gate-Then-Score Architecture | Gates (hard filter) → Scoring (soft rank). 10 gate types: range, threshold, boolean, composite, enummap, exclusion, selfrange, freshness, temporalrange, traversal. 13 scoring computations: geodecay, lognormalized, communitymatch, inverselinear, candidateproperty, weightedrate, pricealignment, temporalproximity, customcypher, traversalalias, kge, variantdiscovery, ensembleconfidence. |
| 14 | NULL Semantics | Every gate declares `null_behavior: pass | fail`. Compiler handles it — callers don't. |
| 15 | Bidirectional Matching | Gates with `invertible: true` swap candidate ↔ query. Gates with `match_directions: [specific]` scope to direction. |
| 16 | File Structure is Fixed | See Directory Structure above. Do NOT create new top-level directories without architectural approval. |

### Layer 5 — Testing + Quality (17–18)

| # | Contract | Rule |
|---|----------|------|
| 17 | Test Requirements | Unit: gate compilation, scoring math, param resolution. Integration: testcontainers-neo4j. Compliance: prohibited factors blocked at compile time. Performance: <200ms p95 match latency. |
| 18 | L9_META on Every File | Every tracked file carries an L9_META header (schema v1). Injected by `tools/l9_meta_injector.py`. |

### Layer 6 — Graph Intelligence (19–20)

| # | Contract | Rule |
|---|----------|------|
| 19 | GDS Jobs Declarative | Algorithms declared in `spec.gds_jobs`. Schedule type: `cron | manual`. Projections spec-driven. |
| 20 | KGE Embeddings | CompoundE3D, 256-dim default. Beam search (width=10, depth=3). KGE scores feed the same WITH clause as all others. Embeddings domain-specific, never cross-tenant. |

### Layer 7 — Hardening (21–24)

| # | Contract | Rule |
|---|----------|------|
| 21 | Feature Flag Discipline | Every behavioral change that alters query results, adds validation, or activates dormant code MUST be gated by a `bool` flag in `engine/config/settings.py`. Flag naming: `{area}_{behavior}` (e.g., `score_clamp_enabled`). Default `True` for safety validators, `False` for experimental features. Document in `docs/FEATURE_GATES.md`. |
| 22 | Scoring Weight Ceiling | Sum of all default scoring weights MUST be ≤ 1.0. Enforced at startup by `engine/boot.py _assert_default_weight_sum()`. When adding a new weight dimension, REDUCE existing defaults to maintain the ceiling. Per-request weights validated in `handle_match()`. |
| 23 | Admin Subaction Registration | Every subaction MUST: (a) be documented in the Admin Subactions table above, (b) use snake_case naming, (c) return `{"status": "ok"|"error", "subaction": "<name>"}`, (d) log invocation with tenant and trace_id, (e) validate required keys with `_require_key()`. |
| 24 | Resilience Patterns | All Neo4j queries go through `GraphDriver.execute_query()` — never raw sessions. Circuit breaker: `NEO4J_CIRCUIT_THRESHOLD=3`, `NEO4J_CIRCUIT_COOLDOWN=30s`. All caches MUST be bounded (maxsize) + time-limited (TTL). No unbounded dicts as caches. No new module-level mutable globals — use `EngineState`. |

## System State

### Open PRs (seL4 Upgrade Program)

Update this section when merging PRs.

| PR | Wave | Title | Status |
|----|------|-------|--------|
| [#57](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/57) | 1 | Invariant & Validation Hardening | OPEN |
| [#58](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/58) | 2 | Refinement-Inspired Scoring | OPEN |
| [#59](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/59) | 3 | Capability & Access Control | OPEN |
| [#60](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/60) | 4 | State Management & Resilience | OPEN |
| [#64](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/64) | 5 | Correctness Tooling & Verification | OPEN |
| [#63](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/63) | 6 | Dormant Feature Activation | OPEN |
| [#65](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/65) | — | seL4 Technical & Executive Documentation | OPEN |

### Dormant Subsystems (built, not activated)

| System | Lines | Blocker | Activation |
|--------|-------|---------|------------|
| KGE (CompoundE3D + BeamSearch) | ~1,500 | `kge_enabled=False` | Wave 6 merge → `trigger_kge` admin subaction |
| GDPR erasure | ~50 | `erase_subject()` unwired | Wave 6 merge → `erase_subject` admin subaction |
| PostgreSQL persistence | 0 | Not in docker-compose | Provision PostgreSQL → wire `asyncpg.Pool` |
| LLM security | ~200 | `ValidatedLLMClient` raises `FeatureNotEnabled` | Set `LLM_PROVIDER` + `LLM_API_KEY` |

## Imports to Reference (Not Duplicate)

- `@docs/L9_Platform_Architecture.md` — Chassis contract, universal envelope, action handler signature
- `@docs/L9_AI_Constellation_Infrastructure_Reference.md` — PacketEnvelope schema, memory substrate, observability
- `@docs/SEL4_UPGRADES.md` — Technical reference for seL4 upgrade program (6 waves, 26 enhancements)
- `@docs/SEL4_UPGRADES_EXECUTIVE.md` — Executive/sales-oriented upgrade summary

## Contract Docs

Read the relevant contract before touching the corresponding subsystem. Enforced by `tools/contract_scanner.py` and `tools/verify_contracts.py`.

| Subsystem | Read These First |
|-----------|-----------------|
| `engine/gates/`, `engine/config/schema.py` | FIELD_NAMES, CYPHER_SAFETY, BANNED_PATTERNS, PYDANTIC_YAML_MAPPING |
| `engine/handlers.py`, `chassis/` | HANDLER_PAYLOADS, METHOD_SIGNATURES, DEPENDENCY_INJECTION, RETURN_VALUES |
| `engine/packet/`, PacketEnvelope | PACKET_ENVELOPE_FIELDS, SHARED_MODELS, DELEGATION_PROTOCOL, PACKET_TYPE_REGISTRY |
| `tests/` | TEST_PATTERNS, ERROR_HANDLING |
| `engine/compliance/` | OBSERVABILITY, MEMORY_SUBSTRATE_ACCESS |
| `domains/`, domain spec versioning | DOMAIN_SPEC_VERSIONING, FEEDBACK_LOOPS, NODE_REGISTRATION |
| `.env.template`, env var naming | ENV_VARS |

## Testing Patterns

- **Unit tests** (`tests/unit/`): Pure functions — gate compilation, scoring math, parameter resolution. No Neo4j.
- **Integration tests** (`tests/integration/`): Full match pipeline with testcontainers-neo4j. Seed sample data, execute match, verify candidates + scores.
- **Compliance tests** (`tests/compliance/`): Verify prohibited factors blocked at compile time.
- **Contract tests** (`tests/contracts/`): One test per CEG contract (20+). Exercises contract boundaries (W5-01).
- **Invariant tests** (`tests/invariants/`): 31 regression tests, one per audit defect. Tagged `@pytest.mark.finding("T1-03")` (W5-02).
- **Scoring benchmark** (`tests/scoring/benchmark.py`): Good/bad pair separation, distribution moments. CI fails if separation < 0.20 (W5-03).
- **Property tests** (`tests/property/`): Hypothesis-based tests for GateCompiler and ScoringAssembler (W5-05).
