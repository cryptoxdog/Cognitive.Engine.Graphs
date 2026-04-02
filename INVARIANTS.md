<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [architecture]
tags: [invariants, contracts, enforcement]
owner: platform
status: active
/L9_META -->

# INVARIANTS.md — CEG Immutable Architectural Rules

**Purpose**: Codifies 24 immutable contracts (C-001 to C-024) that must hold across all repository states.

**Source**: .claude/rules/contracts.md (SHA: 1211d8e), .cursorrules (SHA: 4a51555)

**Last Verified**: SHA 358d15d (2026-04-02)

---

## Scope

All contracts are enforced via:
- `tools/contract_scanner.py` — banned pattern detection
- `tools/verify_contracts.py` — contract file existence and wiring validation
- Pre-commit hooks — local enforcement before commit
- CI pipeline — repository-wide enforcement on every PR
- LLM review agents — CodeRabbit, Qodo, Claude with contract awareness

**Branch protection**: All 5 enforcement layers required. No bypass.

---

## 24 Contracts (C-001 to C-024)

### Layer 1: Chassis Boundary (C-001 to C-005)

**C-001: Single Ingress**
- HTTP surface: `POST /v1/{tenant}/{action}` and `GET /v1/health` only
- Engine NEVER imports `fastapi`, `starlette`, or `uvicorn`
- Engine NEVER creates routes, APIRouter, or app factories
- **Enforcement**: Contract scanner (ARCH-001, ARCH-002, ARCH-003), CI grep check

**C-002: Handler Interface**
- Engine exposes: `async def handle_<action>(tenant: str, payload: dict) -> dict`
- Registration: `chassis.router.register_handler("match", handle_match)` in engine/handlers.py
- handlers.py is the ONLY engine file importing chassis modules (plus boot.py)
- **Enforcement**: Contract scanner signature validation

**C-003: Tenant Isolation**
- Tenant resolved BY chassis (5-level: header → subdomain → key prefix → envelope → default)
- Engine receives tenant as string argument
- Engine NEVER resolves tenant
- Every Neo4j query scopes to tenant database
- No cross-tenant reads
- **Enforcement**: Manual code review (no automated check yet — see Known Unknowns)

**C-004: Observability Inherited**
- Engine NEVER configures structlog, Prometheus, or logging handlers
- Chassis provides: structured JSON logging, trace_id propagation, /metrics endpoint
- Engine uses: `structlog.get_logger(__name__)` only
- **Enforcement**: Contract scanner (OBS-001, OBS-002)

**C-005: Infrastructure is Template**
- Engine NEVER creates: Dockerfile, docker-compose, CI pipeline, Terraform modules
- All exist in l9-template
- Engine adds engine-specific env vars to .env.template only
- **Enforcement**: CODEOWNERS + PR review

### Layer 2: Packet Protocol (C-006 to C-008)

**C-006: PacketEnvelope Only**
- Every inter-service payload is a PacketEnvelope
- `inflate_ingress()` at boundary entry
- `deflate_egress()` at boundary exit
- Engine code between boundaries works with typed dicts/Pydantic (never raw envelopes)
- **Enforcement**: Contract scanner + integration tests

**C-007: Immutability + Content Hash**
- PacketEnvelope is frozen (Pydantic `frozen=True`)
- Mutations create new packets via `.derive()`
- `content_hash` (SHA-256 of canonical payload) is a UNIQUE DB constraint
- Design all writes for idempotency — duplicate content_hash silently rejected
- **Enforcement**: Contract scanner (SHARED-001) + database schema constraint

**C-008: Lineage + Audit**
- Every derived packet sets `parent_id`, `root_id`, increments `generation`
- `hop_trace` is append-only (each node adds a HopEntry)
- `delegation_chain` carries scoped authorization through multi-hop flows
- Engine NEVER bypasses lineage — all packets from `.derive()` or `PacketEnvelope.create()`
- **Enforcement**: Contract scanner (DEL-001, DEL-002) + integration tests

### Layer 3: Security (C-009 to C-011)

**C-009: Cypher Injection Prevention**
- All Neo4j labels and relationship types MUST pass `sanitize_label()` before interpolation
- Regex: `^[A-Za-z_][A-Za-z0-9_]*$`
- Cypher VALUES always use parameterized queries (`$batch`, `$query`)
- Only labels/types are interpolated (after sanitization)
- **Enforcement**: `make cypher-lint` + contract scanner (SEC-001 through SEC-007)

**C-010: Prohibited Factors**
- Compliance fields (race, ethnicity, religion, gender, age, disability, familial_status, national_origin) blocked at compile-time during gate validation
- If domain spec references prohibited field → gate compilation fails (not runtime error)
- `audit_on_violation: true` — every blocked attempt logged
- **Enforcement**: Compliance tests (tests/compliance/)

