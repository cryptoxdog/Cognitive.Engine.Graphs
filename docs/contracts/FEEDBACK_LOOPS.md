
**Closes:** Agents not knowing what the 26 inter-service feedback loops actually carry

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Constellation Feedback Loop Contract

## Rule
Every feedback loop between services has a defined trigger, payload shape,
packet_type, and destination action. Agents implementing any service MUST
implement their inbound loops and fire their outbound loops.

## The 26 Loops

### ENRICH → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 1 | SCORE | Enrichment complete | `enrichment_result` | `score` | `entity_id`, `enriched_fields`, `confidence` |
| 2 | GRAPH | Enrichment complete | `graph_sync` | `sync` | `entity_type`, `batch` (enriched entities) |
| 3 | FORECAST | Enrichment complete | `enrichment_result` | `reforecast` | `entity_id`, `confidence`, `fields_filled` |
| 4 | HEALTH | Enrichment complete | `enrichment_result` | `update_health` | `entity_id`, `field_confidences` |

### SCORE → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 5 | ROUTE | Score computed | `score_record` | `route` | `entity_id`, `composite_score`, `dimension_scores` |
| 6 | FORECAST | Score computed | `score_record` | `update_feature` | `entity_id`, `score_velocity`, `dimension_scores` |
| 7 | ENRICH | Missing fields detected | `enrichment_request` | `enrich` | `entity_id`, `missing_fields`, `priority` |

### ROUTE → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 8 | GRAPH | Outcome recorded | `graph_sync` | `sync_outcome` | `entity_id`, `outcome`, `edge_type: "RESULTED_IN"` |
| 9 | FORECAST | Routing velocity | `routing_decision` | `update_feature` | `entity_id`, `routing_velocity`, `rep_id` |
| 10 | SIGNAL | Route event | `signal_event` | `ingest` | `entity_id`, `signal_type: "routed"`, `assigned_to` |

### FORECAST → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 11 | ENRICH | High-risk deal + missing fields | `enrichment_request` | `enrich` | `entity_id`, `missing_fields`, `risk_score` |
| 12 | ROUTE | Capacity rebalance needed | `routing_decision` | `rebalance` | `segment`, `capacity_recommendation` |

### SIGNAL → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 13 | SCORE | New signal | `signal_event` | `update_score` | `entity_id`, `engagement_score`, `intent_score` |
| 14 | FORECAST | Signal velocity change | `signal_event` | `update_feature` | `entity_id`, `signal_velocity`, `days_since_last` |
| 15 | ENRICH | New entity from signal | `enrichment_request` | `enrich` | `entity_id`, `entity_type`, `source` |
| 16 | GRAPH | Transaction signal | `graph_sync` | `sync_signal` | `entity_id`, `signal_type`, `edge_data` |

### HEALTH → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 17 | ENRICH | Stale/low-confidence entity | `enrichment_request` | `enrich` | `entity_id`, `stale_fields`, `health_score` |
| 18 | SCORE | Health gates confidence | `health_assessment` | `gate_confidence` | `entity_id`, `health_score` |
| 19 | FORECAST | AI readiness score | `health_assessment` | `gate_readiness` | `crm_health_score`, `field_health` |

### HANDOFF → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 20 | GRAPH | Transition outcome | `graph_sync` | `sync_outcome` | `deal_id`, `outcome`, `edge_type: "TRANSITIONED"` |
| 21 | ROUTE | Rep performance data | `routing_decision` | `update_rep_performance` | `rep_id`, `handoff_outcome` |
| 22 | SIGNAL | Transition event | `signal_event` | `ingest` | `deal_id`, `signal_type: "handoff"`, `transition_type` |
| 23 | FORECAST | Post-handoff update | `forecast_snapshot` | `update_deal` | `deal_id`, `outcome`, `new_owner` |

### GRAPH → (outbound)
| # | To | Trigger | packet_type | Action | Payload Keys |
|---|-----|---------|-------------|--------|-------------|
| 24 | SCORE | Graph affinity computed | `graph_match` | `update_score` | `entity_id`, `graph_affinity`, `community_id` |
| 25 | ROUTE | Match rankings | `graph_match` | `inform_routing` | `entity_id`, `match_rank`, `community_win_rate` |
| 26 | FORECAST | Community signals | `graph_match` | `update_feature` | `entity_id`, `community_id`, `community_win_rate` |

## Implementation Rule
When building a service, check this table for:
1. **Outbound loops**: your service MUST fire these packets on the listed triggers
2. **Inbound loops**: your service MUST handle these action types from other services
```


