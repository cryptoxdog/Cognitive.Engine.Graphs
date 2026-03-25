---
name: new-scoring
description: Add a new scoring computation to the CEG engine
---

# New Scoring Computation Development

## Steps

1. **Read existing computations**: Open `engine/scoring/assembler.py` — study the `_compile_*` methods
2. **Read ComputationType enum**: In `engine/config/schema.py`
3. **Add the computation method** in `ScoringAssembler`:
   - Method name: `_compile_{computationname}(self, dim: ScoringDimensionSpec) -> str`
   - Return a Cypher expression string
   - Expression MUST be wrapped in `_clamp_expression()` (Contract 22)
   - Reference only declared fields via `sanitize_label()` (Contract 9)
4. **Register** in `ComputationType` StrEnum
5. **Write tests** verifying:
   - Output is valid Cypher
   - Clamped to [0, 1] at boundaries (0.0 and 1.0)
   - Handles missing/null candidate properties correctly
6. **Run `make test-unit` and `make lint`**

## Clamping Rule

Every scoring expression MUST be clamped. Use the existing helper:
```python
expr = f"candidate.{field} / $max_value"
return self._clamp_expression(expr)  # Wraps in CASE WHEN > 1.0 THEN 1.0 ...
```

## Weight Ceiling

If adding a new default weight to Settings, the total sum MUST remain ≤ 1.0.
Current sum: 0.85 (structural 0.30 + geo 0.25 + reinforcement 0.20 + freshness 0.10).
Reduce existing defaults to make room.
