<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [agent-rules]
tags: [L9_TEMPLATE, agent-rules, claude]
owner: platform
status: active
/L9_META -->

# CLAUDE.md — L9 Graph Engine Project Context

## What This Project Is
This is the **Graph Cognitive Engine** for the L9 constellation. It performs gate-then-score graph matching across multi-domain specs (plastics recycling, mortgage brokerage, healthcare referrals, freight matching). The engine plugs into the L9 chassis (FastAPI shell that handles auth/tenant/HTTP) and exposes action handlers (`match`, `sync`, `admin`). The engine NEVER touches HTTP directly.

## Tech Stack
- **Python 3.12+**, async/await throughout
- **Neo4j 5.x** with GDS plugin (Louvain, similarity, pagerank)
- **PostgreSQL + pgvector** for PacketEnvelope persistence
- **Redis** for idempotency caching (chassis-managed)
- **Pydantic v2** for all schemas (domain specs, config, models)
- **pytest + testcontainers-neo4j** for integration testing

## Directory Structure (Do Not Deviate)
```
engine/
  handlers.py              # Chassis bridge (register_all, handle_match, handle_sync, handle_admin)
  config/schema.py         # DomainSpec Pydantic model
  config/loader.py         # YAML domain spec loader
  gates/compiler.py        # Gate → WHERE clause compiler
  gates/types/             # 10 gate type implementations (Range, Threshold, Boolean, etc.)
  scoring/assembler.py     # Scoring → WITH score clause
  traversal/assembler.py   # Traversal → MATCH clauses
  sync/generator.py        # UNWIND MERGE/MATCH SET Cypher generator
  gds/scheduler.py         # APScheduler for GDS jobs (Louvain, co-occurrence, etc.)
  graph/driver.py          # Neo4j AsyncDriver wrapper
  compliance/              # PII + prohibited factors
  packet/
    chassis_contract.py    # inflate_ingress, deflate_egress
    packet_envelope.py     # PacketEnvelope Pydantic model
domains/
  {domain_id}_domain_spec.yaml   # One per vertical (mortgage, plasticos, healthcare, freight)
tests/
  unit/, integration/, compliance/, performance/
```

## Code Style
- **Type hints everywhere**: Function signatures, class attributes, variables where ambiguous.
- **Async by default**: All I/O operations (Neo4j, PostgreSQL, Redis) use `async`/`await`.
- **Pydantic models for data**: Use `BaseModel` (frozen where appropriate) for all structured data.
- **Ruff for formatting**: Run `ruff format .` before committing (Black-compatible 88-char line length).
- **structlog for logging**: JSON output, include `tenant`, `trace_id`, `action` in log context.

## Key Commands
```bash
# Setup
make setup              # Install deps, setup pre-commit hooks, verify Neo4j connection

# Development
make dev                # Start docker-compose (app + Neo4j + Redis + Prometheus + Grafana)
make test               # Run full pytest suite (unit + integration + compliance)
make test-unit          # Unit tests only (gates, scoring, parameter resolution)
make test-integration   # Integration tests with testcontainers-neo4j
make lint               # ruff check + mypy

# Cypher validation
make cypher-lint        # Check all generated Cypher for injection vectors

# GDS operations
make gds-trigger JOB=louvain DOMAIN=plasticos   # Manual GDS job trigger

# Deployment
make build              # Build Docker image
make deploy ENV=staging # Deploy to target environment (Railway/ArgoCD)
```

## Critical Gotchas (Do NOT Do These)
1. **Never import FastAPI in engine code.** The chassis owns HTTP. Engine handlers receive `(tenant, payload)` and return `dict`. No routes, no middleware, no CORS config.

2. **Always sanitize labels before Cypher interpolation.** Use `sanitize_label()` from `engine.handlers` on any label/type from domain specs:
   ```python
   # BAD
   cypher = f"MATCH (n:{spec.targetnode})"
   
   # GOOD
   sanitized = sanitize_label(spec.targetnode)
   cypher = f"MATCH (n:{sanitized})"
   ```

3. **PacketEnvelope is mandatory for persisted events.** Match results, sync events, GDS job outcomes must be wrapped via `inflate_ingress()` / `deflate_egress()` at the chassis boundary. Do NOT return plain dicts from handlers without wrapping.

4. **Tenant resolution is chassis-only.** Do NOT implement `resolve_tenant()` functions in the engine. Do NOT use FastAPI `Depends(resolve_tenant)`. Tenant comes as the first argument to handlers, resolved by chassis.

5. **Gate compilation order matters.** Traversal → Gates → Scoring. The gate WHERE clause depends on entities materialized by traversal. Scoring depends on gates having filtered the candidate set.

6. **GDS jobs must use real Cypher, not stubs.** The scheduler in `engine/gds/scheduler.py` executes actual Neo4j GDS procedures (gds.louvain.write, gds.graph.project). Do NOT mock these in production code.

## File Import Patterns
```python
# Chassis integration (ONLY in engine/handlers.py)
from chassis.router import register_handler

# Domain specs
from engine.config.loader import DomainPackLoader
from engine.config.schema import DomainSpec, GateSpec, ScoringDimension

# Gate compilation
from engine.gates.compiler import GateCompiler
from engine.gates.types import RangeGate, ThresholdGate, BooleanGate

# Scoring
from engine.scoring.assembler import ScoringAssembler

# Sync
from engine.sync.generator import SyncGenerator, SyncStrategy

# GDS
from engine.gds.scheduler import GDSScheduler

# Graph driver
from engine.graph.driver import GraphDriver

# PacketEnvelope
from engine.packet.chassis_contract import inflate_ingress, deflate_egress
from engine.packet.packet_envelope import PacketEnvelope, PacketMetadata
```

## Imports to Reference (Not Duplicate)
@docs/L9_Platform_Architecture.md — Chassis contract, universal envelope, action handler signature  
@docs/L9_AI_Constellation_Infrastructure_Reference.md — PacketEnvelope schema, memory substrate, observability

## Contracts
Read these before writing engine code. Enforced by tools/contract_scanner.py and tools/verify_contracts.py.
- docs/contracts/FIELD_NAMES.md
- docs/contracts/METHOD_SIGNATURES.md
- docs/contracts/CYPHER_SAFETY.md
- docs/contracts/BANNED_PATTERNS.md
- docs/contracts/ERROR_HANDLING.md
- docs/contracts/HANDLER_PAYLOADS.md
- docs/contracts/PYDANTIC_YAML_MAPPING.md
- docs/contracts/DEPENDENCY_INJECTION.md
- docs/contracts/TEST_PATTERNS.md
- docs/contracts/RETURN_VALUES.md
- docs/contracts/PACKET_ENVELOPE_FIELDS.md
- docs/contracts/DELEGATION_PROTOCOL.md
- docs/contracts/PACKET_TYPE_REGISTRY.md
- docs/contracts/DOMAIN_SPEC_VERSIONING.md
- docs/contracts/FEEDBACK_LOOPS.md
- docs/contracts/NODE_REGISTRATION.md
- docs/contracts/ENV_VARS.md
- docs/contracts/OBSERVABILITY.md
- docs/contracts/MEMORY_SUBSTRATE_ACCESS.md
- docs/contracts/SHARED_MODELS.md

## Testing Patterns
- **Unit tests**: Pure functions (gate compilation, scoring math, parameter resolution). No Neo4j.
- **Integration tests**: Full match pipeline with testcontainers-neo4j. Seed sample data, execute match, verify candidates + scores.
