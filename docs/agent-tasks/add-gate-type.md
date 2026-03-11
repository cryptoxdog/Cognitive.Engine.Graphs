# Task: Add a New Gate Type

```
task: Add gate type "<gate_name>"
tier: 2
contracts_to_read:
  - docs/contracts/FIELD_NAMES.md
  - docs/contracts/METHOD_SIGNATURES.md
  - docs/contracts/CYPHER_SAFETY.md
  - docs/contracts/HANDLER_PAYLOADS.md
```

## Preconditions
- `make test` passes (green baseline)
- Gate type is defined in domain spec YAML
- Gate type does NOT already exist in `engine/gates/types/`

## Steps
1. Create `engine/gates/types/<gate_name>.py`
   - Class inherits from `BaseGate`
   - Constructor signature matches METHOD_SIGNATURES.md
   - All field names snake_case per FIELD_NAMES.md
2. Register in `engine/gates/registry.py`
   - Add to `GATE_REGISTRY` dict
   - Import must resolve (Rule 2)
3. Implement `compile_cypher(self, params) -> str`
   - All values parameterized (Rule 4)
   - All labels sanitized via `sanitize_label()` (Rule 4)
   - NULL behavior defined per gate spec
4. Add tests in `tests/unit/test_gate_<gate_name>.py`
   - Happy path: gate compiles valid Cypher
   - NULL input: gate respects null_behavior setting
   - Invalid input: gate raises ValidationError
   - Cypher injection attempt: gate sanitizes/rejects
5. Update domain spec YAML if needed
6. Run `make agent-check` — ALL checks pass

## Acceptance Criteria
- [ ] Gate class exists with correct constructor signature
- [ ] Gate registered in registry
- [ ] Cypher output is parameterized (zero f-string values)
- [ ] 4+ tests pass (happy, null, invalid, injection)
- [ ] `make agent-check` exits 0

## Anti-Patterns (from Audit History)
- DO NOT use flatcase field names (caused C-1 to C-5)
- DO NOT use eval() for parameter computation (caused C-6, C-7)
- DO NOT f-string interpolate LIMIT/SKIP values (caused C-8)
- DO NOT use str() on lists for Cypher (caused GDS Louvain bug)
- DO NOT forget to create `__init__.py` for new packages
