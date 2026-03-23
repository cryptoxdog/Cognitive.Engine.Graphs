# CURSOR RUNBOOK — L9 GMP + CURSOR INTEGRATION

**Version:** 3.1.0
**Purpose:** Step-by-step execution guide for GMP phases

---

This runbook tells you exactly **which prompt to run in which order**, what Cursor is allowed to modify at each phase, and how to verify completion.

## 1. Artifacts

| Artifact                           | Purpose                              |
| ---------------------------------- | ------------------------------------ |
| `.cursorrules`                     | Workspace governance and phase rules |
| `CURSOR-GOD-PROMPT.md`             | Master orchestrator                  |
| `cursor-phase-0-planning.md`       | Planning                             |
| `cursor-phase-1-baseline.md`       | Baseline verification                |
| `cursor-phase-2-implementation.md` | Implementation                       |
| `cursor-phase-3-enforcement.md`    | Governance enforcement               |
| `cursor-phase-4-validation.md`     | Testing                              |
| `cursor-phase-5-recursion.md`      | Recursive verification               |
| `cursor-phase-6-finalization.md`   | Final evidence                       |
| `governance-reference.md`          | Quick reference                      |

## 2. Typical Flow

### Step 1: Start in GOD MODE

- Load `CURSOR-GOD-PROMPT.md` in Cursor
- Describe your goal (e.g., "Upgrade memory retrieval to hierarchical search")
- GOD prompt routes you to Phase 0

### Step 2: Phase 0 — Planning

- Run `cursor-phase-0-planning.md`
- **Outcome:** TODO PLAN with IDs T-001…T-n
- **Human action:** Review and approve

### Step 3: Phase 1 — Baseline

- Run `cursor-phase-1-baseline.md` with the approved plan
- **Outcome:** Baseline report (READY/BLOCKED)
- **If BLOCKED:** Fix preconditions or adjust TODO PLAN

### Step 4: Phase 2 — Implementation

- Run `cursor-phase-2-implementation.md`
- **Allowed edits:** Only files in TODO PLAN and not protected
- **Outcome:** Implementation report with APPLIED/FAILED TODOs

### Step 5: Phase 3 — Governance

- Run `cursor-phase-3-enforcement.md`
- **Focus:** Governance, audit, observability, approval gates
- **Outcome:** Governance report

### Step 6: Phase 4 — Validation

- Run `cursor-phase-4-validation.md`
- **Outcome:** Validation report (tests, coverage, failures)

### Step 7: Phase 5 — Recursive Verification

- Run `cursor-phase-5-recursion.md`
- **Outcome:** Recursive verification report (invariants, protected systems)

### Step 8: Phase 6 — Finalization

- Run `cursor-phase-6-finalization.md`
- **Outcome:** Evidence report `reports/GMP_Report_{GMP_RUN_ID}.md`

## 3. Allowed Modifications per Phase

| Phase | Allowed Modifications                         | Forbidden           |
| ----- | --------------------------------------------- | ------------------- |
| 0     | `agents/cursor/*`, `.cursorrules`             | Any `*.py`, `*.sql` |
| 1     | `agents/cursor/*` (reports)                   | Any code files      |
| 2     | Files in TODO PLAN (non-protected)            | Protected systems   |
| 3     | `core/governance/**`, `core/observability/**` | Business logic      |
| 4     | `tests/**`, `agents/**`                       | Core runtime code   |
| 5     | `agents/cursor/*`                             | Any code            |
| 6     | `agents/**`, `reports/**`                     | Any code            |

## 4. Verification Checklists

### Phase 0 Checklist

- [ ] TODO PLAN exists
- [ ] No protected files listed
- [ ] Each TODO has: file, operation, anchor, description
- [ ] Dependencies are acyclic

### Phase 1 Checklist

- [ ] All TODOs have READY/BLOCKED status
- [ ] Blocked reasons are clear
- [ ] Baseline report saved

### Phase 2 Checklist

- [ ] Changes only in allowed files
- [ ] Code compiles (`python -m py_compile`)
- [ ] Lint passes (`ruff check`)
- [ ] No new TODOs or placeholders

### Phase 3 Checklist

- [ ] New tools/endpoints have governance
- [ ] Audit hooks added
- [ ] Observability metrics added

### Phase 4 Checklist

- [ ] Tests run completely
- [ ] Results recorded
- [ ] Failures investigated

### Phase 5 Checklist

- [ ] All TODOs verified
- [ ] No protected systems modified
- [ ] No scope drift

### Phase 6 Checklist

- [ ] Evidence report exists
- [ ] All 10 sections present
- [ ] Ends with final declaration

## 5. Error Handling

### If any phase fails:

1. **Do not advance** to the next phase
2. **Fix** the underlying issue
3. **Re-run** the same phase until clean

### Common Issues

| Issue                   | Solution                  |
| ----------------------- | ------------------------- |
| File not found          | Verify path in TODO PLAN  |
| Anchor ambiguous        | Add line number to TODO   |
| Protected file in scope | Remove from TODO PLAN     |
| Test failure            | Fix code or update test   |
| Governance missing      | Add capability definition |

## 6. Quick Commands

```bash
# Validate Python syntax
python -m py_compile path/to/file.py

# Run lint
ruff check path/to/file.py

# Run specific tests
pytest tests/memory/test_retrieval.py -v

# Run all tests
pytest tests/ -v --tb=short
```

## 7. Emergency Procedures

### If GMP goes wrong:

1. **Stop immediately**
2. **Document** what happened in Phase 5 report
3. **Roll back** changes if possible (`git checkout`)
4. **Escalate** to Igor

### If protected file modified:

1. **Immediate stop**
2. **Revert** changes: `git checkout -- <file>`
3. **Report** violation
4. **Revise** TODO PLAN

---

**End CURSOR-RUNBOOK.md**
