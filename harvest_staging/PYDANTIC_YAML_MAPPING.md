<!-- L9_TEMPLATE: true -->
# L9 Pydantic ↔ YAML Mapping Contract

## Rule
Pydantic field names are IDENTICAL to YAML keys. snake_case everywhere.
No aliases. No Field(alias=...). No model_config with populate_by_name.

## Example: spec.yaml ↔ DomainSpec

```yaml
# YAML (domains/plasticos_domain_spec.yaml)
domain:
  id: plasticos
  name: PlasticOS
  version: "1.0.0"

match_entities:            # ← snake_case in YAML
  candidate:
    - label: Facility
      match_direction: buyer_to_seller

gates:
  - type: range
    field: mfi_range_min   # ← snake_case
    query_param: mfi       # ← snake_case
    null_behavior: pass    # ← snake_case
```

```python
# Python (engine/config/schema.py)
class DomainSpec(BaseModel):
    domain: DomainMeta
    match_entities: MatchEntitiesSpec   # ← SAME as YAML key
    gates: list[GateSpec]

class GateSpec(BaseModel):
    type: GateType
    field: str
    query_param: str
    null_behavior: str = "fail"         # ← SAME as YAML key
```


## BANNED Patterns

```python
# ❌ No aliases
class GateSpec(BaseModel):
    null_behavior: str = Field(alias="nullBehavior")  # BANNED

# ❌ No flatcase
class DomainSpec(BaseModel):
    matchentities: MatchEntitiesSpec  # BANNED — must be match_entities

# ❌ No camelCase
class DomainSpec(BaseModel):
    matchEntities: MatchEntitiesSpec  # BANNED
```

```

