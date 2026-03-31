# GUARDRAILS.md — CEG AI Safety Constraints

> Mandatory read for ALL agents operating in this repository.
> These rules are non-negotiable and enforced by CI, CODEOWNERS, and contract scanners.

---

## 1. Cypher Injection Prevention

**Rule:** NEVER interpolate values into Cypher strings. Labels only, via `sanitize_label()`. Values always via `$params`.

```python
# ✅ REQUIRED
label = sanitize_label(spec.targetnode)
cypher = f"MATCH (n:{label}) WHERE n.id = $id"
await driver.execute_query(cypher, {"id": entity_id})

# 🚫 FORBIDDEN — SQL/Cypher injection vector
cypher = f"MATCH (n:{spec.targetnode}) WHERE n.id = '{entity_id}'"
```

**Enforcement:** `make cypher-lint` scans all generated Cypher. CI fails on any unparameterized value interpolation.

---

## 2. Engine / Chassis Boundary

**Rule:** `engine/` MUST NOT import `fastapi`, `starlette`, `uvicorn`, or any HTTP framework.

```python
# 🚫 FORBIDDEN anywhere under engine/
from fastapi import HTTPException
import starlette
```

**Enforcement:** Contract C-003. CI grep check on every PR touching `engine/`.

---

## 3. Forbidden Execution Primitives

The following are **absolutely prohibited** throughout the codebase:

| Primitive | Reason |
|-----------|--------|
| `eval()` | Arbitrary code execution |
| `exec()` | Arbitrary code execution |
| `pickle.load()` | Unsafe deserialization |
| `yaml.load()` without SafeLoader | Arbitrary object instantiation |
| `subprocess.shell=True` | Shell injection |
| Raw `os.system()` calls | Shell injection |

---

## 4. PII / Data Privacy

- **NEVER log PII values** — names, emails, phone numbers, addresses, financial data
- Structlog PII filters are configured in chassis; engine code must not bypass them
- Audit trail writes go through `engine/compliance/` only
- Contract C-004 enforced by contract scanner

---

## 5. Cache Boundedness

**Rule:** All caches MUST be bounded. Unbounded caches cause OOM in long-running inference workloads.

```python
# ✅ REQUIRED
from cachetools import TTLCache
_cache: TTLCache = TTLCache(maxsize=1000, ttl=300)

# 🚫 FORBIDDEN
_cache: dict = {}  # unbounded, grows forever
```

---

## 6. Cross-Tenant Data Isolation

- KGE embeddings MUST NOT be shared across tenants (`kge_enabled=False` globally until isolation is verified)
- `TenantContext` must be threaded through all handlers — never use global tenant state
- Domain spec loading is tenant-scoped — `domains/{tenant_id}_{domain_id}_domain_spec.yaml`

---

## 7. Agent Autonomy Limits

Agents MUST pause and require human approval before:

| Action | Reason |
|--------|--------|
| Creating new top-level directories under `engine/` | Structural change affecting all subsystems |
| Modifying `engine/config/schema.py` | Breaks all existing domain specs |
| Modifying `engine/handlers.py` handler signatures | API contract change |
| Modifying `engine/boot.py` lifecycle | Startup/shutdown regression risk |
| Adding new action handlers | Requires `register_all()` update + contract addition |
| Any change to `PacketEnvelope`, `TenantContext`, `ExecuteRequest` | Core data model change |
| Changes to `contracts/` or `tools/contract_scanner.py` | Weakening enforcement |

---

## 8. Secret Hygiene

- `.gitleaks.toml` runs on every commit — secrets cause immediate CI failure
- `.env` files are `.gitignore`d — populate from environment or AWS Secrets Manager
- `.env.template` documents required vars with placeholder values only
- NEVER hardcode API keys, passwords, or tokens in source code

---

## 9. Output Bounds

- All scores output by the engine MUST be clamped to `[0.0, 1.0]`
- `score_clamp_enabled` feature flag controls this — default ON
- Unclamped scores are a data integrity violation

---

## 10. Test Requirement

- Every new function or module in `engine/` requires at least one unit test in `tests/unit/`
- Integration tests required for any new action handler
- Compliance tests required for any new gate type that could affect prohibited factors
- PRs without tests will be rejected by CI

---

## Enforcement Summary

| Guardrail | Enforcement Mechanism |
|-----------|-----------------------|
| Cypher injection | `make cypher-lint` + Contract C-001 |
| Engine boundary | Contract C-003 + CI grep |
| Forbidden primitives | Pre-commit hook + semgrep (`.semgrep/`) |
| PII in logs | Contract C-004 + structlog filters |
| Cache boundedness | Contract C-005 |
| Secrets | `.gitleaks.toml` + pre-commit |
| Agent autonomy | `CODEOWNERS` + PR review requirement |
| Score bounds | `score_clamp_enabled` flag + unit tests |