**C-011: PII Handling**
- PII fields declared in `domain_spec.compliance.pii.fields`
- Handling mode per domain: hash | encrypt | redact | tokenize
- Encryption key source: env | vault | kms (declared in spec, never hardcoded)
- Engine NEVER logs PII values (structlog filters set by chassis)
- **Enforcement**: Contract scanner + structlog filter tests

### Layer 4: Engine Architecture (C-012 to C-016)

**C-012: Domain Spec Source of Truth**
- All matching behavior from `{domain_id}_domain_spec.yaml`
- DomainPackLoader (`engine/config/loader.py`) reads YAML → DomainConfig (Pydantic)
- Every downstream module consumes DomainConfig (never raw YAML, never raw dicts)
- Domain specs are untrusted input (uploaded via admin endpoints) → validate everything
- **Enforcement**: Pydantic validation + integration tests

**C-013: Gate-Then-Score Architecture**
- Matching is two-phase: gates (hard filter) → scoring (soft rank)
- All gate logic compiles to Cypher WHERE clauses (zero post-filtering in Python)
- All scoring dimensions compile to single WITH/ORDER BY clause (no iterative scoring)
- **10 gate types**: range, threshold, boolean, composite, enum_map, exclusion, self_range, freshness, temporal_range, traversal
- **13 scoring computations**: geo_decay, log_normalized, community_match, inverse_linear, candidate_property, weighted_rate, price_alignment, temporal_proximity, custom_cypher, pareto, ensemble, feedback, confidence
- **Enforcement**: Unit tests (gate compilation), integration tests (full pipeline)

