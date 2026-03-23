# seL4-Inspired Upgrade Suite — Technical Documentation

**Repository**: `cryptoxdog/Cognitive.Engine.Graphs`  
**Baseline Commit**: `e7bc2b1`  
**Research Source**: Klein et al., *"seL4: Formal Verification of an OS Kernel"* (SOSP 2009)  
**Upgrade Date**: March 2026  

---

## Table of Contents

1. [Research Paper & Methodology](#research-paper--methodology)
2. [seL4 Principles Mapped to CEG](#sel4-principles-mapped-to-ceg)
3. [Concept Extraction Summary](#concept-extraction-summary)
4. [Wave-by-Wave Enhancement Reference](#wave-by-wave-enhancement-reference)
5. [File & Module Index](#file--module-index)
6. [Feature Flags Reference](#feature-flags-reference)
7. [Test Coverage Summary](#test-coverage-summary)
8. [Dependency Graph](#dependency-graph)

---

## Research Paper & Methodology

### Source Paper

**Title**: *seL4: Formal Verification of an OS Kernel*  
**Authors**: Gerwin Klein, Kevin Elphinstone, Gernot Heiser, June Andronick, David Cock, Philip Derrin, Dhammika Elkaduwe, Kai Engelhardt, Rafal Kolanski, Michael Norrish, Thomas Sewell, Harvey Tuch, Simon Winwood  
**Published**: 22nd ACM Symposium on Operating Systems Principles (SOSP), 2009  
**DOI**: [10.1145/1629575.1629596](https://doi.org/10.1145/1629575.1629596)

The seL4 paper documents the first formal proof of functional correctness for a production-quality operating system microkernel (8,700 lines C, 600 lines assembler). Using the Isabelle/HOL theorem prover, the team established a three-layer refinement chain — Abstract Specification → Executable Specification → C Implementation — proving that every possible execution of the C code conforms to the abstract specification. The verification effort discovered 400+ bugs through proof attempts alone.

### Integration Methodology

A 12-deliverable research-ingestion pipeline was executed against the CEG repository:

| Phase | Deliverable | Purpose |
|-------|------------|---------|
| 1 | Repo Orientation Summary | Baseline audit of 63 Python files, 11,307 lines, 4 subsystems |
| 2 | Paper Concept Extraction | Systematic extraction of 39 transferable concepts from seL4 |
| 3 | Executable Reality Filter | Classification of each concept against actual repo state |
| 4 | Enhancement Opportunity Map | 24 enhancements across 5 impact tiers |
| 5 | Phased Integration Plan | 6 waves, 26 items with full dependency ordering |
| 6 | Architectural Change Review | Safety analysis of all proposed structural changes |
| 7 | Safe Additive Enhancement Specs | Implementation specs for non-architectural items |
| 8–10 | Implementation Patches, Tests, Tools | Reference implementations and verification tooling |
| 11 | Implementation Briefs | Concise build-ready specs per enhancement |
| 12 | Final Prioritized Roadmap | 33-item roadmap with risk register |

**Governing rule**: The seL4 paper is the idea source. The repository and its executable reality are the source of truth. No architectural changes were made without explicit review and approval.

---

## seL4 Principles Mapped to CEG

Ten core seL4 design principles were identified as transferable to CEG's graph-matching architecture:

| # | seL4 Principle | CEG Application | Waves |
|---|---------------|-----------------|-------|
| 1 | **Invariant Preservation** — 80+ globally-proven invariants hold at every machine instruction | Domain-spec cross-reference validators, score-range clamping, gate compilation null-checks, traversal bounds | W1, W5 |
| 2 | **No Unchecked User Arguments** — all user inputs validated before kernel state is touched | Parameter resolver strict mode, weight validation, gate field/type checks | W1 |
| 3 | **Three-Layer Refinement** — Abstract → Executable → Implementation with formal proofs between layers | Score calibration framework (abstract spec), compiled domain packs (executable layer), Cypher generation (implementation) | W2 |
| 4 | **Forward Simulation** — every concrete transition corresponds to an abstract transition | Calibration verification: actual scores checked against expected ranges defined in calibration spec | W2 |
| 5 | **Capability-Based Access Control** — no resource access without holding a valid capability | Tenant authorization enforcement, domain-spec capability model, action-level permissions, delegation audit trail | W3 |
| 6 | **Capability Revocation** — revoking a capability removes all transitively derived capabilities | Delegation tree stored in Neo4j, revoke_capability admin subaction, audit trail for all delegation events | W3 |
| 7 | **Explicit Memory Management** — memory lifecycle is explicit, bounded, not unbounded growth | DomainPackLoader TTL cache (bounded at 100 entries, 30s TTL), GDPR erasure endpoint | W4, W6 |
| 8 | **Concurrency Minimization** — single-stack, event-based, no global mutable state across threads | EngineState dataclass replaces module-global mutables, asyncio.Lock for init paths, circuit breaker for Neo4j | W4 |
| 9 | **Explicit Lifecycle** — every component initialized at startup, not lazily with race conditions | GDS scheduler lifecycle wiring, EngineState boot/shutdown, ComplianceEngine singleton pool | W4, W6 |
| 10 | **Cost-of-Change Visibility** — verification makes the cost of cross-cutting changes visible | Contract verification tests, invariant regression tests, score quality benchmarks, property-based testing | W5 |

---

## Concept Extraction Summary

39 concepts were extracted from the seL4 paper across six dimensions:

| Dimension | Concepts | Key Extractions |
|-----------|----------|-----------------|
| **Architectural Patterns** (A-1 to A-8) | 8 | Three-layer refinement, microkernel minimality, event-based execution, hardware abstraction |
| **Verification & Proof** (V-1 to V-7) | 7 | Refinement proof, Haskell prototype as oracle, forward simulation, state relation R |
| **Invariant Design** (I-1 to I-5) | 5 | Global invariants, input validation before state change, typed object invariants |
| **State Management** (ST-1 to ST-6) | 6 | Single state container, explicit lifecycle, no mutable globals, deterministic transitions |
| **Capability & Access** (C-1 to C-5) | 5 | Capability derivation trees, typed capabilities, revocation proofs, delegation chains |
| **Operational Lessons** (O-1 to O-8) | 8 | Bug taxonomy, cost-of-change metrics, verification-driven testing, incremental proof |

Of these 39 concepts, the reality filter classified:
- **12** as DIRECTLY EXECUTABLE (modify existing files only)
- **10** as ADAPTABLE (new files, no breaking changes)
- **4** as ARCHITECTURAL (structural changes, reviewed and approved)
- **8** as ADJACENT (CI, docs, tooling)
- **5** as NOT APPLICABLE (hardware-specific or already present)

---

## Wave-by-Wave Enhancement Reference

### Wave 1: Invariant & Validation Hardening
**PR**: [#57](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/57) — `+1,010 lines, 32 tests`  
**seL4 Concepts**: Invariant preservation, no unchecked user arguments, termination proofs

| ID | Enhancement | Technical Mechanism |
|----|------------|---------------------|
| W1-01 | Domain-Spec Cross-Reference Validators | `@model_validator(mode='after')` on `DomainSpec` in `engine/config/schema.py`. Validates at load time: edge source/target reference declared node types, gate predicate fields match declared node spec fields, domain weight overrides sum ≤ 1.0, no undeclared parameter references. Raises `DomainSpecError` with exact YAML path on first violation. |
| W1-02 | Score-Range Invariants | Cypher `CASE WHEN … > 1.0 THEN 1.0 WHEN … < 0.0 THEN 0.0 ELSE … END` wrapping each dimension expression in `ScoringAssembler._build_score_expression()`. User-supplied weight validation in `handle_match()` (sum ≤ 1.0, each in [0,1]). Startup assertion in `engine/boot.py` that `W_STRUCTURAL + W_GEO + W_REINFORCEMENT + W_FRESHNESS ≤ 1.0 ± 1e-6`. |
| W1-03 | Gate Compilation Null-Semantic Checks | `GateCompiler.validate_gates()` pre-pass: checks every required gate field has a resolved parameter, detects operator/type mismatches (e.g., `CONTAINS` on integer), post-compilation null-parameter rejection when `STRICT_NULL_GATES=True`. |
| W1-04 | Traversal Pattern Validators | `TraversalAssembler.validate_traversal()`: assert `1 ≤ max_hops ≤ MAX_HOP_HARD_CAP(10)`, direction ∈ `{OUTGOING, INCOMING, BOTH}`, all node labels/relationship types declared in domain spec. Hard `LIMIT MAX_RESULTS` enforced in Cypher regardless of caller input. |
| W1-05 | Parameter Resolver Strict Mode | Replaces bare `except Exception: logger.error(...)` in `ParameterResolver._resolve_derived()` with `raise ValidationError`. Failed derived parameters now propagate as 422 instead of silently evaluating to null. Controlled by `PARAM_STRICT_MODE=True`. |

**How it works**: Wave 1 establishes the invariant foundation. seL4 proves 80+ invariants hold at every machine instruction — CEG had none. These five validators ensure that invalid YAML specs, unbounded scores, null gate parameters, runaway traversals, and swallowed errors are caught before they can corrupt query results. Every validator is gated by a feature flag defaulting to `True`, enabling gradual rollout.

---

### Wave 2: Refinement-Inspired Scoring
**PR**: [#58](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/58) — `+1,734 lines, 71 tests`  
**seL4 Concepts**: Three-layer refinement, forward simulation, state relation R

| ID | Enhancement | Technical Mechanism |
|----|------------|---------------------|
| W2-01 | Score Calibration Framework | `engine/scoring/calibration.py`: `ScoreCalibration` class loads labeled pairs `{node_a, node_b, expected_score_range: [low, high]}` from domain YAML `calibration` section. `calibration_run` admin subaction executes real match queries, compares actual vs. expected ranges, emits structured report. Manual verification tool — not automated weight adjustment. |
| W2-02 | Weight Auto-Tuning Feedback Loop | `engine/scoring/feedback.py`: Accepts `outcome` records (`{match_id, candidate_id, outcome: positive|negative|neutral}`). `score_feedback` admin subaction computes simple gradient (±0.02 nudge per dimension). Proposed weights displayed — never auto-applied. Human-in-the-loop `apply_weight_proposal` gate. `FEEDBACK_ENABLED=False` by default. |
| W2-03 | Ensemble Confidence Bounds | `engine/scoring/confidence.py`: `ConfidenceChecker` detects monoculture (any single dimension > 70% of total score) and flags divergent candidates with `"confidence_flag": "divergent"` in response. Prepares for future KGE ensemble disagreement detection when `KGE_ENABLED=True`. |
| W2-04 | Score Normalization Layer | Optional post-query min-max normalization over result window (top=1.0, bottom=0.0). `scoring_meta` object added to match response: `{raw_max, raw_min, weights_used, normalization_applied}`. `SCORE_NORMALIZE=False` by default. |

**How it works**: seL4's three-layer refinement proves the implementation matches the abstract spec. Wave 2 introduces an analogous structure for CEG's scoring: the calibration spec defines WHAT scores should be (abstract), the scoring assembler computes HOW (executable), and the Cypher output is the implementation. The calibration framework verifies the concrete scores match the abstract target. The feedback loop enables controlled weight convergence constrained by calibration bounds.

---

### Wave 3: Capability & Access Control
**PR**: [#59](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/59) — `54 tests, 851 total passing`  
**seL4 Concepts**: Capability-based access control, capability derivation trees, revocation proofs

| ID | Enhancement | Technical Mechanism |
|----|------------|---------------------|
| W3-01 | Tenant Authorization Enforcement | `BearerAuthMiddleware` extended: extracts `allowed_tenants: list[str]` from JWT payload, compares against `ExecuteRequest.tenant`. Returns 403 if tenant not in allowed list. `TENANT_AUTH_ENABLED=True` (prod), with `TENANT_AUTH_BYPASS_KEY` for internal service-to-service calls. |
| W3-02 | Domain-Spec Capability Model | `engine/auth/capabilities.py`: `CapabilitySet` compiled from domain spec YAML `capabilities` section. Named tokens (`match:read`, `sync:write`, `admin:kge`). Derivation tree stored as Neo4j sub-graph: `(Tenant)-[:HOLDS]->(Capability)-[:DERIVED_FROM]->(Capability)`. |
| W3-03 | Action-Level Permissions | `ACTION_PERMISSION_MAP`: `match→match:read`, `sync→sync:write`, `admin→admin:write`, `kge→admin:kge`. Enforcement at each handler entry point (~3 lines per handler). |
| W3-04 | Delegation Audit Trail | `delegate_capability` and `revoke_capability` admin subactions. Delegation edges: `(Tenant)-[:DELEGATED {ts, expiry, delegator}]->(Capability)`. All events routed through `AuditLogger`. |

**How it works**: seL4 proves no thread can access a resource without holding a capability — CEG previously allowed any authenticated caller to access any tenant's data. Wave 3 closes this gap with a full capability model: JWT-based tenant isolation, YAML-defined capabilities compiled at load time, action-level permission mapping, and a delegation/revocation audit trail mirroring seL4's capability derivation trees.

---

### Wave 4: State Management & Resilience
**PR**: [#60](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/60) — `+1,573 lines, 37 tests`  
**seL4 Concepts**: State relation preservation, concurrency minimization, explicit lifecycle

| ID | Enhancement | Technical Mechanism |
|----|------------|---------------------|
| W4-01 | EngineState Class | `engine/state.py`: `EngineState` dataclass containing `graph_driver`, `domain_loader`, `gds_schedulers`, `compliance_engines`, `initialized`, `init_lock: asyncio.Lock`. Replaces all module-global accesses. `EngineState.reset()` for test teardown. Wired through `GraphLifecycle`. |
| W4-02 | GraphDriver Circuit Breaker | `engine/graph/driver.py`: `failure_count`, `circuit_open_until` state. After `NEO4J_CIRCUIT_THRESHOLD=3` consecutive failures, circuit opens for `NEO4J_CIRCUIT_COOLDOWN=30s`. Immediate `CircuitOpenError` (503) during open state. Auto-reset on success. Health probe reports circuit state. |
| W4-03 | DomainPackLoader Async + TTL Cache | `cachetools.TTLCache(maxsize=100, ttl=30)` replaces unbounded dict. `load_domain_async()` wraps disk I/O in `asyncio.to_thread()`. Per-domain-id `asyncio.Lock` prevents cache-miss stampede. `DOMAIN_CACHE_TTL_SECONDS=30`. |
| W4-04 | ComplianceEngine Singleton + Periodic Flush | Per-domain-id singleton pool in `EngineState.compliance_engines`. Periodic flush task: every 60s or when buffer exceeds `MAX_BUFFER_SIZE=100` entries. `asyncio.Lock` replaces `threading.Lock` in `AuditLogger._emit()`. |

**How it works**: seL4's proof depends on the invariant that global state is always in a consistent abstract state. CEG had module-level mutable globals (`_graph_driver`, `_domain_loader`, `_gds_schedulers`) with no cleanup paths and lazy-init race conditions. Wave 4 encapsulates all mutable state into a single typed `EngineState` container, adds a circuit breaker to prevent cascading failure during Neo4j outages, bounds the domain cache, and makes audit persistence reliable through singleton compliance engines with periodic flushing.

---

### Wave 5: Correctness Tooling & Verification
**PR**: [#64](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/64) — `+2,372 lines, 92 tests`  
**seL4 Concepts**: Formal proof as verification, testing as proof-companion, cost-of-change visibility

| ID | Enhancement | Technical Mechanism |
|----|------------|---------------------|
| W5-01 | Contract Verification Test Suite | `tests/contracts/test_contracts.py`: One test per CEG contract (20 contracts from `.cursorrules`). Tests exercise contract boundaries — e.g., Contract 1 asserts no FastAPI import in engine namespace, Contract 9 asserts startup weight-sum assertion fires on violation. |
| W5-02 | Invariant Regression Tests | `tests/invariants/`: 31 regression tests, one per audit defect. Each reproduces the exact defect trigger condition, asserts the fix holds. Tagged with `@pytest.mark.finding("T1-03")`. CI gate: all invariant tests must pass on every PR. |
| W5-03 | Score Quality Benchmark Suite | `tests/scoring/benchmark.py`: Runs labeled test graphs through full match pipeline. Records: good-pair average, bad-pair average, separation (good_avg − bad_avg), distribution moments (mean, std, skew). CI fails if separation < 0.20 or std < 0.05. |
| W5-04 | Domain-Spec Validation Tool | `tools/validate_domain.py`: Standalone CLI: `python -m ceg.tools.validate_domain path/to/spec.yaml [--strict]`. Runs all W1-01 through W1-04 validators, outputs structured pass/fail report with YAML path references. Pre-commit hook integration. |
| W5-05 | Property-Based Testing | Hypothesis-based tests for `GateCompiler` (any valid `GateSpec` → valid Cypher) and `ScoringAssembler` (any weight vector with sum ≤ 1.0 → scores in [0,1]). Custom `@given` strategies for `GateSpec` and weight vectors. |

**How it works**: seL4 found its bugs not through testing but through proof attempts — 400+ bugs discovered during verification. CEG's 31 defects were found through static analysis. Wave 5 adds the executable equivalent of proof obligations: contract tests verify each of the 20 architectural contracts, invariant tests prevent regression of all 31 fixed defects, the benchmark suite catches scoring quality degradation, the validation CLI catches spec errors before deployment, and property-based tests check invariants hold for all inputs — not just developer-chosen test cases.

---

### Wave 6: Dormant Feature Activation
**PR**: [#63](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pull/63) — `+1,236 lines, 30 tests`  
**seL4 Concepts**: Mechanism/policy separation, explicit memory management, operator-controlled activation

| ID | Enhancement | Technical Mechanism |
|----|------------|---------------------|
| W6-01 | KGE Activation Pathway | `trigger_kge`, `kge_status`, `deactivate_kge` admin subactions. Validates `KGE_ENABLED=True`, domain spec `kge` section, embedding dimension consistency. Smoke-tests on activation. Adds KGE as fifth scoring dimension in ensemble. Activates ~1,500 lines of dormant CompoundE3D + BeamSearch code. |
| W6-02 | GDPR Erasure Endpoint | `erase_subject` admin subaction. Requires `admin:gdpr` capability. Computes PII field paths, sets to null, writes tombstone node, flushes audit immediately. Idempotent (`already_erased` status). `dry_run=True` default. GDPR Article 17 compliance. |
| W6-03 | GDS Job History Exposure | `gds_status` admin subaction: last run time per algorithm, success/error status, next scheduled run, last 10 history entries. `gds_trigger` for manual execution. `gds_health` probe with `GDS_MAX_STALENESS_HOURS=25` threshold. |
| W6-04 | Feature Gates Documentation | `docs/FEATURE_GATES.md`: Structured activation runbook for each gated feature (KGE, GDPR, delegation, PostgreSQL, LLM security, constellation). `feature_status` admin subaction returns all gate states. Replaces `NotImplementedError` with `FeatureNotEnabled` in `ValidatedLLMClient._call()`. |

**How it works**: seL4 separates mechanism from policy — the kernel proves the mechanism is correct, and the operator decides when to activate it. CEG had ~2,000 lines of well-designed but dormant code (KGE embeddings, GDPR erasure, GDS monitoring). Wave 6 provides safe activation pathways backed by Wave 5's test infrastructure: each dormant feature gets an admin subaction with validation gates, smoke tests, rollback procedures, and explicit feature flag documentation.

---

## File & Module Index

### New Files Created Across All Waves

| File | Wave | Purpose |
|------|------|---------|
| `engine/config/validators.py` | W1 | Domain-spec cross-reference invariant validators |
| `engine/scoring/calibration.py` | W2 | Score calibration framework |
| `engine/scoring/feedback.py` | W2 | Weight auto-tuning feedback loop |
| `engine/scoring/confidence.py` | W2 | Ensemble confidence bounds checker |
| `engine/auth/capabilities.py` | W3 | Capability model, derivation trees, delegation |
| `engine/state.py` | W4 | EngineState dataclass — centralized mutable state |
| `engine/errors.py` | W6 | FeatureNotEnabled error class |
| `tests/contracts/test_contracts.py` | W5 | 20 contract verification tests |
| `tests/invariants/` | W5 | 31 invariant regression tests |
| `tests/scoring/benchmark.py` | W5 | Score quality benchmark suite |
| `tests/property/test_gates.py` | W5 | Property-based gate tests (Hypothesis) |
| `tests/property/test_scoring.py` | W5 | Property-based scoring tests (Hypothesis) |
| `tools/validate_domain.py` | W5 | Standalone domain-spec validation CLI |
| `docs/FEATURE_GATES.md` | W6 | Feature activation runbooks |

### Existing Files Modified

| File | Waves | Changes |
|------|-------|---------|
| `engine/config/schema.py` | W1, W2, W3, W6 | Pydantic validators, CalibrationSpec, CapabilitySpec, GdprSpec |
| `engine/config/settings.py` | W1–W6 | 20+ feature flags added |
| `engine/config/loader.py` | W1, W3, W4 | Cross-ref validation, capability compilation, TTL cache |
| `engine/handlers.py` | W1–W6 | Weight validation, capability checks, admin subactions, state access |
| `engine/boot.py` | W1, W4, W6 | Startup assertions, EngineState wiring, health probes |
| `engine/scoring/assembler.py` | W1, W2 | Score clamping, per-dimension pass-through |
| `engine/traversal/compiler.py` | W1 | Gate pre-validation, null-parameter checks |
| `engine/traversal/assembler.py` | W1 | Traversal validation, hard LIMIT enforcement |
| `engine/traversal/resolver.py` | W1 | Strict mode (ValidationError instead of log-and-swallow) |
| `engine/graph/driver.py` | W4 | Circuit breaker logic |
| `engine/compliance/engine.py` | W4 | Singleton pool, asyncio.Lock, periodic flush |
| `engine/kge/compound_e3d.py` | W6 | Domain-spec embedding dim, activation pathway |
| `engine/compliance/pii.py` | W6 | Idempotent erasure, tombstone nodes |
| `engine/gds/scheduler.py` | W6 | Job history exposure, manual trigger |
| `chassis/auth/bearer.py` | W3 | Tenant authorization extraction and check |

---

## Feature Flags Reference

All flags are added to `engine/config/settings.py` and controllable via environment variables.

| Flag | Default | Wave | Purpose |
|------|---------|------|---------|
| `DOMAIN_STRICT_VALIDATION` | `True` | W1 | Enable domain-spec cross-reference validation at load time |
| `SCORE_CLAMP_ENABLED` | `True` | W1 | Clamp per-dimension scoring expressions to [0, 1] |
| `STRICT_NULL_GATES` | `True` | W1 | Reject gate clauses referencing null parameters |
| `MAX_HOP_HARD_CAP` | `10` | W1 | Maximum allowed traversal hops |
| `PARAM_STRICT_MODE` | `True` | W1 | Raise ValidationError on derived-parameter failure |
| `SCORE_NORMALIZE` | `False` | W2 | Enable post-query min-max normalization |
| `FEEDBACK_ENABLED` | `False` | W2 | Enable outcome feedback recording |
| `ENSEMBLE_MAX_DIVERGENCE` | `0.30` | W2 | Maximum allowed ensemble score disagreement |
| `MONOCULTURE_THRESHOLD` | `0.70` | W2 | Flag candidates where one dimension > 70% of score |
| `TENANT_AUTH_ENABLED` | `True` | W3 | Enforce JWT-based tenant authorization |
| `TENANT_AUTH_BYPASS_KEY` | `""` | W3 | Service-to-service bypass for multi-tenant access |
| `CAPABILITY_ENFORCE` | `False` | W3 | Enforce domain-spec capability model |
| `NEO4J_CIRCUIT_THRESHOLD` | `3` | W4 | Consecutive failures before circuit opens |
| `NEO4J_CIRCUIT_COOLDOWN` | `30` | W4 | Seconds circuit stays open after tripping |
| `DOMAIN_CACHE_TTL_SECONDS` | `30` | W4 | TTL for domain pack cache entries |
| `DOMAIN_CACHE_MAXSIZE` | `100` | W4 | Maximum domain packs in cache |
| `MAX_BUFFER_SIZE` | `100` | W4 | Audit buffer entries before forced flush |
| `KGE_ENABLED` | `False` | W6 | Enable KGE embedding scoring dimension |
| `GDS_MAX_STALENESS_HOURS` | `25` | W6 | Max hours before GDS health probe fails |
| `ERASURE_DRY_RUN` | `True` | W6 | GDPR erasure dry-run mode |

---

## Test Coverage Summary

| Wave | Tests Added | Test Type | Key Assertions |
|------|------------|-----------|----------------|
| W1 | 32 | Unit/Integration | Validator catches invalid YAML, scores clamped to [0,1], null gates rejected, traversals bounded |
| W2 | 71 | Unit/Integration | Calibration detects out-of-range scores, feedback gradient ±0.02, normalization preserves ranking, monoculture flagged |
| W3 | 54 | Unit/Integration | Unauthorized tenant → 403, missing capability → 403, delegation creates Neo4j edge, revocation removes edge |
| W4 | 37 | Unit/Integration | EngineState singleton, circuit opens after 3 failures, TTL cache evicts after 30s, flush triggers at buffer limit |
| W5 | 92 | Contract/Invariant/Property/Benchmark | 20 contracts verified, 31 regressions covered, score separation > 0.20, property tests for all weight vectors |
| W6 | 30 | Unit/Integration | KGE activation smoke-test, erasure idempotency, GDS history returns entries, feature_status reports all gates |
| **Total** | **316** | | |

---

## Dependency Graph

```
Wave 1 (Invariants & Validation) ─────────────────────────────────────────────────
  W1-01 Domain-spec validators ────────► W1-03 (gate checks depend on field types)
  W1-02 Score clamping ─────────────────► W2-01 (calibration needs bounded scores)
  W1-04 Traversal validators
  W1-05 Param resolver strict mode

Wave 2 (Refinement-Inspired Scoring) ─────────────────────────────────────────────
  W2-01 Calibration framework ◄── W1-02
  W2-02 Feedback loop ◄── W2-01
  W2-03 Confidence bounds ◄── W1-02
  W2-04 Score normalization ◄── W1-02

Wave 3 (Capability & Access Control) ──────────────────────────────────────────────
  W3-01 Tenant authorization
  W3-02 Capability model ◄── W3-01
  W3-03 Action-level permissions ◄── W3-02
  W3-04 Delegation audit ◄── W3-02, W4-04

Wave 4 (State Management) ─ parallel to Wave 1 ───────────────────────────────────
  W4-01 EngineState class
  W4-02 Circuit breaker ◄── W4-01
  W4-03 TTL cache ◄── W4-01
  W4-04 Compliance singleton ◄── W4-01, W4-03

Wave 5 (Correctness Tooling) ◄── Waves 1–4 ───────────────────────────────────────
  W5-01 Contract tests ◄── W1–W4 (invariants must exist to test)
  W5-02 Invariant regressions ◄── W1–W4 fixes
  W5-03 Score benchmark ◄── W1-02, W2-01
  W5-04 Validation CLI ◄── W1-01, W1-03, W1-04
  W5-05 Property tests ◄── W1-02, W1-03

Wave 6 (Dormant Activation) ◄── Wave 5 ───────────────────────────────────────────
  W6-01 KGE pathway ◄── W1-01, W5-01, W4-01
  W6-02 GDPR erasure ◄── W3-03, W4-04
  W6-03 GDS job history ◄── W4-01
  W6-04 Feature gates docs ◄── All prior waves
```

---

## Cumulative Statistics

| Metric | Value |
|--------|-------|
| Pull Requests | 6 |
| Total Lines Added | ~8,900+ |
| Total Tests Added | 316 |
| New Files Created | 14+ |
| Existing Files Modified | 15+ |
| Feature Flags Added | 20+ |
| Audit Defects Addressed | 31 |
| seL4 Concepts Applied | 10 of 10 |
| Enhancements Delivered | 26 across 6 waves |
