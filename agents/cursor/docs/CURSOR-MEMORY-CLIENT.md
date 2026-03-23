# Cursor Memory Client

> **File:** `agents/cursor/cursor_memory_client.py`
> **Server:** C1 Hetzner (`46.62.243.82`)
> **Last Updated:** 2026-02-13
> **RLS Verified:** 2026-02-13 (cursor scope enabled via migration 0033)

---

## Architecture — C1 Memory Stack

```
┌──────────────────────────────────────────────────────────────────────────┐
│  C1 Hetzner (46.62.243.82)                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  PostgreSQL │  │  pgvector   │  │  Neo4j      │  │  Redis      │     │
│  │  :30432     │  │  (embedded) │  │  :30474     │  │  :30379     │     │
│  └──────┬──────┘  └──────┬──────┘  └─────────────┘  └─────────────┘     │
│         │                │                                               │
│         └────────┬───────┘                                               │
│                  ▼                                                       │
│         ┌───────────────┐                                                │
│         │  MCP Memory   │ ← DIRECT ACCESS (port 9002)                   │
│         │  :9002        │                                                │
│         └───────┬───────┘                                                │
└─────────────────│────────────────────────────────────────────────────────┘
                  │ HTTP
                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│  Mac (Local)                                                             │
│  cursor_memory_client.py → mcp_call_tool() → POST /mcp/call             │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

```bash
cd /Users/ib-mac/Projects/L9

# Health check (tests MCP endpoint)
python3 agents/cursor/cursor_memory_client.py health

# Search memory (searches cursor + developer + global scopes)
python3 agents/cursor/cursor_memory_client.py search "governance rules"

# Write to memory (writes to cursor scope by default)
python3 agents/cursor/cursor_memory_client.py write "lesson content" --kind lesson

# Write with explicit scope
python3 agents/cursor/cursor_memory_client.py write "lesson content" --kind lesson --scope cursor

# Get stats
python3 agents/cursor/cursor_memory_client.py stats
```

---

## Environment

```bash
# Required in .env (L9 project root)
MCP_API_KEY_C=<cursor-key>        # Identifies caller as Cursor (caller_id: "C")
MCP_URL=http://46.62.243.82:9002  # Direct to MCP Memory Server (no nginx)
```

---

## Memory Operations Flow

### WRITE — How Content Gets Stored

```
cmd_write("content", kind="lesson")
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. BUILD PACKET                                                  │
│    - Generate daily session UUID (same ID all day)               │
│    - Map kind → duration (lesson=long, note=medium)              │
│    - Set scope="cursor" (Cursor's designated scope)              │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. MCP CALL                                                      │
│    POST http://46.62.243.82:9002/mcp/call                        │
│    {                                                             │
│      "tool_name": "save_memory",                                 │
│      "arguments": {                                              │
│        "content": "...",                                         │
│        "kind": "lesson",                                         │
│        "scope": "cursor",                                        │
│        "duration": "long",                                       │
│        "user_id": "l9-shared",                                   │
│        "tags": [],                                               │
│        "importance": 1.0                                         │
│      }                                                           │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. SERVER PIPELINE (SubstrateDAG)                                │
│    a) Governance context set (RLS: tenant, org, user, role)      │
│    b) Write to `packet_store` table (PostgreSQL)                 │
│    c) Generate embedding → `semantic_memory` (pgvector 1536-dim) │
│    d) Extract facts → `knowledge_facts` table                    │
│    e) Return packet_id + enrichment status                       │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. RESPONSE                                                      │
│    {                                                             │
│      "packet_id": "uuid-here",                                   │
│      "written_tables": ["packet_store", "semantic_memory", ...], │
│      "ingest_time_ms": 350,                                      │
│      "enrichment_status": "success",                             │
│      "tier_used": "full"                                         │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
```

### SEARCH — How Content Gets Retrieved

```
cmd_search("governance rules", limit=10)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. MCP CALL                                                      │
│    POST http://46.62.243.82:9002/mcp/call                        │
│    {                                                             │
│      "tool_name": "search_memory",                               │
│      "arguments": {                                              │
│        "query": "governance rules",                              │
│        "user_id": "l9-shared",                                   │
│        "scopes": ["cursor", "developer", "global"],              │
│        "top_k": 20,                                              │
│        "threshold": 0.0,                                         │
│        "duration": "all"                                         │
│      }                                                           │
│    }                                                             │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. SERVER PROCESSING                                             │
│    a) Governance context set (RLS session variables)             │
│    b) Generate embedding for query (pgvector)                    │
│    c) Vector similarity search in `semantic_memory`              │
│    d) Filter by scope (cursor, developer, global)                │
│    e) Rank by similarity score                                   │
│    f) Return top_k results                                       │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. CLIENT POST-PROCESSING                                        │
│    a) Filter by min_confidence (if specified)                    │
│    b) Sort by: relevance | importance | recency                  │
│    c) Limit to requested count                                   │
│    d) Return results with similarity scores                      │
└─────────────────────────────────────────────────────────────────┘
```

### INJECT — 5-Layer Context Loading

```
cmd_inject("memory substrate work")
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 1: PREFERENCES                                             │
│    search_memory("Igor preferences coding style")                │
│    → Load user preferences for coding patterns                   │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 2: LESSONS                                                 │
│    search_memory("lessons learned {task}")                       │
│    → Load past mistakes and learnings                            │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 3: DOMAIN                                                  │
│    search_memory("{task} patterns architecture")                 │
│    → Load domain-specific context                                │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 4: TEMPORAL                                                │
│    search_memory("session recent {date}")                        │
│    → Load recent session activity                                │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LAYER 5: WARNINGS                                                │
│    search_memory("mistakes errors avoid {task}")                 │
│    → Surface anti-patterns to avoid                              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Write Kinds & Durations

