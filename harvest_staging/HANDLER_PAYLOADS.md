<!-- L9_TEMPLATE: true -->
# L9 Handler Payload Contract

## Rule
Every action handler has a FIXED payload schema. Agents must validate
incoming payloads against these schemas before processing.

## match
```python
class MatchPayload(BaseModel):
    query: dict[str, Any]              # Entity attributes to match against
    match_direction: str               # e.g., "buyer_to_seller"
    top_n: int = 10                    # Max candidates to return (1-1000)
    weights: dict[str, float] = {}     # Override scoring dimension weights
    filters: dict[str, Any] = {}       # Additional Cypher filters

class MatchResponse(BaseModel):
    candidates: list[dict[str, Any]]
    query_id: str
    match_direction: str
    total_candidates: int
    execution_time_ms: float
```


## sync

```python
class SyncPayload(BaseModel):
    entity_type: str                   # Must match a sync endpoint path
    batch: list[dict[str, Any]]        # 1-10000 entities per batch

class SyncResponse(BaseModel):
    status: Literal["success"]
    entity_type: str
    synced_count: int
```


## admin

```python
class AdminPayload(BaseModel):
    subaction: Literal["list_domains", "get_domain", "init_schema", "trigger_gds"]
    domain_id: str | None = None       # Required for get_domain, init_schema, trigger_gds
    job_name: str | None = None        # Required for trigger_gds

class AdminResponse(BaseModel):
    # Varies by subaction — always a dict
    pass
```


## Validation Pattern

```python
async def handle_match(tenant: str, payload: dict[str, Any]) -> dict[str, Any]:
    validated = MatchPayload.model_validate(payload)  # Raises ValidationError
    # Use validated.query, validated.match_direction, etc.
```

```

