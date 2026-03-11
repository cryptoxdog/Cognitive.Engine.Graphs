# Task: Extend a Contract File

```
task: Extend contract "<contract_name>"
tier: 3
contracts_to_read:
  - The contract file being extended
  - docs/contracts/BANNED_PATTERNS.md (for anti-pattern format)
```

## Preconditions
- `make test` passes
- Extension is ADDITIVE (new sections, new entries)
- No existing content is removed or renamed

## Steps
1. Read the current contract file completely
2. Add new content at the END of the relevant section
   - Follow existing formatting exactly
   - Include both WRONG and RIGHT examples
   - Include audit finding reference if applicable
3. If adding a new scanner rule to BANNED_PATTERNS.md:
   - Add corresponding check to `tools/audit_engine.py`
   - Add corresponding test to `tests/compliance/`
4. Update `tools/l9_template_manifest.yaml` SHA-256 if needed
5. Run `make agent-check`

## Acceptance Criteria
- [ ] No existing content removed or renamed
- [ ] New content follows existing format
- [ ] Examples include WRONG and RIGHT patterns
- [ ] Audit scanner updated if new rule added
- [ ] Compliance test added if new rule added
- [ ] `make agent-check` exits 0

## Anti-Patterns
- DO NOT rename existing sections
- DO NOT change existing field names or signatures
- DO NOT remove anti-pattern examples
- DO NOT add content without WRONG/RIGHT examples
