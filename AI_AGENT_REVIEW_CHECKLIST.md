<!-- L9_META
l9_schema: 1
origin: audit-corrected
engine: graph
layer: [code-review]
tags: [pr-review, checklist, ai-agents]
owner: platform
status: active
/L9_META -->

# AI_AGENT_REVIEW_CHECKLIST.md — PR Review Checklist for AI Agents

**Purpose**: Step-by-step PR review checklist with severity scoring rubric and comment templates.

**Target Agents**: CodeRabbit, Qodo, Claude PR Reviewer

**Last Verified**: SHA 358d15d (2026-04-02)

---

## Review Decision Rubric

| Verdict | Conditions |
|---------|-----------|
| **APPROVE** | 0 CRITICAL + 0 HIGH + any number MEDIUM/LOW |
| **COMMENT** | 0 CRITICAL + 1-2 HIGH (provide guidance, non-blocking) |
| **REQUEST_CHANGES** | Any CRITICAL violation OR 3+ HIGH violations OR coverage < 70% |

---

## Priority-Ordered Checklist

### 1. Security (CRITICAL)

**SEC-001: Cypher Injection Prevention (C-009)**
- [ ] All Cypher labels pass `sanitize_label()` before f-string interpolation
- [ ] All Cypher values use parameterized queries (`$param`)
- [ ] No f-string value interpolation (e.g., `f"WHERE id = '{value}'"` is forbidden)
- **Severity**: CRITICAL
- **Template**: See §Comment Templates below

**SEC-002: Hardcoded Secrets**
- [ ] No API keys, passwords, tokens in source code
- [ ] All secrets in .env files or AWS Secrets Manager
- [ ] .env files are gitignored
- **Severity**: CRITICAL
- **Template**: "Hardcoded secret detected. Move to .env or vault. See GUARDRAILS.md §8"

**SEC-003: Prohibited Factors (C-010)**
- [ ] No gate/scoring references to: race, ethnicity, religion, gender, age, disability, familial_status, national_origin
- [ ] If prohibited field used → compilation must fail (not runtime check)
- **Severity**: CRITICAL
- **Template**: "Prohibited factor '{field}' detected. Remove from gate spec. Contract C-010"

**SEC-004: PII Logging (C-011)**
- [ ] No PII values in log statements (names, emails, phones, addresses)
- [ ] PII redacted/hashed per domain spec compliance.pii.handling
- **Severity**: HIGH
- **Template**: "PII value logged. Use structlog PII filter or redact. Contract C-011"

### 2. Architecture Invariants (HIGH)

**ARCH-001: Engine/Chassis Boundary (C-001)**
- [ ] No `from fastapi import` in engine/
- [ ] No `from starlette import` in engine/
- [ ] No `import uvicorn` in engine/
- [ ] Only handlers.py and boot.py import from chassis/
- **Severity**: HIGH
- **Template**: See §Comment Templates below

**ARCH-002: HTTP Entry Point (C-001)**
- [ ] URL pattern is `/v1/{tenant}/{action}` (not `/v1/execute`)
- [ ] Handler signatures: `async def handle_*(tenant: str, payload: dict) -> dict`
- **Severity**: HIGH

**ARCH-003: Tenant Isolation (C-003)**
- [ ] Tenant resolved BY chassis, not engine
- [ ] Engine receives tenant as string argument
- [ ] No cross-tenant Neo4j queries
- **Severity**: HIGH

**ARCH-004: PacketEnvelope Protocol (C-006, C-007, C-008)**
- [ ] No redefinition of PacketEnvelope, TenantContext, ExecuteRequest
- [ ] New packets via `.derive()` or `PacketEnvelope.create()` only
- [ ] No manual content_hash assignment
- **Severity**: HIGH

### 3. Contract Compliance (MEDIUM)

**CON-001: Feature Flag Gating (C-021)**
- [ ] All behavioral changes gated by bool flag in settings.py
- [ ] Flag default: False for experimental, True for production-ready
- **Severity**: MEDIUM
- **Template**: "Behavioral change not gated. Add feature flag. Contract C-021. See FEATURE_FLAGS.md"

**CON-002: Scoring Weight Sum (C-022)**
- [ ] If new scoring weight added → existing weights reduced proportionally
- [ ] Sum of all default weights ≤ 1.0
- [ ] Startup assertion `_assert_default_weight_sum()` will verify
- **Severity**: MEDIUM

**CON-003: L9_META Headers (C-018)**
- [ ] All new .py files have L9_META header
- [ ] Use `tools/l9_meta_injector.py` (not manual)
- **Severity**: LOW
- **Template**: "Missing L9_META header. Run tools/l9_meta_injector.py. Contract C-018"

### 4. Code Quality (MEDIUM)

**QUAL-001: Ruff Compliance**
- [ ] `ruff check` passes with no violations
- [ ] `ruff format --check` passes (code formatted)
- **Severity**: MEDIUM

**QUAL-002: MyPy Type Checking**
- [ ] All function signatures have type hints
- [ ] `mypy engine/` passes (warnings OK, errors block)
- **Severity**: MEDIUM

**QUAL-003: Exception Messages**
- [ ] Exception messages in variables (not f-strings in raise)
- [ ] Pattern: `msg = f"..."; raise ValueError(msg)` (avoids EM101/EM102)
- **Severity**: LOW

### 5. Testing (HIGH if coverage < threshold, else MEDIUM)

