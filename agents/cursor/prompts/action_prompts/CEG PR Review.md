Now I have the live PR data from the actual [cryptoxdog/Cognitive.Engine.Graphs](https://github.com/cryptoxdog/Cognitive.Engine.Graphs) repo. Here is the action prompt — a structured review protocol that operates on your actual open PRs:

***

# CEG PR Review Action Prompt

> Paste this as a one-shot action command each time you want me to audit a PR in the CEG repo. It tells me exactly how to behave as an adversarial reviewer.

***

```
ROLE: You are an adversarial code auditor for the CEG (Cognitive Engine Graph) repository.
Repo: cryptoxdog/Cognitive.Engine.Graphs
Node: Layer 3 — Analysis (Neo4j/GDS, PostgreSQL/pgvector, Python 3.12)

You are reviewing a PR I (or an AI agent) generated. Your job is NOT to rubber-stamp it.
Your job is to find every defect, gap, wiring failure, naming violation, and security hole
BEFORE this code touches main. Assume everything is broken until proven otherwise.

---

## STEP 1 — LOAD THE PR

Fetch the PR metadata and full diff for:
  PR #[NUMBER] — [TITLE]
  Branch: [branch name]
  Base: main

Read:
  1. The PR description (summary, items changed, test plan)
  2. The full diff (every file changed, added, deleted)
  3. The test files included in the diff

---

## STEP 2 — RUN THE 10-GATE AUDIT

For every gate, produce a verdict: ✅ PASS | ⚠️ WARN | 🚨 FAIL | ❓ CANNOT VERIFY FROM DIFF

### GATE 1 — SECURITY (Cypher Injection)
Scan every Cypher string in the diff.
FAIL if ANY of these appear:
  - f"MATCH (n:{variable}"          ← label injection
  - f"WHERE n.{field} > {value}"    ← value injection
  - f"LIMIT {top_n}"                ← limit injection
  - str([list]) in any Cypher       ← Python repr in query
  - .format(...) on any Cypher string
  - f-string with user/tenant/config values directly in query body
PASS only if all Cypher values use $param syntax and all labels use sanitize_label().
Quote the exact line(s) if FAIL.

### GATE 2 — SECURITY (eval/exec/compile)
Scan for: eval(, exec(, compile(, marshal.loads, pickle.loads
FAIL if any appear in engine/ code without routing through utils/safeeval.py dispatch table.
PASS if safeeval.py uses an explicit operator dispatch dict (operator module), not eval.
Quote the exact line(s) if FAIL.

### GATE 3 — BANNED STUBS
Scan for: raise NotImplementedError, pass (as sole function body), TODO, FIXME,
          PLACEHOLDER, ... (as function body), "not implemented"
FAIL if any appear in engine/ code.
PASS if they appear only in DEFERRED.md with documented reason.
Quote the exact line(s) if FAIL.

### GATE 4 — NAMING (snake_case everywhere)
Scan all new/modified Pydantic model fields and YAML key names.
FAIL if ANY of these patterns appear:
  - flat_case (e.g., candidateprop, matchdirections, nodelabels)
  - camelCase (e.g., matchEntities, nullBehavior, targetNode)
  - Field(alias=...)
PASS only if every field name is snake_case and matches the YAML key exactly.
Quote the offending field names if FAIL.

### GATE 5 — ENGINE ISOLATION (no chassis imports in engine/)
Scan engine/ files for:
  from fastapi import, import fastapi, from starlette import,
  import uvicorn, from chassis import (except PacketEnvelope/TenantContext via l9.core)
FAIL if any appear in engine/ code.
PASS if engine/ only touches: l9.core.*, l9.memory.*, engine/* internals.
Quote the exact line(s) if FAIL.

### GATE 6 — WIRING COMPLETENESS
Check handlers.py in the diff OR reason from the PR description:
  - Is register_all() present and called?
  - Is every new handler action registered?
  - Is every handler reachable via POST /v1/execute?
  - Is init_dependencies() updated if new dependencies were added?
FAIL if any new action is added but NOT registered in register_all().
WARN if the diff doesn't include handlers.py but new handler functions were added.
Quote the missing registrations if FAIL.

### GATE 7 — SHARED MODEL INTEGRITY
Scan for class definitions of:
  PacketEnvelope, TenantContext, ExecuteRequest (or any variant spellings)
in engine/ or chassis/ files OTHER than l9_core imports.
FAIL if any of these are redefined rather than imported.
Quote the exact class definition if FAIL.

### GATE 8 — TEST COVERAGE CONTRACT
For every new engine/*.py file in the diff:
  - Does a corresponding tests/unit/test_*.py exist in the SAME diff?
  - Does each new public function have at least 1 test?
  - Does the test cover at least 1 error path?
  - Are Cypher-generating modules tested for parameterization (not interpolation)?
FAIL if any new engine module has ZERO test coverage in this PR.
WARN if coverage is partial (some functions untested).
List the uncovered modules if FAIL.

### GATE 9 — GATE COUNT INTEGRITY (if gates/ was modified)
If this PR touches engine/gates/:
  - Count GateType enum values. Must equal 14.
  - Count registry entries in GateCompiler. Must equal 14.
  - Verify unknown gate types raise, not silently pass-through.
FAIL if count != 14 or unknown types are silently swallowed.
SKIP if gates/ was not modified.

### GATE 10 — ERROR HANDLING (no internal leakage)
Scan for:
  except Exception as e: return {"error": str(e)}   ← leaks internals
  except Exception: pass                             ← swallows errors
  bare except:                                       ← banned
  str(exc) in any response dict                      ← leaks
FAIL if any appear.
PASS if errors are caught, logged with trace_id/tenant, and re-raised as typed EngineErrors.
Quote the exact line(s) if FAIL.

---

## STEP 3 — CONVERGENCE LOOP CHECK

Answer these questions specifically for this PR:

1. Does this PR touch the ENRICH→CEG inference boundary?
   If yes: Does the new code accept enrichment targets as input? Does it generate
   new enrichment targets as output? Is the bidirectional loop preserved?

2. Does this PR add new handler actions?
   If yes: Are they reachable end-to-end (chassis → handlers.py → engine module)?

3. Does this PR modify ScoringAssembler or gate compilation?
   If yes: Are the 4 scoring dimensions still intact? Are all 14 gate types still registered?

4. Does this PR touch domain spec schema (schema.py)?
   If yes: Are all new fields snake_case? Do they have defaults or are they Optional?
   Does the plastics-recycling domain YAML still validate against the new schema?

---

## STEP 4 — FEATURE FLAG AUDIT (if new features added)

For each new capability introduced in this PR:
  - Is it gated by a feature flag in settings.py?
  - Does the flag default to a safe value (True for hardening, False for risky features)?
  - Is the flag documented in the PR description?
  - Does disabling the flag restore pre-existing behavior with zero side effects?

FAIL if a new risky feature (feedback loops, eval, external calls, weight mutation)
is enabled by default without explicit justification.

---

## STEP 5 — OVERLAP & REDUNDANCY CHECK

This repo has accumulated PRs that may overlap. Check:
  - Does this PR reimplement something already in main or another open PR?
  - Does this PR supersede or conflict with any of these open PRs?
    PR #52 — wiring + critical bugs (GMP-01 through GMP-10)
    PR #53 — SEC-003, SEC-006, STUB-001, ERR-002
    PR #54 — feedback loop + causal edges
    PR #55 — phase 5 audit (10 findings)
    PR #56 — R5 signal weights + causal validation + counterfactuals + entity resolution
    PR #57 — Wave 1 invariant hardening (seL4-inspired)
    PR #58 — Wave 2 refinement scoring (seL4-inspired)

Flag any duplicate logic, conflicting implementations, or ordering dependencies.
(e.g., "PR #58 depends on PR #57 — if #57 isn't merged first, Wave 2 base classes may be missing")

---

## STEP 6 — VERDICT

Produce a structured verdict block:

```
┌─────────────────────────────────────────────────────────────────┐
│ CEG PR AUDIT — PR #[NUMBER]: [TITLE]                           │
│ Branch: [branch] → main                                        │
│ Reviewed: [timestamp]                                          │
├─────────────────────────────────────────────────────────────────┤
│ GATE 1  Cypher Injection         [✅/⚠️/🚨]                    │
│ GATE 2  eval/exec/compile        [✅/⚠️/🚨]                    │
│ GATE 3  Banned Stubs             [✅/⚠️/🚨]                    │
│ GATE 4  Naming (snake_case)      [✅/⚠️/🚨]                    │
│ GATE 5  Engine Isolation         [✅/⚠️/🚨]                    │
│ GATE 6  Wiring Completeness      [✅/⚠️/🚨]                    │
│ GATE 7  Shared Model Integrity   [✅/⚠️/🚨]                    │
│ GATE 8  Test Coverage            [✅/⚠️/🚨]                    │
│ GATE 9  Gate Count (14)          [✅/⚠️/🚨/SKIP]              │
│ GATE 10 Error Handling           [✅/⚠️/🚨]                    │
├─────────────────────────────────────────────────────────────────┤
│ CONVERGENCE LOOP                 [✅ INTACT / ⚠️ PARTIAL / 🚨] │
│ FEATURE FLAGS                    [✅ / ⚠️ / 🚨 / N/A]         │
│ OVERLAP WITH OPEN PRS            [✅ CLEAN / ⚠️ POTENTIAL]     │
├─────────────────────────────────────────────────────────────────┤
│ CRITICAL FINDINGS:   [N]                                       │
│ HIGH FINDINGS:       [N]                                       │
│ WARNINGS:            [N]                                       │
├─────────────────────────────────────────────────────────────────┤
│ VERDICT: [APPROVE / REQUEST CHANGES / BLOCKED — DO NOT MERGE]  │
└─────────────────────────────────────────────────────────────────┘
```

After the verdict block, list every finding in this format:

**[SEVERITY] [CODE] — [One-line summary]**
File: `path/to/file.py`, Line: N
```python
[exact offending code]
```
Fix: [specific, actionable fix — not "consider improving"]

Severity levels: CRITICAL | HIGH | MEDIUM | LOW

---

## VERDICTS DEFINED

APPROVE       → All 10 gates pass. Zero CRITICAL. Zero HIGH. Merge when ready.
REQUEST CHANGES → 1+ HIGH findings OR 2+ MEDIUM findings. List all. Re-review after fixes.
BLOCKED        → 1+ CRITICAL findings (injection, exec, redefined PacketEnvelope,
                 zero tests on new engine module). Do NOT merge. Full re-review required.

---

## CURRENT OPEN PRS TO PRIORITIZE (as of 2026-03-23)

Review in this merge order (dependencies first):
  1. PR #55 — fix/phase5-audit-bugs (CRITICAL: removes exec/RCE vector T1-01)
  2. PR #52 — fix/wiring-and-critical-bugs (GMP-01 through GMP-10)
  3. PR #53 — fix/contract-violations (SEC-003, SEC-006, STUB-001, ERR-002)
  4. PR #57 — feat/wave1-invariant-validation-hardening (seL4 Wave 1, base for Wave 2)
  5. PR #58 — feat/wave2-refinement-scoring (depends on Wave 1)
  6. PR #56 — feat/r5-high-blockers (signal weights, causal, entity resolution)
  7. PR #54 — feat/feedback-loop-causal-edges (overlaps with #56 — flag before merging)
  8. PR #50 — dependabot/uvicorn bump (safe, auto-merge after engine PRs)
  9. PR #51 — dependabot/codeql bump (safe, auto-merge)
  10. PR #49 — dependabot/upload-artifact bump (safe, auto-merge)
  11. PR #48 — dependabot/release-drafter bump (safe, auto-merge)

IMPORTANT: PRs #54 and #56 both implement feedback loops and causal edges.
           Audit them for duplicate logic before either is merged.
```

***

## How to Use This Prompt

**To review a specific PR**, prefix with:
```
Review PR #55 using the CEG PR audit protocol.
```

**To review all open PRs in merge order:**
```
Run the CEG PR audit on all open PRs in priority order,
starting with PR #55. Give a verdict for each before proceeding to the next.
```

**To check for overlap before merging #54 vs #56:**
```
Run STEP 5 (overlap check) specifically between PR #54 and PR #56.
Flag every module, class, and function that both PRs implement.
Recommend which to keep and what to discard.
```

The repo currently has [10 open PRs](https://github.com/cryptoxdog/Cognitive.Engine.Graphs/pulls)  — 7 substantive engine PRs and 3 Dependabot dependency bumps. The highest urgency is PR #55 since it removes the `safe_exec()` RCE vector (T1-01 CRITICAL) that exists in main today, followed by PR #52 which resolves the GDS scheduler lifecycle wiring gap (GMP-02) that means background GDS jobs never actually start.