| Kind         | Duration | TTL     | Use For            |
| ------------ | -------- | ------- | ------------------ |
| `preference` | long     | Forever | Igor's preferences |
| `lesson`     | long     | Forever | Lessons learned    |
| `insight`    | long     | Forever | Strategic insights |
| `fact`       | long     | Forever | Knowledge facts    |
| `rule`       | long     | Forever | Governance rules   |
| `error`      | medium   | 90 days | Error patterns     |
| `note`       | medium   | 90 days | General notes      |

---

## Scopes (RLS-Enforced)

| Scope       | Who Can Write     | Who Can Read                     | Use For                      |
| ----------- | ----------------- | -------------------------------- | ---------------------------- |
| `cursor`    | Cursor IDE        | cursor, cursor_user, platform_admin | Cursor-specific memories     |
| `developer` | L, Cursor         | All roles                        | Shared development knowledge |
| `global`    | L, Cursor         | All roles                        | Cross-project knowledge      |
| `agent`     | Emma, other agents| All roles                        | Agent-specific memories      |
| `l-private` | L only            | l9_system, platform_admin        | L's internal operations      |

**Cursor default write scope:** `cursor`
**Cursor search scopes:** `cursor`, `developer`, `global`

---

## Search Options

```bash
--limit N           # Max results (default 10)
--min-confidence X  # 0.0-1.0 similarity threshold
--sort TYPE         # relevance | importance | recency
```

**Examples:**

```bash
# High-confidence results only
python3 agents/cursor/cursor_memory_client.py search "docker" --min-confidence 0.5

# Sort by most recent
python3 agents/cursor/cursor_memory_client.py search "GMP" --sort recency

# Limit to 3 results
python3 agents/cursor/cursor_memory_client.py search "error" --limit 3
```

---

## All 27 Commands

### Core Memory Commands (6)

| Command    | What It Does                         |
| ---------- | ------------------------------------ |
| `health`   | Check MCP endpoint health            |
| `stats`    | Get packet counts, embeddings, facts |
| `search`   | Semantic search with filtering       |
| `write`    | Write packet to memory               |
| `session`  | Show current daily session UUID      |
| `mcp-test` | Round-trip test (write + search)     |

### Session Commands (4)

