<!-- L9_META
l9_schema: 1
origin: engine-specific
engine: graph
layer: [docs]
tags: [roadmap, planning]
owner: engine-team
status: active
/L9_META -->

# L9 Graph Cognitive Engine — Roadmap

## Current Status: MVP Complete

The Graph Cognitive Engine is feature-complete for MVP with:
- 8 action handlers (match, sync, admin, outcomes, resolve, health, healthcheck, enrich)
- 10 gate types for filtering
- 9+ scoring computation types
- Full security hardening (Cypher injection, path traversal, expression sanitization)
- PacketEnvelope protocol for inter-service communication
- Comprehensive test suite

---

## Post-MVP Roadmap

### Phase 1: Memory Substrate Integration

**Priority:** HIGH  
**Source:** Codebase Audit — Noted Gap #1  
**Tracking:** `chassis/actions.py` DEFERRED comment

#### Packet Persistence to PostgreSQL

Currently, PacketEnvelope request/response pairs are created but not persisted. The chassis contains a `DEFERRED` annotation noting this requires memory substrate integration.

**Scope:**
- [ ] PostgreSQL PacketStore schema design
- [ ] `packet_audit_log` table with RLS policies
- [ ] Integration with `chassis/actions.py` to persist packets after handler execution
- [ ] Retention policies and archival strategy
- [ ] Query API for packet retrieval and audit trail

**Dependencies:**
- PostgreSQL instance (or connection to L9 memory substrate)
- PacketStore schema from L9 constellation

---

### Phase 2: Vector Embeddings (pgvector)

**Priority:** MEDIUM  
**Source:** Codebase Audit — Noted Gap #4  
**Tracking:** Architecture docs reference, not implemented

#### pgvector Integration for Semantic Search

The architecture documentation references PostgreSQL + pgvector as the memory substrate for semantic embeddings, but the current implementation relies entirely on Neo4j for graph storage and Redis for caching.

**Scope:**
- [ ] pgvector extension setup in PostgreSQL
- [ ] Embedding generation pipeline for domain entities
- [ ] Hybrid search: graph traversal + vector similarity
- [ ] Integration with KGE (CompoundE3D) scoring dimension
- [ ] Embedding refresh strategy (sync triggers, scheduled jobs)

**Dependencies:**
- PostgreSQL with pgvector extension
- Embedding model selection (OpenAI, local model, etc.)
- Memory substrate service from L9 constellation

---

## Completed Items

### Audit 5-9 Findings (2026-03-02)
- ✅ All CRITICAL infrastructure issues resolved
- ✅ All HIGH security issues resolved
- ✅ All MED defense-in-depth improvements applied
- ✅ Test coverage expanded for security boundaries

### Domain Structure (2026-03-02)
- ✅ Created `domains/plasticos/spec.yaml` for test fixtures
- ✅ Updated `domains/README.md` to document both domain structures

---

## Future Considerations

### Not Currently Planned

1. **Multi-region deployment** — Single-region sufficient for current scale
2. **Real-time streaming** — Batch sync adequate for current use cases
3. **Custom ML models** — Using declarative scoring dimensions instead

---

## Contributing

To propose roadmap items:
1. Open a GitHub issue with `[ROADMAP]` prefix
2. Include: problem statement, proposed solution, dependencies, effort estimate
3. Tag with appropriate priority label