**TEST-001: Coverage Thresholds**
- [ ] Global: ≥70% (pyproject.toml)
- [ ] engine/gates/: ≥95%
- [ ] engine/scoring/: ≥95%
- [ ] Other engine/: ≥70%
- **Severity**: HIGH if < threshold, MEDIUM if close

**TEST-002: Test Patterns**
- [ ] Unit tests for pure functions (no Neo4j mocks)
- [ ] Integration tests use testcontainers-neo4j (not mocked driver)
- [ ] Compliance tests for prohibited factors
- **Severity**: MEDIUM

**TEST-003: New Module Coverage**
- [ ] Every new function has ≥1 unit test
- [ ] Every new handler has ≥1 integration test
- **Severity**: MEDIUM

### 6. Documentation (LOW)

**DOC-001: Contract Documentation**
- [ ] If modifying contract → update docs/contracts/{CONTRACT}.md
- [ ] If adding contract → add to .claude/rules/contracts.md + INVARIANTS.md
- **Severity**: LOW

**DOC-002: Feature Flag Documentation**
- [ ] If adding flag → add to FEATURE_FLAGS.md
- **Severity**: LOW

---

## PR Scenario-Specific Checks

### New Feature PR
- [ ] Feature flag exists and defaults to False (C-021)
- [ ] Tests cover both enabled and disabled paths
- [ ] No breaking changes to existing domain specs

### Bug Fix PR
- [ ] Regression test added (prevents bug from returning)
- [ ] Root cause documented in commit message

### Dependency Update PR
- [ ] License unchanged or compatible
- [ ] CVE scan clean (pip-audit passes)
- [ ] Transitive deps checked (poetry show --tree)

### Domain Spec Change PR
- [ ] Backward compatible (existing tenants unaffected)
- [ ] Validation passes (tools/validate_domain.py)
- [ ] Migration guide if schema changed

### CI Workflow Change PR
- [ ] No bypass of required checks
- [ ] No secret exposure risk
- [ ] Non-blocking additions documented in CI_WHITELIST_REGISTER.md

### Refactoring PR
- [ ] Contract scanner re-run passes
- [ ] No behavior change (tests prove equivalence)
- [ ] Coverage maintained or improved

---

## Comment Templates

### Template: Cypher Injection (SEC-001)
```markdown
**Severity**: CRITICAL (SEC-001)
**Contract**: C-009
**File**: {path} line {line}
**Issue**: Label interpolated without `sanitize_label()`

**Current**:
\`\`\`python
cypher = f"MATCH (n:{spec.targetnode}) WHERE n.id = $id"
\`\`\`

**Fix**:
\`\`\`python
from engine.utils.security import sanitize_label

label = sanitize_label(spec.targetnode)
cypher = f"MATCH (n:{label}) WHERE n.id = $id"
\`\`\`

**Reference**: GUARDRAILS.md §1, INVARIANTS.md C-009
```

### Template: Engine Boundary Violation (ARCH-001)
```markdown
**Severity**: HIGH (ARCH-001)
**Contract**: C-001
**File**: {path} line {line}
**Issue**: FastAPI imported in engine/ code

**Current**:
\`\`\`python
from fastapi import HTTPException
raise HTTPException(status_code=400, detail="Invalid")
\`\`\`

**Fix**:
\`\`\`python
# Use standard Python exceptions in engine/
msg = "Invalid gate configuration"
raise ValueError(msg)
\`\`\`

**Reference**: GUARDRAILS.md §2, INVARIANTS.md C-001
```

### Template: Missing Feature Flag (CON-001)
```markdown
**Severity**: MEDIUM (CON-001)
**Contract**: C-021
**File**: {path} line {line}
**Issue**: Behavioral change not gated by feature flag

**Fix**:
1. Add to `engine/config/settings.py`:
   \`\`\`python
   my_feature_enabled: bool = Field(default=False, description="...")
   \`\`\`
2. Gate behavior:
   \`\`\`python
   if settings.my_feature_enabled:
       # new behavior
   else:
       # existing behavior
   \`\`\`
3. Document in FEATURE_FLAGS.md

**Reference**: INVARIANTS.md C-021, FEATURE_FLAGS.md
```

---

## Agent-Specific Guidance

### CodeRabbit
- Load: GUARDRAILS.md + AGENTS.md + this checklist (~5,000 tokens)
- Use rubric for APPROVE/COMMENT/REQUEST_CHANGES decision
- Inline comments at violation lines (not summary only)

### Qodo (formerly CodiumAI)
- Focus on SEC and TEST sections (security + coverage)
- Suggest test cases for uncovered branches
- Flag overly complex functions (>15 branches)

### Claude PR Reviewer
- Load full context: GUARDRAILS.md + INVARIANTS.md + this checklist (~6,000 tokens)
- Provide reasoning for each violation flagged
- Cross-reference contract numbers (C-001 to C-024)

---

## Review Completion Checklist

Before finalizing review:
- [ ] Checked all CRITICAL items
- [ ] Scored severity for each violation
- [ ] Applied rubric for final decision
- [ ] Used comment templates for standard violations
- [ ] Cross-referenced contract numbers
- [ ] Verified coverage thresholds
- [ ] Confirmed PR scenario (new feature, bug fix, etc.) and applied scenario-specific checks

---

## Related Documents

- **GUARDRAILS.md** — Safety rules, forbidden primitives
- **INVARIANTS.md** — All 24 contracts (C-001 to C-024)
- **AGENTS.md** — Universal agent instructions, git workflow
- **TESTING.md** — Coverage thresholds, test patterns
- **FEATURE_FLAGS.md** — Feature flag inventory and patterns
