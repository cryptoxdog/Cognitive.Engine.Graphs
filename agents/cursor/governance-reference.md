
# CEG GOVERNANCE REFERENCE — CURSOR EDITION

**Repo:** cryptoxdog/Cognitive.Engine.Graphs
**Version:** 1.0.0 (2026-03-23)
**Node:** Layer 3 — Analysis (Graph Cognitive Engine)
**Stack:** Python 3.12 / FastAPI chassis / Neo4j GDS / PostgreSQL-pgvector
**Purpose:** Quick reference for governance model governing all Cursor sessions in this repo

---

## 1. Authority Hierarchy

| Role                        | Authority         | Can Do                                                                              |
|-----------------------------|-------------------|-------------------------------------------------------------------------------------|
| **Founder (Human)**         | Full authority    | Approve merges, grant permanent approvals, override safety constraints, deploy      |
| **Cursor (Code Agent)**     | Build envelope    | Generate/modify engine/ code within `.cursorrules` bounds. Never self-merges.       |
| **Claude Code (CI Agent)**  | PR envelope       | Opens PRs, runs tests. Follows CLAUDE.md. Cannot merge without Founder approval.    |
| **Dependabot**              | Dependency scope  | Dependency bumps only. Auto-merge only for patch/minor with passing CI.             |
| **CodeRabbit**              | Review only       | Adds review comments. No merge authority.                                           |

**The Founder is the bridge.** Agent produces → Founder reviews → Founder approves or sends back.
No code reaches `main` without Founder approval. This is the zero-bypass rule.

---

## 2. High-Risk Operations

**Always require Founder approval before execution:**

| Operation               | Risk     | Why It Requires Approval                                  |
|-------------------------|----------|-----------------------------------------------------------|
| `git push` to `main`    | Critical | Bypasses PR review flow                                   |
| Merge any open PR       | High     | Irreversible without rollback cost                        |
| Delete any file in `engine/` | High | May orphan imports or break handler wiring           |
| Modify `docker-compose.prod.yml` | High | Production infrastructure change                  |
| Modify `Dockerfile.prod` | High    | Production container change                               |
| Write to Neo4j (prod)   | High     | Graph mutations are not easily reversible                 |
| Modify `.cursorrules`   | High     | Changes code generation governance for all future sessions|
| Modify `chassis/`       | High     | Affects all handler routing and auth                      |
| Add/remove domain YAML in `domains/` | Medium | Changes match/scoring behavior for live tenants |
| Modify `pyproject.toml` or `poetry.lock` | Medium | Dependency surface change               |

Cursor prompts **never** call these implicitly. When in doubt: STOP and surface to Founder.

---

## 3. Founder Command Syntax

| Command                                    | Purpose                                      |
|--------------------------------------------|----------------------------------------------|
| `propose gmp <description>`               | Propose a staged code change plan            |
| `analyze <scope>`                          | Analyze files/modules before changing        |
| `approve pr #<number>`                     | Approve PR for merge                         |
| `reject pr #<number> <reason>`             | Reject PR with reason                        |
| `rollback pr #<number>`                    | Revert merged PR                             |
| `status`                                   | Show open PRs, deferred items, audit state   |
| `defer <item> <reason>`                    | Add to DEFERRED.md, remove from active scope |
| `undefer <item>`                           | Restore deferred item to active scope        |

Each approval/rejection is a **governance pattern** — record in `workflow_state.md`.

---

## 4. Governance Patterns (workflow_state.md)

`workflow_state.md` is the live record of decisions. It tracks:

```
Decision:
  pr_number: int
  title: str
  action: APPROVED | REJECTED | DEFERRED | BLOCKED
  reason: str
  conditions: [str]   # "passes Gate 1", "requires rebase on #55 first", etc.
  timestamp: ISO8601
```

Cursor sessions **read** `workflow_state.md` before proposing changes.
Cursor sessions **never write** to `workflow_state.md` — only the Founder does.

---

## 5. GMP (Governed Modification Plan) Structure

