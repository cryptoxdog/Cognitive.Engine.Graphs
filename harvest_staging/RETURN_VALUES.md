<!-- L9_TEMPLATE: true -->
# L9 Return Value Contract

## Rule
ALL handler returns are dicts that the chassis wraps in the outbound envelope.
The engine NEVER constructs the full envelope — only the `data` payload.

## Success Returns
Every success return MUST include a `status` field (redundant but explicit):
```python
return {
    "status": "success",
    # ... action-specific fields from HANDLER_PAYLOADS.md
}
```


## Error Propagation

Handlers raise exceptions. They do NOT return error dicts.
The chassis catches exceptions and constructs the error envelope.

```python
# ✅ CORRECT — raise, let chassis handle
async def handle_match(tenant: str, payload: dict) -> dict:
    if not payload.get("query"):
        raise ValueError("Missing required field: query")

# ❌ WRONG — returning error dict
async def handle_match(tenant: str, payload: dict) -> dict:
    if not payload.get("query"):
        return {"status": "error", "message": "Missing query"}  # BANNED
```


## Chassis Wrapping (for reference — engine does NOT do this)

```python
# The chassis produces:
{
    "status": "success",        # or "failed"
    "action": "match",
    "tenant": "plasticos",
    "data": { ... },            # ← THIS is what the engine returns
    "meta": {
        "trace_id": "abc-123",
        "execution_ms": 45.2,
        "version": "1.1.0",
        "timestamp": "2026-03-01T20:00:00Z",
    }
}
```

```

