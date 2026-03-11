<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts, cypher]
owner: platform
status: active
/L9_META -->

<!-- L9_TEMPLATE: true -->
# L9 Cypher Safety Contract

## Rule 1: Labels and Relationship Types → sanitize_label()
Labels/types CANNOT be parameterized in Neo4j. They MUST be validated via
`sanitize_label()` before f-string interpolation.

```python
# ✅ CORRECT
label = sanitize_label(spec.target_node)
cypher = f"MATCH (n:{label})"

# ❌ WRONG — unsanitized
cypher = f"MATCH (n:{spec.target_node})"
```


## Rule 2: ALL Values → Cypher Parameters (\$var)

Every value that comes from user input, payload, or domain spec properties
MUST use Cypher parameterization. This includes LIMIT, SKIP, property values.

```python
# ✅ CORRECT
cypher = "MATCH (n:Facility) RETURN n LIMIT $limit"
parameters = {"limit": top_n}

# ❌ WRONG — f-string interpolation of value
cypher = f"MATCH (n:Facility) RETURN n LIMIT {top_n}"
```


## Rule 3: No eval(), no exec(), no compile()

These functions are BANNED in all engine code. No exceptions. No "safe" wrappers.

```python
# ❌ BANNED — even with restricted builtins
result = eval(expression, {"__builtins__": {}}, safe_vars)

# ✅ CORRECT — use explicit computation
if expression_type == "multiply":
    result = a * b
elif expression_type == "convert":
    result = value * conversion_factor
```

For derived parameter computation, use a whitelist dispatch table:

```python
OPERATORS: dict[str, Callable] = {
    "multiply": operator.mul,
    "divide": operator.truediv,
    "add": operator.add,
    "min": min,
    "max": max,
}
```


## Rule 4: Query Dict Keys

When building Cypher from query parameters, keys must be validated:

```python
ALLOWED_QUERY_KEYS = {"lat", "lon", "mfi", "capacity", "material_type", ...}
for key in query:
    if key not in ALLOWED_QUERY_KEYS:
        raise ValueError(f"Unknown query key: {key!r}")
```


## Enforcement

- `tools/audit_engine.py` regex rule `SEC_LABEL_SANITIZATION_REQUIRED`
- `tools/audit_engine.py` pattern rule for `eval(`, `exec(`, `compile(`
- Pre-commit hook scans for unsafe patterns
- CI compliance.yml blocks PRs with violations

```