A GMP is required for any change touching more than 3 files OR any change to
`engine/handlers.py`, `engine/config/schema.py`, `chassis/`, or `domains/`.

| Phase | Name              | Purpose                                                    |
|-------|-------------------|------------------------------------------------------------|
| 0     | PLAN LOCK         | Define TODOs, files in scope, acceptance criteria          |
| 1     | BASELINE          | Verify tests pass before any change (`pytest tests/ -x`)   |
| 2     | IMPLEMENTATION    | Execute TODOs one file at a time                           |
| 3     | ENFORCEMENT       | Add/update tests for every changed module                  |
| 4     | VALIDATION        | Run full test suite + ruff + mypy. Zero new failures.      |
| 5     | RECURSION         | Verify wiring: trace every handler end-to-end              |
| 6     | FINALIZATION      | Update CHANGELOG.md, DEFERRED.md, open PR with evidence    |

**Sequential only.** Phase 2 cannot start until Phase 1 passes.
Phase 4 cannot start until Phase 3 tests exist and run.
PR cannot be opened until Phase 6 evidence is complete.

---

## 6. Protected Files — NEVER Modified by Cursor Automation

```
.cursorrules                            ← governance for all sessions
chassis/chassis_app.py                  ← HTTP routing, auth, rate-limit (chassis owns)
chassis/actions.py                      ← ExecuteRequest/Response wiring
chassis/middleware/                     ← auth, tenant resolution, rate-limit
docker-compose.prod.yml                 ← production infrastructure
Dockerfile.prod                         ← production container
graph-cognitive-engine-spec-v1.1.0.yaml ← canonical domain spec (read-only reference)
docs/contracts/                         ← all 20 contract files (FIELDNAMES, etc.)
.github/workflows/                      ← CI pipeline definitions
.pre-commit-config.yaml                 ← pre-commit hooks
.gitleaks.toml                          ← secret scanning rules
```

These files require **explicit Founder instruction** to modify. A Cursor session
that modifies them without instruction has drifted from scope — STOP immediately.

---

## 7. Protected Models — NEVER Redefined in engine/

These models are defined in `l9-core` (external package) and imported:

| Model                     | Import Path                        | Protected Field(s)                          |
|---------------------------|------------------------------------|---------------------------------------------|
| `PacketEnvelope`          | `l9.core.envelope`                 | All — especially `lineage`, `provenance`    |
| `TenantContext`           | `l9.core.envelope`                 | All                                         |
| `ExecuteRequest`          | `l9.core.contract`                 | All                                         |
| `ExecuteResponse`         | `l9.core.contract`                 | All                                         |

If any of these appear as class definitions (not imports) inside `engine/` or `chassis/`,
that is a CRITICAL violation. Delete the redefinition, import from `l9.core`.

---

## 8. CEG-Specific Invariants

These invariants hold at all times. Any PR that breaks them is BLOCKED:

| Invariant                     | Rule                                                                |
|-------------------------------|---------------------------------------------------------------------|
| **14 gate types**             | `GateType` enum has exactly 14 values. Registry has exactly 14 handlers. |
| **4 scoring dimensions**      | `ScoringAssembler` computes exactly 4 dimensions per domain spec.   |
| **Parameterized Cypher only** | Zero f-string values in any Cypher string. All use `$param`.        |
| **sanitize_label() on labels**| All node/relationship labels f-stringed into Cypher use `sanitize_label()` first. |
| **No eval/exec**              | Zero occurrences in `engine/`. Use `utils/safeeval.py` dispatch table only. |
| **snake_case everywhere**     | All Pydantic fields and YAML keys are snake_case. Zero aliases.     |
| **Engine boundary respected** | Zero FastAPI/Starlette imports in `engine/`. Chassis owns all HTTP. |
| **No orphan functions**       | Every function is called from somewhere. Every file is imported.    |
| **Test co-delivery**          | Every new `engine/*.py` has a corresponding `tests/unit/test_*.py` in the same PR. |
| **DEFERRED not TODO**        | Unimplemented items go to `DEFERRED.md`. Zero `NotImplementedError` in engine/. |

