# GMP v3.2.0 — ONE-PAGE QUICK REFERENCE

## THE 7 PHASES (0-6, ALWAYS IN THIS ORDER)

### Phase 0: PLANNING (5 min planning, 0 min coding)

- [ ] Understand the problem
- [ ] Read target files (no changes)
- [ ] Create TODO list with IDs
- [ ] Document forbidden areas
- [ ] **Output:** Locked TODO plan

### Phase 1: BASELINE (2 min read-only)

- [ ] Confirm all assumptions
- [ ] Check baseline state
- [ ] **FAIL RULE:** If any assumption fails → STOP, re-run Phase 0
- [ ] **Output:** Baseline confirmed

### Phase 2: IMPLEMENTATION (10-30 min coding)

- [ ] Make surgical changes only
- [ ] No refactoring outside plan
- [ ] Execute each TODO item precisely
- [ ] **Output:** Changes complete

### Phase 3: ENFORCEMENT (10-20 min)

- [ ] Add assertions/guards
- [ ] Add fail-fast conditions
- [ ] Improve error messages
- [ ] Document "why" for future devs
- [ ] **Output:** Guards in place

### Phase 4: VALIDATION (10 min testing)

- [ ] Re-read Phase 0 plan
- [ ] Run negative tests
- [ ] Run regression tests
- [ ] **FAIL RULE:** If test fails → STOP, fix it, re-run Phase 4
- [ ] **Output:** Validation passed

### Phase 5: RECURSION (5 min verification)

- [ ] Verify no scope drift
- [ ] Check only TODO-listed files modified
- [ ] Confirm L9 invariants preserved
- [ ] **FAIL RULE:** If drift found → STOP, fix, re-run Phase 5
- [ ] **Output:** Scope verified

### Phase 6: FINALIZATION (5 min evidence)

- [ ] Generate evidence report
- [ ] Map TODO IDs to changes
- [ ] Write final declaration
- [ ] **Output:** System ready, report complete

---

## CRITICAL RULES (MANDATORY)

```
✓ PLAN BEFORE CODING (Phase 0)
✓ VERIFY ASSUMPTIONS (Phase 1)
✓ MATCH PLAN EXACTLY (Phase 2)
✓ ADD GUARDS (Phase 3)
✓ VALIDATE EVERYTHING (Phase 4)
✓ CHECK FOR DRIFT (Phase 5)
✓ DOCUMENT EVIDENCE (Phase 6)
✓ NO SILENT CHANGES
✓ STOP ON FIRST FAILURE
✓ ALL 7 PHASES REQUIRED (0-6)
```

---

## DECISION TREE

```
Does assumption fail in Phase 1?
├─ YES → STOP. Re-run Phase 0.
└─ NO → Continue to Phase 2

Does implementation deviate from plan?
├─ YES → STOP. Revert. Re-run Phase 2.
└─ NO → Continue to Phase 3

Does test fail in Phase 4?
├─ YES → STOP. Fix issue. Re-run Phase 4.
└─ NO → Continue to Phase 5

Does Phase 5 find scope drift?
├─ YES → STOP. Fix. Re-run Phase 5.
└─ NO → Continue to Phase 6
```

---

## DEFINITION OF DONE (ALL 10 MUST BE TRUE)

- [ ] Phase 0 plan created and locked
- [ ] Phase 1 baseline confirmed (all assumptions ✓)
- [ ] Phase 2 implementation complete (matches plan)
- [ ] Phase 3 enforcement added (guards + fail-fast)
- [ ] Phase 4 validation complete (all tests pass)
- [ ] Phase 5 recursive verification complete (no drift)
- [ ] Phase 6 finalization complete (evidence report)
- [ ] All checklists passed (100%)
- [ ] No further changes needed
- [ ] System is ready for deployment

**If ALL 10 are true → Output FINAL REPORT**

---

## COMMON MISTAKES (AVOID THESE)

