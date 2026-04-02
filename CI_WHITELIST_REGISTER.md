<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [ci]
tags: [ci, waivers, non-blocking]
owner: platform
status: active
/L9_META -->

# CI_WHITELIST_REGISTER.md — CI Waivers & Non-Blocking Checks

**Purpose**: Registry of CI waivers, allowed failures, and non-blocking checks.

**Source**: .github/workflows/ci.yml, .pre-commit-config.yaml, .gitleaksignore

**Last Verified**: SHA 358d15d (2026-04-02)

---

## CI Pipeline Decision Model

```
Phase 1: Validation → BLOCKING
Phase 2: Lint & Type Check → BLOCKING
Phase 3: Test Suite → BLOCKING
Phase 4: Security Scanning → ADVISORY (non-blocking)
Phase 5: SBOM Generation → ADVISORY
Phase 6: OpenSSF Scorecard → ADVISORY
Phase 7: CI Gate (Fan-In) → BLOCKING (checks Phases 1-3)
```

**Merge-Blocking Gates**: validate, lint, test (3 jobs)  
**Non-Blocking Jobs**: security, sbom, scorecard (3 jobs)

---

## Non-Blocking CI Checks

### WAIVER-001: MyPy Type Checking (Phase 2)
**Status**: Non-blocking warnings  
**Pattern**: `|| echo "⚠️ Type check warnings (non-blocking)"`  
**File**: .github/workflows/ci.yml line 95  
**Reason**: Strict typing is aspirational, not required for merge  
**Impact**: Type errors logged but do not fail CI  
**Review Cadence**: Quarterly type coverage improvement sprints

### WAIVER-002: pip-audit (Phase 4)
**Status**: Non-blocking  
**Pattern**: `|| echo "⚠️ Vulnerabilities found (non-blocking)"`  
**File**: .github/workflows/ci.yml line 169  
**Reason**: CVE response time varies, should not block dev velocity  
**Impact**: Vulnerabilities logged, addressed via security backlog  
**Review Cadence**: Weekly security triage

### WAIVER-003: Safety Check (Phase 4)
**Status**: Non-blocking  
**Pattern**: `|| echo "⚠️ Safety check warnings (non-blocking)"`  
**File**: .github/workflows/ci.yml line 174  
**Reason**: Safety DB has false positives, manual review required  
**Impact**: Warnings logged, triaged separately  
**Review Cadence**: Weekly security triage

### WAIVER-004: Bandit SAST (Phase 4)
**Status**: Non-blocking  
**Pattern**: `|| echo "⚠️ Security warnings found (non-blocking)"`  
**File**: .github/workflows/ci.yml line 183  
**Reason**: Bandit flags patterns that may be safe in context  
**Impact**: Security warnings logged, reviewed in PR  
**Review Cadence**: Per-PR manual review

### WAIVER-005: SBOM Generation Failure (Phase 5)
**Status**: Non-blocking  
**ADR**: None (tool-level failure, not waiver)  
**Reason**: Anchore SBOM action may fail on transient errors  
**Impact**: SBOM missing for that run, regenerates on next commit  
**Review Cadence**: Monthly SBOM coverage check

### WAIVER-006: OpenSSF Scorecard Failure (Phase 6)
**Status**: Non-blocking  
**ADR**: None (external service, not waiver)  
**Reason**: Scorecard service may not exist yet in 2026  
**Impact**: Security posture scoring missing  
**Review Cadence**: Quarterly scorecard review (when available)

### WAIVER-007: Dependency Review Failure (Phase 4)
**Status**: Non-blocking on non-PR events  
**Pattern**: `if: github.event_name == 'pull_request'` (conditional)  
**Reason**: Only runs on PRs, not on direct pushes to main  
**Impact**: No dependency review on hotfixes  
**Review Cadence**: Post-hotfix dependency audit

---

## Pre-Commit Hook Exclusions

**Source**: .pre-commit-config.yaml

### EXCLUSION-001: test_gates_all_types.py
**Hooks Excluded**: mypy, pytest  
**Reason**: Requires mock updates for new gate types  
**Expiration**: When gate type mocks updated  
**File**: tests/unit/gates/test_gates_all_types.py