| Command          | What It Does                           |
| ---------------- | -------------------------------------- |
| `session-close`  | Close session, create embedding anchor |
| `session-resume` | Resume with context from past sessions |
| `resume-for`     | Resume for specific task by similarity |
| `session-diff`   | Compare current session to previous    |

### Context Injection Commands (6)

| Command        | What It Does                                       |
| -------------- | -------------------------------------------------- |
| `inject`       | 5-layer context injection (prefs, lessons, domain) |
| `warn`         | Surface past mistakes relevant to task             |
| `suggest`      | Pattern-based next-step suggestions                |
| `temporal`     | Time-windowed search (24h, 7d, 30d)                |
| `fix-error`    | Find past fixes for an error                       |
| `dedupe-check` | Check if content already exists                    |

### Graph Commands - Neo4j (5)

| Command         | What It Does                 |
| --------------- | ---------------------------- |
| `graph-health`  | Check Neo4j health           |
| `graph-context` | Get context for a domain     |
| `graph-query`   | Run Cypher query             |
| `graph-entity`  | Get entity by type and ID    |
| `graph-rels`    | Get relationships for entity |

### Cache Commands - Redis (6)

| Command             | What It Does                |
| ------------------- | --------------------------- |
| `cache-health`      | Check Redis health          |
| `cache-get`         | Get value by key            |
| `cache-set`         | Set value with optional TTL |
| `cache-session`     | Get current session context |
| `cache-set-session` | Set session context         |
| `cache-sessions`    | List recent sessions        |

---

## Database Schema

### packet_store table (PostgreSQL)

```sql
CREATE TABLE packet_store (
    id UUID PRIMARY KEY,
    user_id VARCHAR(255),
    content TEXT,
    packet_type VARCHAR(50),
    scope VARCHAR(50),           -- cursor, developer, global, agent, l-private
    importance FLOAT,
    timestamp TIMESTAMPTZ,
    session_id UUID,
    envelope JSONB,              -- Full PacketEnvelope v2
    schema_version VARCHAR(20),
    tenant_id UUID,
    org_id UUID
);
```

### semantic_memory table (pgvector)

```sql
CREATE TABLE semantic_memory (
    id UUID PRIMARY KEY,
    packet_id UUID REFERENCES packet_store(id),
    embedding vector(1536),      -- OpenAI ada-002 dimension
    content TEXT,
    scope VARCHAR(50),
    created_at TIMESTAMPTZ,
    tenant_id UUID,
    org_id UUID
);
```

---

## Row-Level Security (RLS)

All memory tables use PostgreSQL Row-Level Security for multi-tenant isolation.

### RLS Credentials (Deterministic UUIDs)

The client uses deterministic UUIDs generated from string identifiers via `uuid5`:

| Identifier       | String Value | UUID                                   |
| ---------------- | ------------ | -------------------------------------- |
| **Tenant**       | `l9`         | `73350468-3158-5d0f-9b8c-9b193d96fc4b` |
| **Organization** | `quantumai`  | `14910cef-fea1-51d7-9a28-05579e6c0c18` |
| **User**         | `l9-shared`  | `2f00c090-3816-51a0-806c-34d32522a070` |

**Source:** `config/rls_config.py`

### How RLS Works

```
cursor_memory_client.py
         │
         ▼
MCP Server (mcp_memory/src/main.py)
         │
         ├─► build_governance_context()
         │     caller_scope = "cursor" (for non-L callers)
         │     allowed_scopes = ["cursor", "developer", "global"]
         │     project_id = "l9-default"
         │
         ▼
memory/substrate_repository.py
         │
         └─► SELECT l9_set_scope(tenant_uuid, org_uuid, user_uuid, role)
                    │
                    ▼
            PostgreSQL: SET LOCAL app.tenant_id = '...'
                        SET LOCAL app.org_id = '...'
                        SET LOCAL app.user_id = '...'
                        SET LOCAL app.role = 'end_user'
                    │
                    ▼
            RLS policies enforced per-transaction
            (cursor scope visible to cursor/cursor_user/platform_admin)
```

### RLS Scope Access Matrix

