# Cursor-L9 Integration Guide

**Updated:** 2026-02-13
**Purpose:** How Cursor IDE leverages L9's infrastructure
**MCP Memory:** Direct access at `http://46.62.243.82:9002`

---

## Integration Status

| Capability             | Status     | How                                                        |
| ---------------------- | ---------- | ---------------------------------------------------------- |
| **Memory Read**        | WORKS      | MCP `search_memory` via direct HTTP to port 9002           |
| **Memory Write**       | WORKS      | MCP `save_memory` via direct HTTP to port 9002             |
| **Memory Scope**       | WORKS      | Cursor writes to `scope: "cursor"` (migration 0033)        |
| **Kernel Reference**   | WORKS      | `readme/L9-KERNEL-REFERENCE.md`                            |
| **Mistake Prevention** | WORKS      | `.cursor/rules/92-learned-lessons.mdc`                     |
| **Neo4j Graph**        | WORKS      | `agents/cursor/cursor_neo4j_query.py`                      |
| **MCP Memory Server**  | ACTIVE     | `http://46.62.243.82:9002` (direct, no proxy)              |
| **Repo Indexes**       | ACTIVE     | 34 index files at `reports/repo-index/`                    |

---

## 1. Memory Read & Write (MCP Memory Server)

Cursor has **full read/write access** to L9's memory via the MCP Memory Server.

### Connection

```bash
# Direct to MCP Memory (no nginx, no proxy)
MCP_URL=http://46.62.243.82:9002
MCP_API_KEY_C=<cursor-api-key>
```

### Write (scope: cursor)

```bash
python3 agents/cursor/cursor_memory_client.py write "lesson content" --kind lesson --scope cursor
```

### Search (scopes: cursor, developer, global)

```bash
python3 agents/cursor/cursor_memory_client.py search "governance rules"
```

### Core Tables

| Table                 | Contents                          |
| --------------------- | --------------------------------- |
| `packet_store`        | All memory packets (canonical)    |
| `semantic_memory`     | pgvector 1536-dim embeddings      |
| `knowledge_facts`     | Extracted knowledge graph facts   |
| `reasoning_traces`    | Agent reasoning step chains       |
| `agent_memory_events` | Tool calls, decisions, lifecycle  |
| `graph_checkpoints`   | Agent state snapshots             |

### RLS Scope Model

| Scope       | Cursor Can Write | Cursor Can Read | Purpose                  |
| ----------- | ---------------- | --------------- | ------------------------ |
| `cursor`    | Yes (default)    | Yes             | Cursor-specific memories |
| `developer` | No               | Yes             | Shared dev knowledge     |
| `global`    | No               | Yes             | Cross-project knowledge  |
| `l-private` | No               | No              | L's internal operations  |

---

## 2. Kernel Reference (Governance Rules)

L9's 10 kernels are in `private/` which is blocked by `.cursorignore`.

**Solution:** Readable summary at `readme/L9-KERNEL-REFERENCE.md`

### Key Governance Rules to Follow

| Kernel         | Key Rule for Cursor                                  |
| -------------- | ---------------------------------------------------- |
| **Master**     | Igor-only authority, executive mode by default       |
| **Behavioral** | Confidence >= 0.80 → execute, < 0.50 → ask questions |
| **Memory**     | Never repeat mistakes, log all corrections           |
| **Developer**  | Use structlog, httpx, Pydantic v2                    |

### Apply Kernel Rules

When generating code, reference the kernel summary:

```python
# L9 Pattern (from Developer Kernel)
import structlog
import httpx
from pydantic import BaseModel

# NOT L9 Pattern
import logging    # Use structlog instead
import requests   # Use httpx instead
```

---

## 3. Mistake Prevention

Mistakes are prevented via `.cursor/rules/92-learned-lessons.mdc` which is always-applied.

This rule contains 40+ learned lessons extracted from real user corrections, including:
- Path rules (Dropbox not Library, $HOME not hardcoded)
- Execution rules (surgical edits, run commands proactively)
- Verification rules (never claim fixed without proof)
- Data integrity (never fabricate data)
- File operations (never move/rename without permission)

The rule is automatically loaded by Cursor for every session — no manual action needed.

---

## 4. What Cursor Shares with L

| Shared         | Details                            |
| -------------- | ---------------------------------- |
| **Codebase**   | Same L9 workspace                  |
| **Rules**      | Same `.cursor/rules/*.mdc` files   |
| **Patterns**   | Same Python/TypeScript conventions |
| **PostgreSQL** | Same database, scope-isolated      |
| **Memory**     | Same MCP server, scope-isolated    |

| NOT Shared           | Details                                     |
| -------------------- | ------------------------------------------- |
| **Write Scope**      | L writes `developer`; Cursor writes `cursor`|
| **l-private Scope**  | Only L can read/write l-private              |
| **Redis Session**    | Separate tenant IDs (cursor vs l-cto)       |
| **Private Kernels**  | Cursor reads summary only                   |

---

## 5. Neo4j Graph Access

Cursor can query L9's Neo4j repo graph:

```bash
# Count nodes by type
python3 agents/cursor/cursor_neo4j_query.py --count-nodes

# Find a class
python3 agents/cursor/cursor_neo4j_query.py --find-class ToolRegistry

# Find files
python3 agents/cursor/cursor_neo4j_query.py --find-file executor

# List all tools
python3 agents/cursor/cursor_neo4j_query.py --list-tools

# Custom Cypher
python3 agents/cursor/cursor_neo4j_query.py "MATCH (t:Tool) RETURN t.name LIMIT 10"
```

---

