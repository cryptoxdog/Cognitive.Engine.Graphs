# Feature Gates — Activation Runbook

<!--
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [feature-gates, activation, runbook]
owner: engine-team
status: active
--- /L9_META ---
-->

This document describes every gated feature in the Graph Cognitive Engine,
its current activation state, prerequisites, activation steps, validation,
and rollback procedure.

> **Principle**: seL4-inspired mechanism/policy separation. The *mechanism*
> (code) ships dormant. The *policy* (operator decision) activates it via
> environment variables. Nothing activates by default.

---

## Quick Reference

| Feature | Flag | Default | State |
|---|---|---|---|
| KGE (CompoundE3D) | `KGE_ENABLED` | `False` | dormant |
| GDPR Erasure | `GDPR_ERASURE_ENABLED` | `False` | dormant |
| GDPR Dry-Run | `GDPR_DRY_RUN` | `True` | active when erasure enabled |
| GDS Scheduler | `GDS_ENABLED` | `True` | active |
| GDS Staleness Probe | `GDS_MAX_STALENESS_HOURS` | `25` | active |
| Score Normalization | `SCORE_NORMALIZE` | `False` | dormant |
| Outcome Feedback | `FEEDBACK_ENABLED` | `False` | dormant |
| Confidence Checking | `CONFIDENCE_CHECK_ENABLED` | `True` | active |
| Pareto Ensemble | `PARETO_ENABLED` | `True` | active |
| Pareto Weight Discovery | `PARETO_WEIGHT_DISCOVERY_ENABLED` | `False` | dormant |
| Domain Strict Validation | `DOMAIN_STRICT_VALIDATION` | `True` | active |
| Score Clamping | `SCORE_CLAMP_ENABLED` | `True` | active |
| Strict Null Gates | `STRICT_NULL_GATES` | `True` | active |
| Param Strict Mode | `PARAM_STRICT_MODE` | `True` | active |
| LLM Security (ValidatedLLMClient) | `LLM_PROVIDER` | — | stub |
| Constellation Orchestration | — | — | dormant |
| PostgreSQL Persistence | — | — | dormant |

---

## 1. KGE — CompoundE3D Embeddings

**State**: Dormant
**Flag**: `KGE_ENABLED=True`
**Settings**: `kge_embedding_dim` (default 256), `kge_confidence_threshold` (default 0.3)

### Prerequisites
- Domain spec must include a `kge:` section with valid `embeddingdim` and `trainingrelations`.
- Neo4j vector index must exist (matching dimension and cosine similarity).
- Embedding dimension in domain spec must match `kge_embedding_dim` setting.

### Activation Steps
1. Set `KGE_ENABLED=True` in environment.
2. Ensure domain spec has `kge:` section.
3. Call admin subaction `trigger_kge` with `domain_id` to activate.
4. Verify with `kge_status` subaction.

### Validation
- `kge_status` returns `enabled: true` with config details.
- `trigger_kge` smoke test confirms vector index is reachable.

### Rollback
- Set `KGE_ENABLED=False`. KGE scoring dimensions return 0.0.
- No data deletion needed — embeddings remain in Neo4j but are unused.

---

## 2. GDPR Erasure

**State**: Dormant
**Flag**: `GDPR_ERASURE_ENABLED=True`
**Settings**: `GDPR_DRY_RUN=True` (default — compute scope without executing)

### Prerequisites
- Domain spec must have `compliance.pii` section with field declarations.
- Caller must hold `admin:gdpr` capability (when capability auth is enabled).
- Recommend running dry-run first (`GDPR_DRY_RUN=True`).

### Activation Steps
1. Set `GDPR_ERASURE_ENABLED=True` in environment.
2. Keep `GDPR_DRY_RUN=True` initially for safe validation.
3. Call `erase_subject` admin subaction with `data_subject_id`.
4. Review dry-run report: nodes affected, edges affected.
5. Set `GDPR_DRY_RUN=False` and re-run for actual deletion.

### Validation
- Dry-run returns `{"dry_run": true, "would_affect": {...}}`.
- Real run returns `{"status": "erased", "summary": {...}}`.
- Audit trail contains `PII_ERASURE` entry at CRITICAL severity.

### Rollback
- Set `GDPR_ERASURE_ENABLED=False`. Endpoint returns disabled status.
- Erasure is irreversible — restore from backup if needed.

---

## 3. GDS Job Management

**State**: Active (scheduler runs automatically when `GDS_ENABLED=True`)
**Flag**: `GDS_ENABLED=True` (default)
**Settings**: `GDS_MAX_STALENESS_HOURS=25` (health probe threshold)

### Admin Subactions
- `gds_status` — returns per-algorithm run history, last status, next scheduled.
- `gds_trigger` — manually triggers a single algorithm run by name.
- `gds_health` — checks whether algorithms have run within staleness window.

### Prerequisites
- Domain spec must have `gdsjobs:` section with algorithm definitions.
- Neo4j must be reachable for GDS algorithm execution.

### Activation Steps
1. GDS is active by default. Use `gds_status` to inspect.
2. Use `gds_trigger` for initial population after deployment.
3. Adjust `GDS_MAX_STALENESS_HOURS` if algorithms run less frequently.

### Validation
- `gds_status` shows successful runs with timestamps.
- `gds_health` returns `healthy` when all algorithms are within staleness window.

---

## 4. Score Calibration (W2-01)

**State**: Active
**Admin Subaction**: `calibration_run`

Score calibration runs against the domain spec's `calibration.pairs` section.
No feature flag needed — available whenever calibration pairs are defined.

---

## 5. Outcome Feedback (W2-02)

**State**: Dormant
**Flag**: `FEEDBACK_ENABLED=True`

Enables the outcome feedback convergence loop. When active, outcome records
(positive/negative/neutral) influence scoring dimension weights over time.

---

## 6. Score Normalization (W2-04)

**State**: Dormant
**Flag**: `SCORE_NORMALIZE=True`

Post-query min-max normalization of match scores to [0, 1] range.

---

## 7. PostgreSQL Persistence

**State**: Dormant
**Prerequisites**: PostgreSQL instance provisioned (docker-compose or managed).

The audit logger and packet store have PostgreSQL write paths implemented
but require a connection pool (`db_pool`) to be injected at startup.
Currently logs warnings when `db_pool=None`.

---

## 8. LLM Security (ValidatedLLMClient)

**State**: Stub
**Error**: `FeatureNotEnabled("LLM SDK", flag="LLM_PROVIDER")`

Input sanitization and output schema validation are fully implemented.
The `_call()` integration point requires an LLM provider SDK to be wired.
See `DEFERRED.md: DEFERRED-002`.

---

## 9. Constellation Orchestration

**State**: Dormant

PacketEnvelope protocol, delegation chains, and hop traces are implemented
but require multi-node deployment to exercise. Single-node deployment uses
the chassis bridge directly.

---

## Querying Feature Status

Use the `feature_status` admin subaction to get current state of all gates:

```json
{
  "subaction": "feature_status"
}
```

Returns all feature flags with their current boolean/integer values.
