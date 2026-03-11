# Task: Fix API Regression Finding

```
task: Fix API regression "<finding_code>"
tier: 2
contracts_to_read:
  - docs/contracts/API_REGRESSION.md
  - docs/contracts/METHODSIGNATURES.md
```

## Steps
1. Read the finding: what changed (class removed, method removed, signature changed)
2. **CLASS_REMOVED:** restore class or add deprecation shim
3. **METHOD_REMOVED:** restore with deprecation warning + alias
4. **SIGNATURE_CHANGED:**
   a. Update `docs/contracts/METHODSIGNATURES.md` with new signature
   b. `grep -rn "ClassName(" engine/ tests/` — find all callers
   c. Update every caller to match
   d. Re-run auditor — finding disappears
5. Run `make agent-check`

## Acceptance
- [ ] Finding gone from audit output
- [ ] METHODSIGNATURES.md updated
- [ ] All callers updated
- [ ] Tests pass
- [ ] `make agent-check` exits 0
