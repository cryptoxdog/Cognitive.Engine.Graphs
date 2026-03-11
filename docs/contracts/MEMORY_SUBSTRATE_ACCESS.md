<!-- L9_META
l9_schema: 1
origin: l9-template
engine: graph
layer: [docs, contracts]
tags: [L9_TEMPLATE, contracts]
owner: platform
status: active
/L9_META -->

**Closes:** Agents bypassing the LangGraph DAG pipeline

```markdown
<!-- L9_TEMPLATE: true -->
# L9 Memory Substrate Access Contract

## Rule
All data entering the memory substrate goes through `ingest_packet()`.
No node writes directly to `packetstore`, `memory_embeddings`, or any other
substrate table. The LangGraph DAG handles validation, embedding, graph sync,
insight extraction, and checkpointing.

## The Only Write Path
```python
from l9.memory.ingestion import ingest_packet

await ingest_packet(PacketEnvelopeIn(
    packet_type="enrichment_result",
    payload={"entity_id": "abc-123", "enriched_fields": {...}},
    tenant=TenantContext(actor="enrichment-engine", org_id="acme"),
))
```


## What ingest_packet() Does (you don't)

1. `intake_node` — parse, validate
2. `reasoning_node` — add reasoning block if applicable
3. `memory_write_node` — INSERT to `packetstore`
4. `graph_sync_node` — sync to Neo4j if relevant
5. `semantic_embed_node` — generate embedding → `memory_embeddings`
6. `checkpoint_node` — save DAG state
7. `extract_insights_node` — extract facts/entities
8. `store_insights_node` — persist extracted insights
9. `world_model_trigger_node` — update world model
10. `analogical_enrichment_node` — cross-domain analogies (optional)

## The Only Read Path

```python
from l9.memory.retrieval import PipelineRouter

results = await PipelineRouter.retrieve(
    query="HDPE contamination tolerance for Houston facilities",
    tenant_id="acme",
    limit=10,
)
```


## BANNED

```python
# ❌ Direct SQL to packetstore
await pg.execute("INSERT INTO packetstore ...")

# ❌ Direct embedding writes
await pg.execute("INSERT INTO memory_embeddings ...")

# ❌ Bypassing PipelineRouter for reads
await pg.execute("SELECT * FROM packetstore WHERE ...")

# ❌ Creating custom DAG nodes
# Only the substrate team modifies the LangGraph DAG
```


## PostgreSQL Tables (for reference — never write directly)

| Table | Purpose |
| :-- | :-- |
| `packetstore` | Central event log |
| `memory_embeddings` | Vector store (pgvector HNSW) |
| `knowledge_facts` | S-P-O triples |
| `graph_checkpoints` | Agent state snapshots |
| `reasoning_traces` | Reasoning chains |
| `reflection_store` | Lessons learned |
| `tool_audit_log` | Tool execution audit |
| `world_model_entities` | World model entities |
| `tasks` | Task tracking |

```
