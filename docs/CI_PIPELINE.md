<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [ci]
tags: [ci, pipeline, pre-commit, enforcement]
owner: platform
status: active
/L9_META -->

# CI_PIPELINE.md — CI Pipeline & Pre-Commit Hooks

**Purpose**: Documents CI pipeline phases, pre-commit hooks, and blocking/advisory decision model.

**Source**: .github/workflows/ci.yml, .pre-commit-config.yaml

**Provenance**: Extracted from external audit documentation pack (2026-04-02). Verified against live repo 2026-04-26.

---

## CI Pipeline (7 Phases)

### Phase 1: Validation
- Check Python syntax (all .py files)
- Validate YAML files (.github/workflows/*.yml)

### Phase 2: Lint & Type Check
- Ruff linter (`ruff check`)
- Ruff formatter (`ruff format --check`)
- Mypy type checker (non-blocking warnings)

### Phase 3: Test Suite
- Pytest with coverage (`pytest --cov`)
- Minimum coverage: 60% (CI), 70% (pyproject.toml), 95% (engine/gates/, engine/scoring/)
- PostgreSQL service (postgres:16)
- Redis service (redis:7-alpine)

### Phase 4: Security Scanning
- Gitleaks (secret detection)
- pip-audit (dependency vulnerabilities, non-blocking)
- Safety (vulnerability scanner, non-blocking)
- Bandit (SAST, non-blocking)

### Phase 5: SBOM Generation
- Anchore SBOM action (spdx-json format)

### Phase 6: OpenSSF Scorecard
- Security posture scoring

### Phase 7: CI Gate (Fan-In)
- **Blocking**: validate, lint, test (must pass)
- **Advisory**: security, sbom, scorecard (failures logged, not blocking)

---

## Decision Model

```
Phase 1: Validation      → BLOCKING
Phase 2: Lint & Type     → BLOCKING
Phase 3: Test Suite      → BLOCKING
Phase 4: Security        → ADVISORY (non-blocking)
Phase 5: SBOM            → ADVISORY
Phase 6: Scorecard       → ADVISORY
Phase 7: CI Gate (Fan-In)→ BLOCKING (checks Phases 1-3)
```

**Merge-Blocking Gates**: validate, lint, test (3 jobs)
**Non-Blocking Jobs**: security, sbom, scorecard (3 jobs)

---

## Pre-Commit Hooks (15 hooks)

1. `trailing-whitespace` — remove trailing whitespace
2. `end-of-file-fixer` — ensure newline at EOF
3. `check-yaml` — validate YAML syntax
4. `check-added-large-files` — reject files >500KB
5. `check-merge-conflict` — detect merge conflict markers
6. `mixed-line-ending` — enforce LF line endings
7. `ruff` — Python linting
8. `ruff-format` — Python formatting
9. `mypy` — type checking (strict mode)
10. `block-fastapi-in-engine` — enforce C-001 (custom hook)
11. `check-cypher-interpolation` — enforce C-009 (custom hook)
12. `contract-scanner` — run tools/contract_scanner.py
13. `verify-contracts` — run tools/verify_contracts.py
14. `l9-meta-check` — verify L9_META headers (C-018)
15. `gitleaks` — secret scanning

**Current Exclusions**:
- `test_gates_all_types.py` — requires mock updates
- `test_scoring.py` — requires mock updates
- `test_config.py` — requires mock updates

These exclusions must be removed when mock updates are completed.

---

## Agent Decision Matrix for CI Failures

| CI Step Fails | Action |
|---------------|--------|
| validate (syntax/YAML) | STOP — fix syntax errors |
| lint (ruff check) | STOP — run `make lint-fix` |
| lint (ruff format) | STOP — run `ruff format .` |
| lint (mypy) | WARN — address type errors if blocking, ignore warnings |
| test (pytest) | STOP — fix failing tests or add coverage |
| security (gitleaks) | STOP — remove secret, add to vault |
| security (pip-audit) | WARN — triage vulnerability, create security issue |
| security (safety) | WARN — review warning, create issue if legitimate |
| security (bandit) | WARN — review warning, suppress if false positive |
| sbom | WARN — investigate Anchore failure, retry |
| scorecard | WARN — investigate scorecard failure, retry |

---

## Coverage Threshold Hierarchy

| Source | Threshold | Scope |
|--------|-----------|-------|
| ci.yml `COVERAGE_THRESHOLD` | 60% | CI default |
| pyproject.toml `fail_under` | 70% | Global minimum |
| TESTING.md layer-specific | 95% | engine/gates/, engine/scoring/ |

**Hierarchy**: Layer-specific (95%) > pyproject.toml global (70%) > CI default (60%)

---

## Related Documents

- **TESTING.md** — Test structure and coverage thresholds
- **GUARDRAILS.md** — Banned patterns registry
- **docs/TROUBLESHOOTING.md** — Common CI failure resolutions
- **.github/workflows/ci.yml** — Pipeline definition (source of truth)
- **.pre-commit-config.yaml** — Hook configuration (source of truth)
