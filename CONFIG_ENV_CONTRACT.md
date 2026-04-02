<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [config]
tags: [environment, configuration, settings]
owner: platform
status: active
/L9_META -->

# CONFIG_ENV_CONTRACT.md — Environment Variables Contract

**Purpose**: All environment variables with types, defaults, usage contracts, and feature flags.

**Source**: .env.template, engine/config/settings.py, .claude/rules/feature-flags.md

**Last Verified**: SHA 358d15d (2026-04-02)

---

## Configuration Loading Order

```
1. Environment variables (OS env)
   ↓
2. .env file (repo root, gitignored)
   ↓
3. .env.local file (repo root, gitignored, overrides .env)
   ↓
4. Pydantic Settings defaults (engine/config/settings.py)
```

**Pydantic Settings auto-maps**:
- `MY_VAR_NAME` env var → `Settings.my_var_name` field (case-insensitive, underscores match)

---

## Required Environment Variables (No Defaults)

| Variable | Type | Purpose | Failure Mode |
|----------|------|---------|--------------|
| NEO4J_URI | str | Neo4j connection URI | Startup fails, cannot connect to graph |
| NEO4J_USER | str | Neo4j username | Startup fails, authentication error |
| NEO4J_PASSWORD | str | Neo4j password | Startup fails, authentication error |

**Startup Behavior**: If any required var is missing → Settings initialization raises ValidationError → app fails to start

---

## Optional Environment Variables (Have Defaults)

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| L9_DEFAULT_TENANT | str | "default" | Fallback tenant for 5-level resolution |
| L9_LOG_LEVEL | str | "INFO" | Structlog log level (DEBUG, INFO, WARN, ERROR) |
| REDIS_URL | str | "redis://localhost:6379/0" | Redis connection string |
| MAX_RESULTS | int | 100 | Maximum match results returned per query |

---

## Feature Flags (Behavioral Gates)

**Source**: FEATURE_FLAGS.md, engine/config/settings.py

**Contract C-021**: Every behavioral change gated by bool flag in settings.py

### Core Engine Flags

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| GDS_ENABLED | bool | True | GDS scheduler toggle |
| KGE_ENABLED | bool | False | KGE embedding scoring dimension |
| PARETO_ENABLED | bool | True | Multi-objective Pareto-optimal scoring |
| PARETO_WEIGHT_DISCOVERY_ENABLED | bool | False | Learned weight trade-offs |

### Invariant Hardening Flags

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| DOMAIN_STRICT_VALIDATION | bool | True | Cross-reference validation at domain load |
| SCORE_CLAMP_ENABLED | bool | True | Clamp dimension scores to [0, 1] |
| STRICT_NULL_GATES | bool | True | Reject gates with null-resolved parameters |
| MAX_HOP_HARD_CAP | int | 10 | Maximum traversal hops |
| PARAM_STRICT_MODE | bool | True | Raise on parameter resolution failures |

### Scoring Refinement Flags

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| FEEDBACK_ENABLED | bool | False | Outcome feedback loop |
| CONFIDENCE_CHECK_ENABLED | bool | True | Ensemble confidence bounds |
| MONOCULTURE_THRESHOLD | float | 0.70 | Single-dimension dominance cap |
| ENSEMBLE_MAX_DIVERGENCE | float | 0.30 | GDS/KGE score divergence cap |
| SCORE_NORMALIZE | bool | False | Post-query min-max normalization |

### Scoring Weights (Contract C-022: Sum ≤ 1.0)

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| W_STRUCTURAL | float | 0.30 | Graph structure scoring weight |
| W_GEO | float | 0.25 | Geospatial proximity weight |
| W_REINFORCEMENT | float | 0.20 | Feedback loop reinforcement weight |
| W_FRESHNESS | float | 0.10 | Temporal recency weight |

**Sum**: 0.85 (must be ≤ 1.0, enforced by `engine/boot.py::_assert_default_weight_sum()`)

**Adding New Weight**: Reduce existing weights proportionally to maintain sum ≤ 1.0

---

## CI Environment Variables

**Source**: .github/workflows/ci.yml

| Variable | Value | Purpose |
|----------|-------|---------|
| PYTHON_VERSION | 3.12 | Python version for CI |
| REQUIREMENTS_FILE | requirements.txt | Pip requirements file |
| COVERAGE_THRESHOLD | 60 | Minimum coverage % (overridden by pyproject.toml 70%) |
| TEST_DIR | tests/ | Test directory path |
| SOURCE_DIR | . | Source code directory |
| DATABASE_URL | postgresql://test_user:test_password@localhost:5432/test_db | PostgreSQL connection (test service) |
| REDIS_URL | redis://localhost:6379/0 | Redis connection (test service) |

**Note**: DATABASE_URL provisions PostgreSQL service in CI, but CEG does not use PostgreSQL in runtime.  
**Likely**: CI template artifact from l9-template, not removed yet.

---

## Secret Management

**Current**: Secrets in .env files (gitignored)

**Future (Aspirational)**: AWS Secrets Manager integration

**Contract C-011 (PII Handling)**: Encryption key source declared in domain spec:
```yaml
compliance:
  pii:
    encryption_key_source: env | vault | kms
```

**Forbidden**: Hardcoded secrets, API keys, passwords in source code (violates GUARDRAILS.md §8)

---

## L9_ Prefix Convention (Contract ENV-001)

**Rule**: All infrastructure environment variables MUST use `L9_` prefix

**Examples**:
- ✅ `L9_DEFAULT_TENANT`
- ✅ `L9_LOG_LEVEL`
- ❌ `DEFAULT_TENANT` (banned by contract scanner ENV-001)

**Exemptions**: Third-party service variables (NEO4J_, REDIS_, AWS_) do not require L9_ prefix

**Current L9_ vars**:
1. L9_DEFAULT_TENANT
2. L9_LOG_LEVEL
3. (Others not documented — see settings.py for complete list)

---

## Local Development Quick Start

**Minimum .env for `make dev`**:

```bash
# Copy template
cp .env.template .env

# Populate required values
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Optional overrides
L9_LOG_LEVEL=DEBUG
FEEDBACK_ENABLED=false
```

**Docker Compose handles**: NEO4J_, REDIS_ vars automatically in containerized mode

---

## Known Unknowns

1. Complete list of L9_ prefixed vars (only L9_DEFAULT_TENANT and L9_LOG_LEVEL documented)
2. AWS Secrets Manager integration status (aspirational or implemented?)
3. PostgreSQL usage in runtime (CI provisions it, but no Python pg driver in deps)

**Agent Action**: If working with env vars not listed here, consult `engine/config/settings.py` Settings class for full inventory.

---

## Related Documents

- **Source**: .env.template (required/optional vars)
- **Source**: engine/config/settings.py (Settings class, defaults)
- **Feature Flags**: FEATURE_FLAGS.md (complete flag inventory)
- **Secrets**: GUARDRAILS.md §8 (secret hygiene rules)
- **Contracts**: INVARIANTS.md C-021 (feature flag discipline), C-022 (weight ceiling)
