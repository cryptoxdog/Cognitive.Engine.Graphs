# Task: Fix Log Safety Finding

```
task: Fix log safety finding "<finding_code>"
tier: 1
contracts_to_read:
  - docs/contracts/LOG_SAFETY.md
  - docs/contracts/ERRORHANDLING.md
```

## Steps

### SENSITIVE_LOGGED / CREDENTIAL_PRINT
- Remove the sensitive variable from log/print
- If debugging is needed, log a masked version: `***{last4}`
- Never log: password, token, secret, api_key, ssn, credit_card

### STACK_TRACE_LEAK
- Replace `return {"error": str(e)}` with generic message
- Log the full exception internally with `logger.exception("...")`

## Acceptance
- [ ] Finding gone from audit output
- [ ] No sensitive tokens in any log/print statement
- [ ] `make agent-check` exits 0