**C-014: NULL Semantics Deterministic**
- Every gate declares `null_behavior: pass | fail`
- `pass` → wraps predicate in `(candidate.prop IS NULL OR <predicate>)`
- `fail` → NULL candidate rejected
- Per-gate, not global
- Compiler handles it (callers don't)
- **Enforcement**: Unit tests (null semantics per gate type)

**C-015: Bidirectional Matching**
- Gates with `invertible: true` swap `candidate_prop ↔ query_param` when match direction reverses
- Gates with `match_directions: [specific]` only fire for those directions
- Scoring dimensions similarly scope to `match_directions`
- Compiler handles inversion (gate implementations are direction-unaware)
- **Enforcement**: Unit tests (inversion logic)

**C-016: File Structure Fixed**
- `engine/handlers.py` → ONLY chassis bridge (`register_all`)
- `engine/config/` → Domain spec schema + loader + settings + units
- `engine/gates/` → Gate compiler + null semantics + registry + types/
- `engine/scoring/` → Scoring assembler
- `engine/traversal/` → Traversal assembler + resolver
- `engine/sync/` → Sync generator
- `engine/gds/` → GDS scheduler (APScheduler from spec.gds_jobs)
- `engine/graph/` → Neo4j async driver wrapper
- `engine/compliance/` → Prohibited factors + PII + audit
- `engine/packet/` → PacketEnvelope bridge (chassis_contract.py)
- `engine/utils/` → safe_eval, security (sanitize_label)
- `chassis/` → Thin chassis adapter (actions.py)
- `domains/` → `{domain_id}_domain_spec.yaml` per vertical
- Do NOT create new top-level directories without architectural approval
- **Enforcement**: CODEOWNERS + PR review

### Layer 5: Testing + Quality (C-017 to C-018)

**C-017: Test Requirements**
- Unit tests: gate compilation, scoring math, parameter resolution, null semantics per gate
- Integration tests: testcontainers-neo4j (do NOT mock Neo4j driver)
- Compliance tests: verify prohibited factors blocked at compile time
- Performance: <200ms p95 match latency
- Validation: compiled Cypher for plasticos_spec.yaml must match hand-verified reference output
- **Enforcement**: CI pytest run (unit + integration + compliance)

**C-018: L9_META Headers**
- Every tracked file carries L9_META header (schema version 1)
- Fields: l9_schema, origin, engine, layer, tags, owner, status
- Format varies by filetype (YAML comment, HTML comment, Python docstring, JSON key, TOML table)
- Injected by `tools/l9_meta_injector.py` (not manually)
- **Enforcement**: Pre-commit hook + CI check

### Layer 6: Graph Intelligence (C-019 to C-020)

**C-019: GDS Declarative**
- Graph Data Science algorithms (Louvain, similarity, etc.) declared in `spec.gds_jobs`
- Schedule type: cron | manual
- Projections declare `node_labels` + `edge_types`
- Scheduler reads spec and creates APScheduler jobs (no hardcoded algorithm calls)
- GDS write targets (`write_property`, `write_to`, `write_edge`) spec-driven
- **Enforcement**: GDS scheduler tests

**C-020: KGE Embeddings**
- Model: CompoundE3D, 256-dim default
- Training relations from `domain_spec.ontology.edges`
- Beam search (width=10, depth=3) for link prediction
- Ensemble strategy: weighted_average | rank_aggregation | mixture_of_experts
- KGE scores are a scoring dimension (feed into same WITH clause as all others)
- Vector index stored in Neo4j (cosine similarity)
- Embeddings are domain-specific, never shared cross-tenant
- **Enforcement**: Integration tests (when `kge_enabled=True`)

### Layer 7: Hardening (C-021 to C-024)

**C-021: Feature Flag Discipline**
- Every behavioral change gated by bool flag in `engine/config/settings.py`
- True = safety/production-ready
- False = experimental
- **Enforcement**: Code review + FEATURE_FLAGS.md documentation
- **See**: FEATURE_FLAGS.md for complete flag inventory

**C-022: Scoring Weight Ceiling**
- Default weights sum ≤ 1.0
- Enforced at startup via `engine/boot.py::_assert_default_weight_sum()`
- When adding new weight: reduce existing weights proportionally
- **Enforcement**: Startup assertion (fails app boot if violated)

**C-023: Admin Subaction Registration**
- snake_case naming
- Return `{status, subaction}` dict
- Log with tenant context
- Validate inputs with `_require_key()`
- **Enforcement**: Code review + integration tests

**C-024: Resilience Patterns**
- All Neo4j via GraphDriver (circuit breaker: 3 failures / 30s window)
- Bounded caches only (TTLCache or equivalent)
- No module-level globals (use Settings singleton or dependency injection)
- **Enforcement**: Contract scanner + code review

---

## Enforcement Matrix

| Contract | CI Automation | Human Review Required |
|----------|---------------|----------------------|
| C-001 | ✅ Contract scanner ARCH-001/002/003 | ❌ |
| C-002 | ✅ Signature validation | ❌ |
| C-003 | ❌ No static check | ✅ Manual verification |
| C-004 | ✅ Contract scanner OBS-001/002 | ❌ |
| C-005 | ❌ CODEOWNERS | ✅ PR review |
| C-006 | ✅ Integration tests | ❌ |
| C-007 | ✅ Contract scanner SHARED-001 + DB constraint | ❌ |
| C-008 | ✅ Contract scanner DEL-001/002 | ❌ |
| C-009 | ✅ make cypher-lint + SEC-001 to SEC-007 | ❌ |
| C-010 | ✅ Compliance tests | ❌ |
| C-011 | ✅ Structlog filter tests | ❌ |
| C-012 | ✅ Pydantic validation | ❌ |
| C-013 | ✅ Unit + integration tests | ❌ |
| C-014 | ✅ Unit tests | ❌ |
| C-015 | ✅ Unit tests | ❌ |
| C-016 | ❌ CODEOWNERS | ✅ Architectural approval |
| C-017 | ✅ CI pytest | ❌ |
| C-018 | ✅ Pre-commit + CI | ❌ |
| C-019 | ✅ GDS tests | ❌ |
| C-020 | ✅ Integration tests (when enabled) | ❌ |
| C-021 | ❌ Code review | ✅ Flag must exist in settings.py |
| C-022 | ✅ Startup assertion | ❌ |
| C-023 | ✅ Integration tests | ❌ |
| C-024 | ✅ Contract scanner + code review | ✅ Circuit breaker config |

**Automated**: 18/24 (75%)  
**Manual**: 6/24 (25%)

---

## Invariant Addition Protocol

To add a new contract (C-025+):
1. Document in `.claude/rules/contracts.md` (source of truth)
2. Add to `.cursorrules` Layer summary
3. Create `docs/contracts/NEW_CONTRACT.md` with detailed spec
4. Add scanner rule to `tools/contract_scanner.py` (if automatable)
5. Update `tools/verify_contracts.py` to check new contract file exists
6. Add test coverage in `tests/contracts/`
7. Update this file (INVARIANTS.md)
8. Require architecture team review

**Agent Guidance**: Do not add contracts autonomously. Surface proposal to Founder.

---

## Known Unknowns

1. **C-003 Tenant Isolation**: No automated static analysis check for tenant scoping violations (manual code review only)
2. **C-016 File Structure**: No automated check for unauthorized new top-level directories
3. **Contract file completeness**: `docs/contracts/` directory was not fully audited — some contract files may be missing

---

## Agent Guidance

- **Before modifying engine/**: Verify you are not violating C-001, C-003, C-004, C-016
- **Before writing Cypher**: Always use `sanitize_label()` for labels (C-009)
- **Before adding behavior**: Gate with feature flag (C-021)
- **Before adding scoring weight**: Reduce existing weights to maintain sum ≤ 1.0 (C-022)
- **Before committing**: Run `make lint` (enforces C-009, C-018, and code style)

**If uncertain about a contract**: Reference `.claude/rules/contracts.md` or `docs/contracts/{CONTRACT_NAME}.md`.

---

## Related Documents

- **Source**: .claude/rules/contracts.md (C-001 to C-024 tabular reference)
- **Detailed specs**: docs/contracts/ (20 individual contract files)
- **Enforcement**: tools/contract_scanner.py, tools/verify_contracts.py
- **CI pipeline**: .github/workflows/ci.yml
- **Agent safety**: GUARDRAILS.md (overlaps with C-009, C-010, C-011, C-021, C-024)
