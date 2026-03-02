<!-- L9_TEMPLATE: true -->
# L9 Error Handling Contract

## Rule 1: No Bare Except
```python
# ❌ BANNED
try:
    result = do_thing()
except:
    pass

# ❌ BANNED — swallowed exception
try:
    result = do_thing()
except Exception:
    logger.error("something went wrong")
    result = None  # silent failure

# ✅ CORRECT — specific exception, re-raise or return error
try:
    result = do_thing()
except ValueError as e:
    logger.error(f"Validation failed: {e}", exc_info=True)
    raise
except neo4j.exceptions.ServiceUnavailable as e:
    logger.error(f"Neo4j unavailable: {e}", exc_info=True)
    raise ConnectionError(f"Graph database unavailable: {e}") from e
```


## Rule 2: Handlers Return Errors, Don't Swallow Them

Action handlers must either:

- Raise an exception (chassis catches it and returns status: "failed")
- Return a dict with explicit error info

They must NEVER return partial/empty results silently.

## Rule 3: Validation Errors Must Raise

Pydantic validators, gate compilation, scoring assembly — if input is invalid,
RAISE immediately. Do not return None, empty string, or default value.

```python
# ❌ WRONG
def compile_gate(self, gate: GateSpec) -> str | None:
    if gate.type not in SUPPORTED_TYPES:
        return None  # silent skip

# ✅ CORRECT
def compile_gate(self, gate: GateSpec) -> str:
    if gate.type not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported gate type: {gate.type!r}")
```


## Rule 4: Log Context

All error logs must include: tenant, action, trace_id (if available).

```python
logger.error(f"Gate compilation failed", extra={
    "tenant": tenant,
    "gate_type": gate.type,
    "match_direction": match_direction,
})
```

```
