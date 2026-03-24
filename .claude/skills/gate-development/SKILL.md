---
name: new-gate
description: Add a new gate type to the CEG engine
---

# New Gate Type Development

## Steps

1. **Read existing gates**: Open `engine/gates/types/all_gates.py` to understand the BaseGate pattern
2. **Read the GateType enum**: Open `engine/config/schema.py` and find the GateType StrEnum
3. **Create the gate class** in `engine/gates/types/all_gates.py`:
   - Extend `BaseGate`
   - Implement `compile_where(self, spec: GateSpec, domain_spec: DomainSpec) -> str`
   - ALL field references MUST pass `sanitize_label()` (Contract 9)
   - Handle `null_behavior` (pass/fail) per Contract 14
   - Handle `invertible` and `match_directions` per Contract 15
4. **Register the gate type** in `GateType` StrEnum in `engine/config/schema.py`
5. **Write tests** in `tests/unit/`:
   - Test compilation produces valid Cypher
   - Test null_behavior: pass wraps in IS NULL OR
   - Test null_behavior: fail rejects null candidates
   - Test with sanitize_label edge cases
6. **Run `make test-unit` and `make lint`**

## Template

```python
class NewGate(BaseGate):
    """Description of what this gate filters."""
    
    def compile_where(self, spec: GateSpec, domain_spec: DomainSpec) -> str:
        field = sanitize_label(spec.candidateprop)
        param_name = f"${spec.parametername}"
        return f"candidate.{field} >= {param_name}"
```
