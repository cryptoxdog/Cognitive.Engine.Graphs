# Architecture — Cognitive Engine Graphs (CEG)

> Agent reference: read this before creating files, modifying handlers, or touching the engine/chassis boundary.
> Full intelligence-layer detail: `INTELLIGENCE_ARCHITECTURE.md`

## System Identity

CEG is a **domain-configurable graph matching and scoring engine**. It transforms domain data into inference-bearing Neo4j graph structures, executes gate-then-score Cypher queries, and closes the feedback loop through signal weight learning, causal attribution, and entity resolution.

**Version:** 2.0.0 | **Stack:** Python 3.12 + Neo4j 5.x + GDS + Pydantic v2 + FastAPI (chassis only)

---

## Structural Law: Engine / Chassis Separation

```
engine/       ← Core logic. ZERO FastAPI imports. Receives (tenant, payload) → dict.
chassis/      ← Thin HTTP adapter. Calls engine. Owns request/response lifecycle.
```

**Violation = critical defect.** Engine code that imports `fastapi`, `starlette`, or `uvicorn` will be rejected by CI.

---

## Directory Map

```
engine/
  handlers.py          8 action handlers: match, sync, admin, outcomes, resolve, health, healthcheck, enrich
  boot.py              Startup/shutdown lifecycle, weight-sum assertion
  config/              DomainSpec YAML schema, Settings singleton, loader
  gates/               Gate → WHERE clause compiler (10 gate types)
  scoring/             Scoring → WITH clause (13 computation types), calibration, confidence
  traversal/           MATCH clause generator, parameter resolver
  sync/                UNWIND MERGE/MATCH SET Cypher generator
  gds/                 APScheduler for GDS jobs (Louvain, co-occurrence, power-law pruning)
  graph/               Neo4j AsyncDriver wrapper + circuit breaker
  compliance/          PII enforcement, audit trail, prohibited factors
  health/              AI readiness scoring, gap prioritization, re-enrichment
  intake/              CRM-to-YAML ingestion pipeline
  personas/            Algebraic trait vector composition
  causal/              Causal edge compiler, BFS serializer, counterfactual generator
  feedback/            Convergence loop, signal weights (lift formula + CI), drift detection
  resolution/          Entity resolver, multi-signal similarity, deduplication
  kge/                 CompoundE3D embeddings — DORMANT (kge_enabled=False)

chassis/               FastAPI app, routers, middleware, request validation
domains/               {domain_id}_domain_spec.yaml — one per vertical
contracts/             24 enforced behavioral contracts
tests/
  unit/                Pure functions, no Neo4j
  integration/         testcontainers-neo4j full pipeline
  compliance/          Prohibited factors blocked at compile time
  contracts/           Contract scanner assertions
  invariants/          Engine invariant property tests
  property/            Hypothesis-based property tests
tools/
  contract_scanner.py  Scans generated Cypher for contract violations
  verify_contracts.py  Asserts all 24 contracts pass
  validate_domain.py   Validates domain spec YAML against Pydantic schema
```

---

## Request Flow

```
HTTP POST /v1/{tenant}/{action}
  └── chassis/routers.py        validates PacketEnvelope
      └── engine/handlers.py    dispatches to action handler
          └── DomainSpec         loaded from domains/{domain_id}_domain_spec.yaml
              ├── gates/          compile WHERE clauses
              ├── traversal/      compile MATCH clauses
              ├── scoring/        compile WITH + RETURN (weighted scoring)
              └── graph/driver    execute_query() → results
                  └── feedback/   if feedbackloop.enabled → convergence cycle
```

## Feedback / Convergence Cycle

```
Outcome recorded → fingerprint stored → ConvergenceLoop triggers:
  ScorePropagator   → boost/penalize matching configurations
  SignalWeightCalc  → lift formula + 95% CI → DimensionWeight nodes in Neo4j
  CounterfactualGen → generate alternative scenarios for losses
  DriftDetector     → χ²-divergence check against historical distribution
                           ↓
  ScoringAssembler.load_learned_weights() → spec_weight × learned_weight = final
```

---

## Domain Spec (Source of Truth)

All matching behavior is declared in YAML. No hardcoded business logic in engine code.

```yaml
# domains/example_domain_spec.yaml skeleton
version: "1.0"
domain_id: example
targetnode: Contact
gates: [...]         # WHERE clause definitions
scoring: [...]       # WITH clause + weight definitions
traversal: [...]     # MATCH clause definitions
feedbackloop:
  enabled: false
causal:
  enabled: false
```

**Key rule:** If behavior can be expressed in the domain spec, it belongs there — not in Python.

---

## Contracts (24 Enforced)

Behavioral contracts are checked by `tools/contract_scanner.py` on every CI run.  
Full contract definitions: `docs/contracts/` and `.claude/rules/contracts.md`

Critical contracts include:
- `C-001` No raw label interpolation into Cypher
- `C-002` All queries routed through `GraphDriver.execute_query()`
- `C-003` Engine imports no FastAPI/Starlette/uvicorn
- `C-004` No PII values in log output
- `C-005` All caches bounded (TTLCache or equivalent)

---

## Feature Flags

All behavioral changes are gated. Flags live in `engine/config/settings.py`.

| Flag | Controls |
|------|----------|
| `feedback_loop_enabled` | Convergence cycle activation |
| `kge_enabled` | CompoundE3D embeddings (dormant) |
| `score_clamp_enabled` | Score output bounded to [0, 1] |
| `causal_enabled` | Causal edge compilation |
| `entity_resolution_enabled` | Deduplication pipeline |

---

## Where to Put Code

| Task | Location |
|------|----------|
| New gate type | `engine/gates/` + register in gate enum |
| New scoring dimension | `engine/scoring/` + add to assembler |
| New action handler | `engine/handlers.py` + update `register_all()` |
| New HTTP route | `chassis/routers.py` only |
| New domain vertical | `domains/{id}_domain_spec.yaml` |
| New contract | `contracts/` + `tools/contract_scanner.py` |

> Cross-reference: `.claude/rules/routing.md` for exhaustive routing rules.
