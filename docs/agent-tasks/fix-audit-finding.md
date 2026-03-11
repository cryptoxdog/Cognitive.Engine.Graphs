# Task: Fix Audit Finding

```
task: Fix audit finding "<finding_id>"
tier: 1
contracts_to_read:
  - (determined by finding's rule number)
```

## Preconditions
- Run `python tools/audit_engine.py` — note exact finding ID and location
- Read the rule number from the finding (e.g., C-1 → Rule 1)
- Read the corresponding contract file

## Steps
1. Locate the exact file:line from audit output
2. Read the contract that governs this pattern
3. Fix the violation — use the "RIGHT" pattern from the contract, not invention
4. Run `python tools/audit_engine.py` — finding must disappear
5. Run `make test` — no regressions
6. Run `make agent-check` — full green

## Acceptance Criteria
- [ ] Specific finding no longer appears in audit output
- [ ] No NEW findings introduced
- [ ] All existing tests still pass
- [ ] `make agent-check` exits 0

## Anti-Patterns
- DO NOT "fix" by deleting the file containing the violation
- DO NOT suppress the finding by adding exclusions
- DO NOT change the audit rule to match the bad code