| Scope       | end_user | cursor | l9_system | platform_admin |
| ----------- | -------- | ------ | --------- | -------------- |
| `cursor`    | No       | Yes    | No        | Yes            |
| `developer` | Yes      | Yes    | Yes       | Yes            |
| `global`    | Yes      | Yes    | Yes       | Yes            |
| `agent`     | Yes      | Yes    | Yes       | Yes            |
| `shared`    | Yes      | Yes    | Yes       | Yes            |
| `l-private` | No       | No     | Yes       | Yes            |

### Tables with RLS Enabled

| Table                     | Policy Type                           |
| ------------------------- | ------------------------------------- |
| `packet_store`            | tenant + org + scope + admin override |
| `semantic_memory`         | scope-based (migration 0033)          |
| `knowledge_facts`         | scope-based (migration 0033)          |
| `episodic_events`         | tenant + role-based                   |
| `episodic_semantic_links` | inherited from episodic_events        |
| `memory_embeddings`       | tenant + org + admin override         |
| `memory_access_log`       | tenant + org + admin override         |
| `entity_relationships`    | tenant + org + admin override         |
| `memory_summaries`        | tenant + org + admin override         |
| `reflection_store`        | tenant + org + admin override         |
| `task_reflections`        | tenant + org + admin override         |
| `semantic_facts`          | tenant + role-based                   |
| `feedback_events`         | tenant + org + admin override         |

---

## Troubleshooting

### Health Check Failed

```bash
# Check if MCP is reachable directly
curl -s http://46.62.243.82:9002/health

# Check API key is set
echo $MCP_API_KEY_C

# Test MCP endpoint directly
curl -X POST http://46.62.243.82:9002/mcp/call \
  -H "Authorization: Bearer $MCP_API_KEY_C" \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "get_memory_stats", "arguments": {"user_id": "l9-shared", "duration": "all"}}'
```

### 403: Scope Not Authorized

If you see `403: Scope 'X' not authorized for this context`:
1. Cursor must use `scope: "cursor"` for writes
2. Search scopes must be `["cursor", "developer", "global"]`
3. Check that `mcp_memory/src/main.py` includes `cursor` in `allowed_scopes`

### 403: project_id Must Be Derived

If you see `403: project_id must be derived from governance context`:
1. Ensure `project_id` defaults match across `main.py`, `mcp_server.py`, and `memory_unified.py`
2. All should default to `"l9-default"`

### Empty Search Results After Write

1. Check that `semantic_memory` RLS policy allows `cursor` scope (migration 0033)
2. Verify the write actually succeeded (check response for `packet_id`)
3. Wait a moment for embedding generation to complete

### Write Returns Error

1. Check API key is correct (`MCP_API_KEY_C`)
2. Verify C1 MCP container is running: `ssh c1 "docker ps | grep mcp"`
3. Check content isn't too long (max ~10KB)

---

## C1 Endpoints Reference

| Service        | Endpoint                         | Port  |
| -------------- | -------------------------------- | ----- |
| **MCP Memory** | `http://46.62.243.82:9002`       | 9002  |
| **PostgreSQL** | `46.62.243.82:30432`             | 30432 |
| **Neo4j HTTP** | `http://46.62.243.82:30474`      | 30474 |
| **Neo4j Bolt** | `bolt://46.62.243.82:30687`      | 30687 |
| **Redis**      | `46.62.243.82:30379`             | 30379 |

---

## Key Files

| File | Purpose |
|------|---------|
| `agents/cursor/cursor_memory_client.py` | CLI + library — all memory operations |
| `agents/cursor/cursor_memory_kernel.py` | Session kernel — lessons, TODOs, confidence |
| `agents/cursor/cursor_memory_kernel.yaml` | Binding contract — when to read/write/inject |
| `mcp_memory/src/main.py` | MCP server — builds governance context |
| `mcp_memory/src/routes/memory_unified.py` | Route handlers — save/search/stats |
| `config/rls_config.py` | RLS UUID generation |
| `migrations/0033_add_cursor_scope.sql` | cursor scope + RLS policy updates |
