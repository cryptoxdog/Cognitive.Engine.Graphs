---
paths:
  - "engine/**/*.py"
---
# Subsystems & Handler Registry

## Action Handlers (engine/handlers.py)
All handlers: `async def handle_*(tenant: str, payload: dict) -> dict`

| Action | Handler | Purpose |
|--------|---------|---------|
| match | handle_match | Gate-then-score graph matching |
| sync | handle_sync | Batch entity ingestion (UNWIND MERGE) |
| admin | handle_admin | Domain management, GDS trigger, calibration |
| outcomes | handle_outcomes | Outcome feedback for score tuning |
| resolve | handle_resolve | Entity resolution / deduplication |
| health | handle_health | Field-level health assessment + readiness |
| healthcheck | handle_healthcheck | Alias for health |
| enrich | handle_enrich | ROI-based re-enrichment triggering |

## Admin Subactions (payload["subaction"])
| Subaction | Purpose |
|-----------|---------|
| list_domains | List loaded domain specs |
| get_domain | Return specific domain spec |
| init_schema | Initialize Neo4j schema |
| trigger_gds | Manual GDS algorithm run |
| calibration_run | Score calibration vs expected ranges |
| score_feedback | Compute weight adjustment proposal |
| apply_weight_proposal | Apply proposed weight change |

## Dependency Map
```
handlers.py (registers all 8 actions)
  ├── config/ → schema.py → settings.py
  ├── gates/compiler.py → gates/types/ → null_semantics.py
  ├── scoring/assembler.py → calibration.py, confidence.py, pareto.py
  ├── traversal/assembler.py → resolver.py
  ├── sync/generator.py
  ├── compliance/engine.py → pii.py, prohibited_factors.py
  ├── graph/driver.py (ALL Neo4j access — circuit breaker + timeout)
  ├── health/ → config, graph
  ├── intake/ → config, schema
  ├── personas/ (self-contained)
  ├── causal/ → schema, utils/security
  ├── feedback/ → schema, graph
  ├── resolution/ → schema, graph
  └── kge/ (dormant — kge_enabled=False)
boot.py (lifecycle — plus handlers.py, ONLY files importing chassis)
```

## Domain Spec Sections (engine/config/schema.py)
| Section | Schema Class | Purpose |
|---------|-------------|---------|
| ontology | OntologySpec | Node/edge types, properties |
| match_entities | MatchEntitiesSpec | Source/target definitions |
| query_schema | QuerySchemaSpec | Input parameters |
| traversal | TraversalSpec | Path patterns, hop limits |
| gates | list[GateSpec] | Hard filters (10 types) |
| scoring | ScoringSpec | Soft rank (13 computations) |
| sync | SyncSpec | Ingestion endpoints |
| gds_jobs | GDSSpec | Algorithm scheduling |
| kge | KGESpec | Embedding config |
| compliance | ComplianceSpec | PII, prohibited factors |
| calibration | CalibrationSpec | Expected score ranges |
| causal_edges | list[CausalEdgeSpec] | Causal relationships |