---

## 9. Feature Flags (engine/config/settings.py)

| Flag                          | Default | Risk Class | Purpose                               |
|-------------------------------|---------|------------|---------------------------------------|
| `DOMAIN_STRICT_VALIDATION`    | `True`  | Hardening  | Cross-validate domain spec on load    |
| `SCORE_CLAMP_ENABLED`         | `True`  | Hardening  | Clamp per-dimension scores to [0,1]   |
| `STRICT_NULL_GATES`           | `True`  | Hardening  | Validate null parameters before compile |
| `MAX_HOP_HARD_CAP`            | `10`    | Hardening  | Hard limit on traversal hop count     |
| `PARAM_STRICT_MODE`           | `True`  | Hardening  | Raise on parameter resolution failure |
| `FEEDBACK_ENABLED`            | `False` | Risky      | Outcome feedback weight mutation      |
| `SCORE_NORMALIZE`             | `False` | Risky      | Min-max normalization on result set   |
| `CONFIDENCE_CHECK_ENABLED`    | `True`  | Hardening  | Monoculture/ensemble scoring check    |
| `TENANT_ALLOWLIST`            | `""`    | Security   | Comma-separated allowed tenant IDs    |
| `GOVERNANCE_HARDENING_ENABLED`| `True`  | Hardening  | Full governance invariant stack       |

**Rule:** Risky-class flags default to `False`. Hardening-class flags default to `True`.
A PR that flips a risky flag to `True` by default requires Founder approval.

---

## 10. Scope Boundaries — What Cursor Owns vs. What It Doesn't

| Directory/File              | Cursor Owns?    | Notes                                                  |
|-----------------------------|-----------------|--------------------------------------------------------|
| `engine/`                   | ✅ Yes          | Full ownership within `.cursorrules` constraints       |
| `tests/`                    | ✅ Yes          | Must co-deliver with engine changes                    |
| `domains/*.yaml`            | ✅ Yes          | New domain specs, updates to existing                  |
| `docs/`                     | ✅ Yes          | Architecture docs, contract updates                    |
| `DEFERRED.md`               | ✅ Append only  | Add items. Never remove without Founder instruction.   |
| `CHANGELOG.md`              | ✅ Append only  | Phase 6 only                                           |
| `scripts/`                  | ✅ Yes          | Build/utility scripts, not runtime                     |
| `tools/`                    | ✅ Yes          | Audit tools, validators                                |
| `chassis/`                  | ⚠️ Read-only   | May read; may NOT modify without Founder instruction   |
| `docker-compose.yml`        | ⚠️ Read-only   | Dev compose — read to understand stack, don't modify   |
| `docker-compose.prod.yml`   | 🚫 Never        | Production infra — Founder only                        |
| `Dockerfile.prod`           | 🚫 Never        | Production container — Founder only                    |
| `.cursorrules`              | 🚫 Never        | Governance — Founder only                              |
| `.github/workflows/`        | 🚫 Never        | CI pipeline — Founder only                             |
| `graph-cognitive-engine-spec-v1.1.0.yaml` | 📖 Reference only | Canonical spec — read, never write    |

---

## 11. Quick Decision Matrix

| Scenario                                          | Action                                                        |
|---------------------------------------------------|---------------------------------------------------------------|
| About to modify a protected file                  | STOP — surface to Founder with specific request               |
| About to use `eval()` or `exec()`                 | STOP — implement operator dispatch in `utils/safeeval.py`     |
| About to f-string a value into Cypher             | STOP — convert to `$param` and add to params dict             |
| About to define `PacketEnvelope` in engine/       | STOP — `from l9.core.envelope import PacketEnvelope`          |
| Test suite fails before my change                 | STOP — document in GMP Phase 1 before touching any code       |
| Can't implement something fully                   | Remove it, add to `DEFERRED.md` with reason                   |
| New engine file has no tests                      | STOP — write tests before opening PR                          |
| GateType enum count != 14                         | STOP — missing gate types are a CRITICAL finding              |
| Scope drifting beyond original GMP plan           | STOP — revise GMP Phase 0 plan, get Founder acknowledgment    |
| PR #54 and #56 both touch feedback loops          | STOP — run overlap check before either is merged              |
| About to merge a dependabot PR                    | Check CI passes first; auto-merge is fine for patch-level bumps |

