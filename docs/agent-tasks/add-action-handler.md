# Task: Add a New Engine Action Handler

```
task: Add action handler "<action_name>"
tier: 2
contracts_to_read:
  - docs/contracts/HANDLER_PAYLOADS.md
  - docs/contracts/FIELD_NAMES.md
  - docs/contracts/RETURN_VALUES.md
  - docs/contracts/METHOD_SIGNATURES.md
```

## Preconditions
- `make test` passes
- Action name is registered in copier.yml `engine_actions`
- Action does NOT already exist in `engine/handlers.py`

## Steps
1. Define Pydantic payload model in `engine/handlers.py` or `engine/models/`
   - All fields snake_case
   - No aliases
2. Add async handler function: `async def handle_<action>(tenant: str, payload: dict) -> dict`
   - First line: validate payload with Pydantic model
   - Never access `payload[key]` directly after validation
   - Return standard shape: `{"status": "success", "data": {...}, "meta": {...}}`
3. Register handler: `register_handler("<action>", handle_<action>)`
4. Add tests in `tests/unit/test_handlers.py`
   - Valid payload: returns success
   - Invalid payload: raises ValidationError
   - Missing required field: raises ValidationError
5. Run `make agent-check`

## Acceptance Criteria
- [ ] Pydantic model exists with snake_case fields
- [ ] Handler validates payload as first line
- [ ] Handler registered with chassis
- [ ] Return value matches RETURN_VALUES.md shape
- [ ] 3+ tests pass
- [ ] `make agent-check` exits 0
