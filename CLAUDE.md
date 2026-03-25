<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [agent-rules]
tags: [L9_TEMPLATE, agent-rules, claude]
owner: platform
status: active
/L9_META -->

# CLAUDE.md — L9 Graph Cognitive Engine

@AGENTS.md

## Design Principles

1. **Domain spec is the single source of truth** — all behavior flows from YAML. No hardcoded business logic.
2. **Gate-then-score in Cypher, not Python** — matching is a single Cypher query. No post-filtering.
3. **Engine owns logic, chassis owns HTTP** — handlers receive `(tenant, payload)` → `dict`.
4. **Additive by default** — new capabilities as new files. Feature flags control activation.
5. **Explicit over implicit** — managed state (`EngineState`), bounded caches (`TTLCache`), validated inputs, bounded outputs ([0, 1]).
6. **Mechanism/policy separation** — engine proves mechanisms via tests. Operator activates via flags.

## Code Style Examples

```python
# ✅ GOOD — sanitized label, parameterized values, explicit types
from engine.utils.security import sanitize_label

async def query_candidates(driver: GraphDriver, spec: DomainSpec) -> list[dict[str, Any]]:
    label = sanitize_label(spec.targetnode)
    cypher = f"MATCH (n:{label}) WHERE n.active = $active RETURN n LIMIT $limit"
    return await driver.execute_query(cypher, {"active": True, "limit": settings.max_results})

# 🚫 BAD — unsanitized label, hardcoded limit, no type hints
async def query_candidates(driver, spec):
    cypher = f"MATCH (n:{spec.targetnode}) WHERE n.active = true RETURN n LIMIT 25"
    return await driver.execute_query(cypher)
```

```python
# ✅ GOOD — exception message in variable, explicit union, feature-flagged
def validate_weights(weights: dict[str, float] | None = None) -> None:
    if not settings.score_clamp_enabled:
        return
    if weights and sum(weights.values()) > 1.0:
        msg = f"Weight sum {sum(weights.values()):.4f} exceeds 1.0 ceiling"
        raise ValidationError(msg)

# 🚫 BAD — f-string in raise, implicit Optional, no flag gate
def validate_weights(weights: dict = None):
    if weights and sum(weights.values()) > 1.0:
        raise ValueError(f"Weight sum {sum(weights.values())} too high")
```

```python
# ✅ GOOD — gate type extends BaseGate, registered in enum
class ProximityGate(BaseGate):
    """Gate that filters by graph distance."""
    def compile_where(self, spec: GateSpec, domain: DomainSpec) -> str:
        field = sanitize_label(spec.candidateprop)
        return f"candidate.{field} <= $max_distance"

# 🚫 BAD — standalone function, no BaseGate, no sanitization
def proximity_gate(spec, domain):
    return f"candidate.{spec.candidateprop} <= {spec.threshold}"
```

## Boundaries

### ✅ Always
- Check the **Capability Registry** before building (see `.claude/rules/capability-registry.md`)
- Run `make lint` before committing
- Gate behavioral changes with feature flags in `engine/config/settings.py`
- Use `sanitize_label()` on all Cypher label interpolation
- Route Neo4j through `GraphDriver.execute_query()` — never raw sessions

### ⚠️ Ask Before
- Creating new top-level directories
- Modifying handler signatures in `engine/handlers.py`
- Changing `engine/config/schema.py` (affects all domain specs)
- Adding new action handlers
- Architectural changes to boot lifecycle

### 🚫 Never
- Import FastAPI/Starlette/uvicorn in `engine/`
- Use `eval()`, `exec()`, `pickle.load()`
- Interpolate values (not labels) into Cypher — use `$params`
- Log PII values
- Create unbounded caches
- Redefine PacketEnvelope, TenantContext, or ExecuteRequest

## Imports

```python
@docs/L9_Platform_Architecture.md
@docs/L9_AI_Constellation_Infrastructure_Reference.md
@docs/SEL4_UPGRADES.md
```

## References

Detailed reference material loads automatically from `.claude/rules/` when you edit relevant files:
- **Contracts** → `.claude/rules/contracts.md` (all 24 contracts)
- **Feature Flags** → `.claude/rules/feature-flags.md`
- **Subsystems** → `.claude/rules/subsystems.md` (directory structure, handler registry, dependency map)
- **Capability Registry** → `.claude/rules/capability-registry.md` (18 existing capabilities)
- **Code Routing** → `.claude/rules/routing.md` (where to put code)
- **System State** → `.claude/rules/system-state.md` (open PRs, dormant subsystems)