## 6. Repo Index Files (34 Total)

Before searching the codebase, check `reports/repo-index/`:

| Index File | Contents | Use For |
|---|---|---|
| `class_definitions.txt` | 1,900+ classes with paths | "Where is class X?" |
| `function_signatures.txt` | 4,794 functions (ALL) | "What args does Y take?" |
| `inheritance_graph.txt` | 802 inheritance relationships | "What extends BaseAgent?" |
| `method_catalog.txt` | 5,288 class methods | "What methods does X have?" |
| `route_handlers.txt` | 180 API routes | "What handles POST /api/memory?" |
| `pydantic_models.txt` | 470 BaseModel subclasses | "What's the schema for X?" |
| `dynamic_tool_catalog.txt` | Scanned from core/tools/ | Accurate tool discovery |

---

## 7. Tool Registration (ADR-0094)

Tools are registered via the **unified primary pipeline** (ADR-0094):

```
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL REGISTRATION FLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  @register_tool decorator at module level:                      │
│                                                                 │
│  1. Tool auto-registers into runtime/tool_registry.py           │
│                        ↓                                        │
│  2. sync_runtime_tools_to_primary() bridges to primary          │
│                        ↓                                        │
│  3. core.tools.base_registry.ToolRegistry (primary)             │
│                        ↓                                        │
│  4. Tool available to ALL agents via unified pipeline            │
│                                                                 │
│  Agent-specific tool access is controlled by:                   │
│  - Agent kernel configuration                                   │
│  - Governance approval gates                                    │
│  - NOT by tool registration (tools are agent-agnostic)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Verify Tool Wiring

```bash
python3 ci/check_tool_wiring.py
```

---

## 8. Kernel Patterns for Cursor

When generating code for L9, Cursor MUST follow these patterns from the kernels:

### Python Imports (MANDATORY)

```python
# REQUIRED - Always use these
import structlog              # NOT logging
import httpx                  # NOT requests
from pydantic import BaseModel  # Pydantic v2 (not v1)

# FORBIDDEN - Never use these
import logging   # Use structlog instead
import requests  # Use httpx instead
```

### Code Standards

| Pattern         | Required                          |
| --------------- | --------------------------------- |
| Type hints      | All functions                     |
| Docstrings      | Google style                      |
| Error handling  | Explicit packets, not bare except |
| I/O operations  | Always async                      |
| Data validation | Pydantic v2 BaseModel             |
| DORA headers    | `__dora_meta__` dict in every module |

### Pre-Generation Checklist

Before outputting any Python code for L9:

1. Uses `structlog` (not `logging`)
2. Uses `httpx` (not `requests`)
3. Uses Pydantic v2 patterns
4. Has type hints on all functions
5. Has Google-style docstrings
6. No bare `except:` clauses
7. All I/O is async
8. Uses `$HOME` not hardcoded paths
9. Has `__dora_meta__` header (ADR-0014)
10. Uses parameterized SQL, not f-strings (ADR-0087)

---

## 9. Cursor Agent Files

| File | Purpose | Status |
|------|---------|--------|
| `agents/cursor/cursor_memory_client.py` | CLI + library for all MCP memory operations | **ACTIVE** — primary tool |
| `agents/cursor/cursor_memory_kernel.py` | Session kernel — lessons, TODOs, confidence logic | **ACTIVE** — singleton |
| `agents/cursor/cursor_memory_kernel.yaml` | Binding contract — when to read/write/inject | **ACTIVE** — loaded at init |
| `agents/cursor/cursor_neo4j_query.py` | CLI for querying Neo4j graph | **ACTIVE** — manual use |
| `agents/cursor/cursor_retrieval_kernel.py` | 3-tier retrieval: cache → memory → repo | **DORMANT** — not wired |
| `agents/cursor/cursor_session_hooks.py` | Session lifecycle hooks for working memory | **DORMANT** — not wired |
| `agents/cursor/cursor_system_prompt.md` | System prompt for MCP memory identity | **REFERENCE** — not auto-loaded |
| `agents/cursor/governance-reference.md` | Quick governance reference | **REFERENCE** |

---

## Integration Points

### Files Cursor Should Reference

| File                                    | Purpose                        |
| --------------------------------------- | ------------------------------ |
| `readme/L9-KERNEL-REFERENCE.md`         | Kernel governance rules        |
| `.cursor/rules/*.mdc`                   | Cursor-native rules (always-applied) |
| `reports/repo-index/*.txt`              | 34 pre-built codebase indexes  |
| `agents/cursor/cursor_memory_kernel.yaml` | Memory behavior contract     |
| `agents/cursor/governance-reference.md` | Governance quick reference     |

### How to Leverage L9 from Cursor

1. **Before generating code:** Check `L9-KERNEL-REFERENCE.md` for patterns
2. **Before searching codebase:** Check `reports/repo-index/` indexes first
3. **To read L's context:** Use `cursor_memory_client.py search` with scopes
4. **To persist learnings:** Use `cursor_memory_client.py write --scope cursor`
5. **To query graph:** Use `cursor_neo4j_query.py` for class/file/tool lookups

---

## Related Documentation

- `docs/MCP-MEMORY-CAPSULE.md` — Agent integration guide for MCP Memory
- `docs/DATABASE_BEST_PRACTICES.md` — Database patterns and RLS guide
- `docs/MEMORY_PIPELINE_MAP.md` — Full memory ingestion/retrieval pipeline
- `readme/L9-KERNEL-REFERENCE.md` — All 10 kernels summarized
- `.cursor-commands/learning/failures/repeated-mistakes.md` — Mistake database