| ❌ WRONG                  | ✅ RIGHT                        |
| ------------------------- | ------------------------------- |
| Skip Phase 0              | Always create locked plan first |
| Code without planning     | Plan 5 min, code 20 min         |
| Ignore failed assumptions | STOP, re-plan (Phase 0)         |
| Refactor beyond plan      | Surgical changes only           |
| Keep coding after failure | STOP, fix, re-run phase         |
| Skip Phase 4 validation   | All tests are mandatory         |
| Silent changes            | Document everything             |
| Skip Phase 5 verification | Always check for drift          |

---

## CONTEXT PROFILES (CHOOSE ONE)

### Profile 1: Single-File Code Fix

**When:** Bug in one file (NameError, TypeError, logic error)

```
MISSION OBJECTIVE:
Fix: [Error: e.g., "NameError: name 'settings' undefined"]
File: [Path: /opt/l9/api/server.py]
Lines: [XXX-YYY]
Root Cause: [Why it's broken]
```

### Profile 2: Multi-File Refactoring

**When:** Changes across 2+ files

```
MISSION OBJECTIVE:
Refactor: [What's changing]
Scope: [List all files]
Dependency: [file1 → file2 → file3]
Sequence: [Which changes first?]
```

### Profile 3: Infrastructure Fix

**When:** Docker, config, VPS deployment

```
MISSION OBJECTIVE:
Fix: [Problem: e.g., "Dockerfile build fails"]
System: [Docker / Caddy / PostgreSQL]
Symptom: [Error message]
Root Cause: [Why]
Rollback: [How to undo if needed]
```

### Profile 4: API/Dependency Management

**When:** Adding libraries, updating imports

```
MISSION OBJECTIVE:
Update: [Dependency or API change]
Reason: [Why needed]
Scope: [Which modules affected]
Dependency Map: [What calls what]
```

---

## PHASE 0 TEMPLATE (MINIMAL)

```markdown
## PHASE 0 PLAN (LOCKED)

**Problem:** [Exact description with error message]
**Root Cause:** [Why it happens]
**Solution:** [How to fix in plain language]

### Files to Modify:

- [ ] /path/to/file.py (lines XXX-YYY, function name_here)

### Forbidden Areas:

- [ ] [Specific things that MUST NOT change]

### TODO Items (In Order):

1. [ ] T-001: [Exact change, with line numbers]
   - Verification: [How to confirm it worked]
2. [ ] T-002: [Exact change, with line numbers]
   - Verification: [How to confirm it worked]

### Risks:

- [Risk A]: [Mitigation]
```

---

## PHASE 1 BASELINE TEMPLATE

```markdown
## BASELINE CHECKLIST

[ ] Assumption 1: [Statement] - Expected: [Description] - Found: [Actual from code] - Status: ✓ PASS / ❌ FAIL

[ ] Assumption 2: [Statement] - Expected: [Description] - Found: [Actual from code] - Status: ✓ PASS / ❌ FAIL
```

---

## FINAL REPORT CHECKLIST

After all phases complete:

```
✓ EXECUTION REPORT
- Task: [Brief description]
- Status: COMPLETE
- Phases: 0, 1, 2, 3, 4, 5, 6 (all executed)
- Files Modified: [List]
- Changes Made: [Summary]
- Tests: All passed ✓
- Ready for deployment: YES ✓

## FINAL DECLARATION
All phases (0–6) complete.
No assumptions. No drift.
Implementation matches locked Phase 0 plan exactly.
System is ready for deployment.
```

---

## WHEN STUCK

| Problem                     | Solution                                       |
| --------------------------- | ---------------------------------------------- |
| Don't know what to change   | Re-read Phase 0 plan                           |
| Assumption seems wrong      | STOP. Re-run Phase 0 completely                |
| Want to add something extra | Document it. Re-run Phase 0 for approval       |
| Test is failing             | Fix it. Re-run ENTIRE Phase 4                  |
| Scope drift detected        | Fix it. Re-run Phase 5                         |
| Not sure if you're done     | Check Definition of Done (all 10 must be true) |

---

**Remember:** Plan > Code > Verify > Lock. No exceptions. No shortcuts. Determinism guaranteed.

**Version:** 3.2.0 | **Last Updated:** 2026-01-18 | **Status:** Production Ready (L9 Canonical)