### EXCLUSION-002: test_scoring.py
**Hooks Excluded**: mypy, pytest  
**Reason**: Requires mock updates for new scoring dimensions  
**Expiration**: When scoring mocks updated  
**File**: tests/unit/scoring/test_scoring.py

### EXCLUSION-003: test_config.py
**Hooks Excluded**: mypy  
**Reason**: Requires Settings mock updates  
**Expiration**: When Settings class stabilizes  
**File**: tests/unit/config/test_config.py

**Review Requirement**: These exclusions must be removed when mock updates are completed. Permanent exclusions not allowed.

---

## Gitleaks Secret Scanning Waivers

**Source**: .gitleaksignore

**Total Waivers**: 0 (file is empty)

**Decision**: No secrets currently excepted from scanning. All secrets must be in .env files or vault.

---

## Ruff Ignore List (pyproject.toml)

**Frozen per INVARIANT-017**: Ruff ignore list is frozen. New ignores require architectural approval.

**Global Ignores** (apply to all files):
```python
E501,     # line too long (formatter handles)
TRY003,   # long exception messages (acceptable)
TRY400,   # logging.error vs logging.exception
EM101,    # raw string in exception
EM102,    # f-string in exception
PLR0913,  # too many arguments (threshold: 8)
PLR0912,  # too many branches (threshold: 15)
PLR0911,  # too many return statements (threshold: 8)
PLR2004,  # magic value comparison
TC001,    # typing-only first-party import (runtime issue)
TC003,    # typing-only stdlib import (runtime issue)
ARG001-5, # unused function/method/lambda args (interface compliance)
PT011,    # pytest.raises too broad
SIM102,   # collapsible if (readability preference)
SIM105,   # contextlib.suppress (explicit try/except clearer)
RET504,   # unnecessary assign before return
PLC0415,  # import outside top-level (lazy imports)
PLW0603,  # global statement (module singletons)
DTZ005,   # datetime.now without tz (scheduler local time)
RUF012,   # mutable class default (ClassVar not always needed)
RUF013,   # implicit Optional (legacy code)
TRY004,   # TypeError vs other exception
B007,     # unused loop control variable
E741,     # ambiguous variable name (short vars in tools)
PLC0206,  # dict index missing items (dynamic dicts)
S104,     # bind 0.0.0.0 (containerized)
S110,     # try-except-pass (optional feature degradation)
S112,     # try-except-continue (resilient batch ops)
S311,     # non-crypto random (scoring jitter, test data)
S108,     # hardcoded tmp (containerized)
```

**Impact**: These patterns are allowed repo-wide. Agent code may trigger these rules without CI failure.

**Per-File Ignores**: See pyproject.toml `[tool.ruff.lint.per-file-ignores]` section for directory-specific exceptions.

---

## Coverage Threshold Waivers

**CI Default**: 60% (`COVERAGE_THRESHOLD` in ci.yml)  
**Global Minimum**: 70% (`fail_under` in pyproject.toml)  
**Layer-Specific**: 95% for engine/gates/, engine/scoring/ (TESTING.md)

**Hierarchy**: Layer-specific > Global > CI default

**No Waivers**: Coverage cannot be reduced below thresholds without architectural approval.

---

## Decision Matrix for Agents

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

## Known Unknowns

1. **Gitleaks rule count**: `.gitleaks.toml` exists but was not audited for custom rule count
2. **Semgrep usage**: Referenced in enforcement docs but no config found in `.semgrep/`
3. **ADR files**: Waiver pattern suggests ADRs for each whitelist item, but none found

**Agent Action**: If CI reports a failure not listed here, reference ci.yml directly for that step's configuration.

---

## Related Documents

- **Source**: .github/workflows/ci.yml (CI pipeline definition)
- **Source**: .pre-commit-config.yaml (hook exclusions)
- **Source**: .gitleaksignore (secret scan waivers — currently empty)
- **Source**: pyproject.toml (ruff ignore list)
- **Coverage**: TESTING.md (layer-specific thresholds)
- **Security**: GUARDRAILS.md (secret hygiene, banned patterns)