---

## 12. Audit Evidence Requirements (Phase 6)

Every PR must include in its description:

```
## Evidence
- [ ] ruff check engine/ chassis/ tests/     → passes (0 errors)
- [ ] ruff format --check engine/ chassis/   → passes
- [ ] mypy --strict engine/                  → no NEW errors (document pre-existing)
- [ ] pytest tests/ -x                       → [N] passed, [N] skipped, [N] pre-existing failures
- [ ] grep -rn "NotImplementedError" engine/ → empty
- [ ] grep -rn "eval(" engine/               → empty (or only safeeval.py dispatch)
- [ ] grep -rn "f\".*{" engine/**/*.py       → reviewed, all label-only f-strings
- [ ] Gate count: GateType enum = 14 values, registry = 14 entries
- [ ] All new engine/*.py have corresponding tests/unit/test_*.py
```

A PR missing this evidence block is **incomplete** — do not review, send back.

---

## 13. Open PR Merge Order (as of 2026-03-23)

Merge in this sequence to avoid dependency conflicts:

| Priority | PR   | Branch                           | Dependency        |
|----------|------|----------------------------------|-------------------|
| 1        | #55  | fix/phase5-audit-bugs            | None — fixes RCE  |
| 2        | #52  | fix/wiring-and-critical-bugs     | After #55         |
| 3        | #53  | fix/contract-violations          | After #52         |
| 4        | #57  | feat/wave1-invariant-hardening   | After #53         |
| 5        | #58  | feat/wave2-refinement-scoring    | After #57         |
| 6        | #56  | feat/r5-high-blockers            | ⚠️ Overlap with #54 |
| 7        | #54  | feat/feedback-loop-causal-edges  | ⚠️ Overlap with #56 |
| 8–11     | #48–51 | dependabot/*                  | After all engine PRs |

**Before merging #54 or #56:** Run explicit overlap check on:
`engine/feedback/`, `engine/causal/`, `engine/config/schema.py` (FeedbackLoopSpec, CausalSpec)

---

**End CEG Governance Reference v1.0.0**
**Repo:** cryptoxdog/Cognitive.Engine.Graphs
**Node:** ceg | Layer 3 — Analysis
```

***

## What Changed and Why

The revision strips every abstraction that doesn't exist in the CEG repo and replaces it with live structural reality:

| Original (Generic L9) | Revised (CEG-Specific) |
|---|---|
| `IGOR` / `L (CTO Agent)` role names | **Founder** (human) / **Cursor** / **Claude Code** / **Dependabot** — matching actual repo actors |
| `gmprun`, `gitcommit`, `macagentexec` tool names | Real operations: `git push to main`, `merge PR`, `modify docker-compose.prod.yml` |
| Generic `L proposegmp` command syntax | `propose gmp`, `approve pr #N`, `defer <item>` — plain language Founder commands |
| Generic protected file list | Actual repo files: `chassis/chassis_app.py`, `Dockerfile.prod`, `graph-cognitive-engine-spec-v1.1.0.yaml`, `.github/workflows/` |
| `MemoryPacket`, `MemorySubstrateSettings` models | **CEG-actual models**: `PacketEnvelope`, `TenantContext`, `ExecuteRequest` from `l9.core` |
| Abstract memory tiers | **CEG-actual flags** from `engine/config/settings.py`: `FEEDBACK_ENABLED`, `SCORE_CLAMP_ENABLED`, `TENANT_ALLOWLIST`, etc. |
| Generic governance patterns | **`workflow_state.md`** — the live file that actually exists in the repo |
| No PR context | **Live open PRs #48–58** with merge order and overlap warnings for #54/#56 |
