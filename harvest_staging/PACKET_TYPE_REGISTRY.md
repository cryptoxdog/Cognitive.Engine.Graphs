
**Closes:** Agents inventing random packet type strings

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Packet Type Registry

## Rule
`packet_type` is a string enum. New values can be ADDED. Existing values must
NEVER be renamed or removed. Use EXACTLY these strings.

## Current Registry

| packet_type | Surface | Description |
|------------|---------|-------------|
| `api_request` | API | Client request via chassis |
| `api_response` | API | Chassis response |
| `api_error` | API | Error response |
| `memory_write` | Memory | Persisted memory event |
| `memory_read` | Memory | Retrieval request/result |
| `reasoning_trace` | Agent | Agent reasoning chain |
| `tool_call` | Agent | Tool invocation record |
| `tool_result` | Agent | Tool execution result |
| `tool_audit` | Agent | Governance audit record |
| `insight` | Memory | Extracted insight/pattern |
| `consolidation` | Memory | Memory consolidation output |
| `world_model_update` | Memory | World model entity change |
| `identity_fact` | Memory | High-confidence identity fact |
| `graph_sync` | Graph | Batch sync event |
| `graph_match` | Graph | Match query result |
| `gds_job` | Graph | GDS algorithm result |
| `event` | General | Generic system event |
| `message` | General | Chat/conversation turn |
| `schema_proposal` | Schema | Schema evolution proposal |
| `enrichment_request` | Enrichment | Request to enrich entity |
| `enrichment_result` | Enrichment | Enrichment response with confidence |
| `score_record` | Scoring | Score computation result |
| `routing_decision` | Routing | Routing assignment record |
| `signal_event` | Signal | Normalized engagement/intent signal |
| `health_assessment` | Health | Entity/CRM health result |
| `forecast_snapshot` | Forecast | Deal/pipeline forecast |
| `handoff_document` | Handoff | Stage transition document |

## WRONG (agents generate these)
```python
"ENRICHMENT_RESULT"     # WRONG → "enrichment_result" (lowercase)
"enrich_response"       # WRONG → "enrichment_result"
"enrichResult"          # WRONG → "enrichment_result"
"match_result"          # WRONG → "graph_match"
"sync_event"            # WRONG → "graph_sync"
"GRAPH_MATCH"           # WRONG → "graph_match" (lowercase)
```


## Adding a New Packet Type

1. Add to this file
2. Add to `PacketType` enum in `l9/packet/envelope.py`
3. Add validation in `PacketValidator`
4. Update `tools/audit_rules.yaml` if compliance checks apply
```

