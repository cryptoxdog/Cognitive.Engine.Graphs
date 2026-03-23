#!/usr/bin/env python3
"""
Cursor Memory Client — Access L9 Memory Substrate via MCP Tools
================================================================

## ARCHITECTURE

    PRIMARY METHOD:  MCP Tools via /mcp/call endpoint
    FALLBACK METHOD: Direct HTTP API (deprecated, for graph/cache only)

## MCP TOOLS (PRIMARY - All Memory Operations)

    | Tool              | Purpose                          |
    |-------------------|----------------------------------|
    | save_memory       | Write packets to memory          |
    | search_memory     | Semantic search across memories  |
    | get_memory_stats  | Get packet counts and stats      |

## FALLBACK (Graph/Cache Only - No MCP Tools Available)

    | Endpoint                  | Purpose                |
    |---------------------------|------------------------|
    | /api/v1/memory/graph/*    | Neo4j graph operations |
    | /api/v1/memory/cache/*    | Redis cache operations |

## USAGE

    # Health (tests MCP endpoint PRIMARY + API FALLBACK)
    python cursor_memory_client.py health

    # MCP Test (write + read round-trip via MCP tools)
    python cursor_memory_client.py mcp-test

    # Search (via MCP search_memory tool)
    python cursor_memory_client.py search "error handling patterns"

    # Write (via MCP save_memory tool)
    python cursor_memory_client.py write "Igor prefers surgical edits" --kind preference

    # Stats (via MCP get_memory_stats tool)
    python cursor_memory_client.py stats

## CONFIGURATION

    Environment variables (set in repo-root .env, .env.local, or export):

    MCP_API_KEY_C: API key for Cursor (PRIMARY)
        - This key identifies caller as "C" (Cursor IDE)
        - Required for all MCP operations
        - Value: Set in .env file (NEVER hardcode)

    MCP_URL: MCP Memory endpoint
        - MUST use direct IP: http://46.62.243.82/memory
        - Domain (l9.quantumaipartners.com) is BLOCKED by Cloudflare for Python
        - nginx routes /memory/* to l9-mcp-memory:9002/*

    L9_API_URL: L9 API endpoint (fallback for graph/cache)
        - Direct IP: http://46.62.243.82
        - Local: http://127.0.0.1:8000 (Docker)

## QUICK START

    # Load from .env or set manually (get value from .env file)
    export MCP_API_KEY_C="${MCP_API_KEY_C}"
    export MCP_URL="http://46.62.243.82/memory"
    python3 agents/cursor/cursor_memory_client.py health

## SCHEMA

    PacketEnvelope: v2.0.0
    Session UUID: Date-based (same ID for entire day)
"""

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Memory Client",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-14T12:08:12Z",
    "updated_at": "2026-01-17T23:47:56Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "cursor_memory_client",
    "type": "cli",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": ["Neo4j", "Redis"],
        "memory_layers": ["working_memory", "semantic_memory"],
        "imported_by": [],
    },
}
# ============================================================================

import argparse
import hashlib
import json
import os
import ssl
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog

# =============================================================================
# Schema Version (PacketEnvelope v2.0.0)
# =============================================================================


logger = structlog.get_logger(__name__)

SCHEMA_VERSION = "2.0.0"
SUPPORTED_VERSIONS = ["1.0.0", "1.0.1", "1.1.0", "1.1.1", "2.0.0"]

# ADR-0098: DRY — Cursor default scopes defined once, used everywhere.
# Canonical source: core.config_constants.ALLOWED_SCOPES_CURSOR
# Duplicated here because this client runs standalone (outside L9 sys.path).
_DEFAULT_SCOPES: list[str] = ["cursor", "developer", "global"]

# =============================================================================
# Session UUID - Date-based (same for entire day)
# =============================================================================

# Namespace UUID for Cursor sessions (fixed, used for UUID5 generation)
CURSOR_SESSION_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def get_daily_session_id() -> str:
    """
    Generate deterministic session UUID based on current date.
    Same session ID for entire day, new one each day.

    Uses UUID5 (SHA-1 based) with fixed namespace + date string.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    session_uuid = uuid.uuid5(CURSOR_SESSION_NAMESPACE, f"cursor-session-{today}")
    return str(session_uuid)


def compute_content_hash(payload: dict) -> str:
    """Compute SHA-256 content hash for PacketEnvelope v2.0 integrity."""
    content_str = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(content_str.encode()).hexdigest()


# =============================================================================
# Configuration
# =============================================================================

# Try to load from repo root: .env first, then .env.local (local overrides)
_repo_root = Path(__file__).parent.parent.parent


def _load_dotenv_file(path: Path, *, override: bool) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            k = key.strip()
            v = value.strip()
            if override:
                os.environ[k] = v
            else:
                os.environ.setdefault(k, v)


_load_dotenv_file(_repo_root / ".env", override=False)
_load_dotenv_file(_repo_root / ".env.local", override=True)

# =============================================================================
# C1 HETZNER CONNECTION (Updated 2026-01-31)
# =============================================================================
# CRITICAL: Use direct IP to bypass Cloudflare (blocks Python user-agent)
#
# nginx on C1 routes:
#   /memory/* -> l9-mcp-memory:9002/* (strips /memory/ prefix)
#   /*        -> l9-api:8000/*
#
# Domain l9.quantumaipartners.com goes through Cloudflare which blocks Python.
# Direct IP 46.62.243.82 bypasses Cloudflare.
# =============================================================================

# MCP Memory endpoint (PRIMARY) - use direct IP to bypass Cloudflare
MCP_URL = os.getenv("MCP_URL", "http://46.62.243.82/memory")

# L9 API URL (FALLBACK for graph/cache) - also use direct IP
L9_API_URL = os.getenv("L9_API_URL", "http://46.62.243.82")

# MCP_API_KEY_C is the correct key for Cursor (caller_id: "C")
# Fallback chain: MCP_API_KEY_C -> L9_EXECUTOR_API_KEY (legacy)
L9_EXECUTOR_API_KEY = os.getenv("MCP_API_KEY_C") or os.getenv("L9_EXECUTOR_API_KEY", "")

# Skip SSL verification for self-signed certs
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# =============================================================================
# MCP Client (Primary - MCP Server ONLY)
# =============================================================================


def mcp_call_tool(tool_name: str, arguments: dict) -> dict:
    """
    Call MCP tool via /mcp/call endpoint.

    This is the PRIMARY method - all memory operations go through MCP server.
    """
    if not L9_EXECUTOR_API_KEY:
        return {"error": "L9_EXECUTOR_API_KEY not set. Add to .env or environment."}

    url = f"{MCP_URL}/mcp/call"
    headers = {
        "Authorization": f"Bearer {L9_EXECUTOR_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "tool_name": tool_name,
        "arguments": arguments,
    }

    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            result = json.loads(response.read().decode())
            # MCP server returns {"status": "success", "result": {...}, "caller": "C"}
            if result.get("status") == "success":
                return result.get("result", {})
            return {"error": result.get("detail", "MCP call failed")}
    except urllib.error.HTTPError as e:
        error_detail = e.read().decode() if e.fp else ""
        return {"error": f"HTTP {e.code}", "detail": error_detail}
    except urllib.error.URLError as e:
        return {"error": str(e)}


# =============================================================================
# FALLBACK: Direct HTTP API (Graph/Cache ONLY - No MCP tools available)
# =============================================================================


def api_request(method: str, path: str, data: dict | None = None) -> dict:
    """
    Direct HTTP API request (FALLBACK ONLY).

    ⚠️ USE ONLY FOR:
    - Graph operations (/api/v1/memory/graph/*) - No MCP tool available
    - Cache operations (/api/v1/memory/cache/*) - No MCP tool available

    ❌ DO NOT USE FOR:
    - Memory write/read (use mcp_call_tool("save_memory", ...))
    - Search (use mcp_call_tool("search_memory", ...))
    - Stats (use mcp_call_tool("get_memory_stats", ...))
    """
    if not L9_EXECUTOR_API_KEY:
        return {"error": "L9_EXECUTOR_API_KEY not set. Add to .env or environment."}

    url = f"{L9_API_URL}{path}"
    headers = {
        "Authorization": f"Bearer {L9_EXECUTOR_API_KEY}",
        "Content-Type": "application/json",
        "X-User-Id": "cursor",
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "detail": e.read().decode()}
    except urllib.error.URLError as e:
        return {"error": str(e)}


# =============================================================================
# Commands
# =============================================================================


def cmd_stats():
    """Get memory stats via MCP."""
    result = mcp_call_tool(
        "get_memory_stats",
        {
            "user_id": "l9-shared",  # Shared user_id for L + C
            "duration": "all",
        },
    )
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_health():
    """
    Check MCP memory health (PRIMARY) and API health (FALLBACK).

    Tests:
    1. MCP endpoint (/mcp/call) - PRIMARY method for memory operations
    2. Direct API (/health) - FALLBACK/infrastructure health

    MCP is healthy ONLY if /mcp/call endpoint responds successfully.
    """
    results = {
        "mcp_endpoint": {"status": "unknown", "method": "PRIMARY"},
        "api_health": {"status": "unknown", "method": "FALLBACK"},
        "overall": "unknown",
    }

    # TEST 1: MCP Endpoint (PRIMARY) - test with get_memory_stats
    mcp_result = mcp_call_tool(
        "get_memory_stats",
        {
            "user_id": "l9-shared",
            "duration": "all",
        },
    )

    if "error" in mcp_result:
        results["mcp_endpoint"] = {
            "status": "unhealthy",
            "method": "PRIMARY",
            "error": mcp_result.get("error"),
            "detail": mcp_result.get("detail", ""),
        }
    else:
        results["mcp_endpoint"] = {
            "status": "healthy",
            "method": "PRIMARY",
            "response_keys": (list(mcp_result.keys()) if isinstance(mcp_result, dict) else "ok"),
        }

    # TEST 2: Direct API Health (FALLBACK)
    url = f"{L9_API_URL}/health"
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as response:
            api_result = json.loads(response.read().decode())
            results["api_health"] = {
                "status": "healthy",
                "method": "FALLBACK",
                "service": api_result.get("service", "unknown"),
                "startup_ready": api_result.get("startup_ready", False),
            }
    except Exception as e:
        results["api_health"] = {
            "status": "unhealthy",
            "method": "FALLBACK",
            "error": str(e),
        }

    # OVERALL: MCP must be healthy for memory operations
    if results["mcp_endpoint"]["status"] == "healthy":
        results["overall"] = "healthy"
        results["message"] = "✅ MCP endpoint healthy - memory operations available"
    elif results["api_health"]["status"] == "healthy":
        results["overall"] = "degraded"
        results["message"] = "⚠️ MCP unhealthy, API healthy - memory operations UNAVAILABLE, use direct API workaround"
    else:
        results["overall"] = "unhealthy"
        results["message"] = "❌ Both MCP and API unhealthy - no memory operations available"

    logger.info("output", value=json.dumps(results, indent=2))


def cmd_search(query: str, limit: int = 10, min_confidence: float = 0.0, sort_by: str = "relevance"):
    """
    Semantic search via MCP with confidence filtering and sorting.

    Args:
        query: Search query
        limit: Max results (default 10)
        min_confidence: Minimum confidence threshold 0.0-1.0 (default 0.0)
        sort_by: Sort order - relevance, importance, recency (default relevance)
    """
    result = mcp_call_tool(
        "search_memory",
        {
            "query": query,
            "user_id": "l9-shared",  # Shared user_id for L + C
            "scopes": [
                "cursor",
                "developer",
                "global",
            ],  # Cursor reads cursor + developer + global (not l-private)
            "top_k": limit * 2,  # Fetch extra for filtering
            "threshold": min_confidence,
            "duration": "all",
        },
    )

    # Server returns "results" key, not "memories"
    hits = result.get("results", []) or result.get("memories", [])

    # Filter by min_confidence (if not already filtered by threshold)
    if min_confidence > 0:
        hits = [h for h in hits if h.get("similarity", 0) >= min_confidence]

    # Sort
    if sort_by == "importance":
        hits.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
    elif sort_by == "recency":
        hits.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    # else: keep relevance order (default from MCP)

    # Limit final results
    hits = hits[:limit]

    print(
        json.dumps(
            {
                "query": query,
                "hits": hits,
                "count": len(hits),
                "min_confidence": min_confidence,
                "sort_by": sort_by,
            },
            indent=2,
        )
    )


def cmd_write(
    content: str,
    kind: str = "note",
    thread_id: str | None = None,
    scope: str = "cursor",
    tags: list[str] | None = None,
):
    """
    Write to memory via MCP using PacketEnvelope v2.0 schema.

    Uses daily session UUID if no thread_id provided.
    Cursor IDE writes default to scope='cursor' per RLS design (ADR-0005).

    Agents MUST add tags and keywords to every memory write for best retrieval.
    Pass domain/topic/keyword tags (e.g. ["lesson", "cursor", "structlog", "error_handling"]).
    If tags are omitted, a single kind-based tag is used as fallback.
    """
    # Use daily session ID if not explicitly provided
    session_id = thread_id or get_daily_session_id()

    # Require tags for retrieval quality: use caller tags or fallback to kind
    tag_list = list(tags) if tags else [f"kind:{kind}"]

    # Map kind to MCP duration (default: long for durability)
    kind_to_duration = {
        "preference": "long",
        "lesson": "long",
        "error": "medium",
        "insight": "long",
        "note": "medium",
        "fact": "long",
    }
    duration = kind_to_duration.get(kind, "long")

    # Call MCP save_memory tool
    result = mcp_call_tool(
        "save_memory",
        {
            "content": content,
            "kind": kind,
            "scope": scope,
            "duration": duration,
            "user_id": "l9-shared",  # Shared user_id for L + C
            "tags": tag_list,
            "importance": 1.0,  # Default importance
        },
    )

    # Add session info to output
    result["_session_id"] = session_id
    result["_schema_version"] = SCHEMA_VERSION

    logger.info("output", value=json.dumps(result, indent=2))


def cmd_session():
    """Show current daily session ID."""
    session_id = get_daily_session_id()
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    print(
        json.dumps(
            {
                "date": today,
                "session_id": session_id,
                "schema_version": SCHEMA_VERSION,
            },
            indent=2,
        )
    )


def cmd_mcp_test():
    """
    MCP Round-Trip Test — Write + Search via MCP tools only.

    Tests the PRIMARY method (MCP tools) end-to-end:
    1. Write a test packet via save_memory tool
    2. Search for it via search_memory tool
    3. Report success/failure

    This is the definitive test of MCP memory availability.
    """
    import time

    test_id = f"mcp-test-{int(time.time())}"
    test_content = f"MCP_ROUNDTRIP_TEST: {test_id} - Cursor IDE verifying MCP tool pipeline"

    results = {
        "test_id": test_id,
        "steps": {},
        "overall": "unknown",
    }

    # STEP 1: Write via MCP save_memory tool
    write_result = mcp_call_tool(
        "save_memory",
        {
            "content": test_content,
            "kind": "note",
            "scope": "cursor",
            "duration": "short",  # Short-lived test packet
            "user_id": "l9-shared",
            "tags": ["mcp_test", test_id],
            "importance": 0.1,  # Low importance test
        },
    )

    if "error" in write_result:
        results["steps"]["write"] = {
            "status": "failed",
            "error": write_result.get("error"),
            "detail": write_result.get("detail", ""),
        }
        results["overall"] = "failed"
        results["message"] = f"❌ MCP WRITE FAILED: {write_result.get('error')}"
        logger.info("output", value=json.dumps(results, indent=2))
        return
    results["steps"]["write"] = {
        "status": "success",
        "memory_id": write_result.get("memory_id"),
    }

    # STEP 2: Search via MCP search_memory tool
    time.sleep(1)  # Brief delay for indexing

    search_result = mcp_call_tool(
        "search_memory",
        {
            "query": test_id,  # Search by unique test ID
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 5,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    if "error" in search_result:
        results["steps"]["search"] = {
            "status": "failed",
            "error": search_result.get("error"),
            "detail": search_result.get("detail", ""),
        }
        results["overall"] = "partial"
        results["message"] = f"⚠️ MCP WRITE OK but SEARCH FAILED: {search_result.get('error')}"
    else:
        # Server returns "results" key, not "memories"
        memories = search_result.get("results", []) or search_result.get("memories", [])
        # Handle None content gracefully - use empty string if content is None
        found = any(test_id in (m.get("content") or "") for m in memories)

        results["steps"]["search"] = {
            "status": "success" if found else "not_found",
            "results_count": len(memories),
            "test_found": found,
        }

        if found:
            results["overall"] = "success"
            results["message"] = "✅ MCP ROUND-TRIP SUCCESS: Write + Search both working"
        else:
            results["overall"] = "partial"
            results["message"] = "⚠️ MCP WRITE OK but test packet not found in search (may need indexing time)"

    logger.info("output", value=json.dumps(results, indent=2))


def cmd_session_close():
    """
    Close session and create embedding anchor for future retrieval.

    1. Aggregates all packets from current session (via MCP search_memory)
    2. Generates session summary
    3. Creates embedding of summary (session anchor) via MCP save_memory
    4. Stores for semantic session retrieval
    """
    session_id = get_daily_session_id()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    # Step 1: Get all packets from this session via MCP
    search_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"session {today}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 50,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    memories = search_result.get("memories", [])
    packet_count = len(memories)

    # Step 2: Generate session summary
    if memories:
        # Extract content from memories
        contents = []
        for m in memories[:20]:  # Top 20 most relevant
            content = m.get("content", "")
            if content:
                contents.append(content[:200])  # Truncate long content

        summary = f"SESSION {today}: {packet_count} packets. Key topics: " + "; ".join(contents[:5])
    else:
        summary = f"SESSION {today}: No packets captured."

    # Step 3: Write session anchor to memory via MCP save_memory
    result = mcp_call_tool(
        "save_memory",
        {
            "content": summary,
            "kind": "context",  # Session anchor is context
            "scope": "cursor",
            "duration": "long",  # Session anchors persist
            "user_id": "l9-shared",
            "tags": ["session_anchor", f"session_{today}"],
            "importance": 1.0,
        },
    )

    # Output
    output = {
        "status": "session_closed",
        "session_id": session_id,
        "session_date": today,
        "packets_aggregated": packet_count,
        "summary_length": len(summary),
        "embedding_created": "memory_id" in result,
        "memory_id": result.get("memory_id"),
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_session_resume(task_description: str | None = None):
    """
    Resume session by finding relevant previous session anchors.

    If task_description provided, finds most similar past session.
    Otherwise, retrieves yesterday's/recent session context.
    All searches via MCP search_memory tool.
    """
    session_id = get_daily_session_id()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    # Search for session anchors via MCP
    query = task_description if task_description else "session_anchor recent work"

    search_result = mcp_call_tool(
        "search_memory",
        {
            "query": query,
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 5,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    memories = search_result.get("memories", [])

    # Filter for session anchors or recent sessions
    session_context = []
    for m in memories:
        content = m.get("content", "")
        similarity = m.get("similarity", 0)
        kind = m.get("kind", "unknown")

        if content:
            session_context.append(
                {
                    "content": content[:500],
                    "similarity": round(similarity * 100, 1),
                    "kind": kind,
                }
            )

    # Also search for recent lessons and preferences via MCP
    prefs_result = mcp_call_tool(
        "search_memory",
        {
            "query": "Igor preferences patterns",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["preference"],
            "top_k": 3,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    preferences = []
    for m in prefs_result.get("memories", []):
        content = m.get("content", "")
        if content:
            preferences.append(content[:200])

    # Search for recent lessons via MCP
    lessons_result = mcp_call_tool(
        "search_memory",
        {
            "query": "lessons errors cursor",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["lesson"],
            "top_k": 3,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    lessons = []
    for m in lessons_result.get("memories", []):
        content = m.get("content", "")
        if content:
            lessons.append(content[:200])

    output = {
        "status": "session_resumed",
        "session_id": session_id,
        "session_date": today,
        "task_query": task_description,
        "context_items": len(session_context),
        "session_context": session_context[:3],
        "preferences_loaded": len(preferences),
        "lessons_loaded": len(lessons),
        "message": f"🔄 Session resumed. Loaded {len(session_context)} context items, {len(preferences)} preferences, {len(lessons)} lessons.",
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_resume_for(task: str):
    """
    Resume for a specific task - finds most relevant past session by semantic similarity.

    Usage: python cursor_memory_client.py resume-for "implement Redis session context"
    """
    cmd_session_resume(task)


def cmd_warn(task_description: str):
    """
    Proactive Anti-Pattern Warning - surfaces past mistakes relevant to the task.

    Searches for errors, lessons, and warnings related to the task description.
    Shows what to AVOID based on past experience.
    All searches via MCP search_memory tool.

    Usage: python cursor_memory_client.py warn "modifying docker-compose"
    """
    # Search for errors related to task via MCP
    errors_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"error mistake {task_description}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["error", "lesson"],
            "top_k": 5,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    # Search for lessons related to task via MCP
    lessons_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"lesson warning {task_description}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["lesson"],
            "top_k": 5,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    # Search for violations via MCP
    violations_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"violation critical {task_description}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 3,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    warnings = []

    # Process errors
    for m in errors_result.get("memories", []):
        content = m.get("content", "")
        similarity = m.get("similarity", 0)
        kind = m.get("kind", "")

        if content and similarity > 0.02 and kind in ["error", "lesson", "insight"]:
            warnings.append(
                {
                    "type": "⚠️ WARNING",
                    "content": content[:300],
                    "relevance": round(similarity * 100, 1),
                    "source": kind,
                }
            )

    # Process lessons
    for m in lessons_result.get("memories", []):
        content = m.get("content", "")
        similarity = m.get("similarity", 0)
        kind = m.get("kind", "")

        if content and similarity > 0.02 and kind == "lesson":
            # Avoid duplicates
            if not any(w["content"][:100] == content[:100] for w in warnings):
                warnings.append(
                    {
                        "type": "📚 LESSON",
                        "content": content[:300],
                        "relevance": round(similarity * 100, 1),
                        "source": kind,
                    }
                )

    # Process violations
    for m in violations_result.get("memories", []):
        content = m.get("content", "")
        similarity = m.get("similarity", 0)

        if content and similarity > 0.02:
            warnings.append(
                {
                    "type": "🚨 CRITICAL",
                    "content": content[:300],
                    "relevance": round(similarity * 100, 1),
                    "source": "violation",
                }
            )

    # Sort by relevance
    warnings.sort(key=lambda x: x["relevance"], reverse=True)

    output = {
        "task": task_description,
        "warning_count": len(warnings),
        "warnings": warnings[:10],  # Top 10
        "message": f"🛡️ Found {len(warnings)} relevant warnings/lessons for: {task_description}",
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_inject(task_description: str | None = None, layers: str = "all"):
    """
    Layered Context Injection - injects context at 5 levels.

    Layers:
    1. Preferences - Igor's coding style, patterns
    2. Command - patterns for current command type
    3. Domain - patterns for current domain (memory, agents, etc.)
    4. File - patterns for specific files being touched
    5. Temporal - recent session context

    Usage: python cursor_memory_client.py inject "working on memory substrate"
           python cursor_memory_client.py inject --layers "preferences,lessons"
    """
    context = {
        "preferences": [],
        "lessons": [],
        "domain": [],
        "temporal": [],
        "warnings": [],
    }

    # Layer 1: Preferences via MCP
    prefs_result = mcp_call_tool(
        "search_memory",
        {
            "query": "Igor preferences patterns coding style",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["preference"],
            "top_k": 5,
            "threshold": 0.0,
            "duration": "all",
        },
    )
    for m in prefs_result.get("memories", []):
        content = m.get("content", "")
        if content:
            context["preferences"].append(content[:200])

    # Layer 2: Lessons via MCP
    lessons_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"lessons errors cursor {task_description or ''}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["lesson"],
            "top_k": 5,
            "threshold": 0.0,
            "duration": "all",
        },
    )
    for m in lessons_result.get("memories", []):
        content = m.get("content", "")
        if content:
            context["lessons"].append(content[:200])

    # Layer 3: Domain context (if task provided) via MCP
    if task_description:
        domain_result = mcp_call_tool(
            "search_memory",
            {
                "query": task_description,
                "user_id": "l9-shared",
                "scopes": _DEFAULT_SCOPES,
                "top_k": 5,
                "threshold": 0.0,
                "duration": "all",
            },
        )
        for m in domain_result.get("memories", []):
            content = m.get("content", "")
            if content:
                context["domain"].append(content[:200])

    # Layer 4: Temporal (recent) via MCP
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    temporal_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"session {today} recent work",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 3,
            "threshold": 0.0,
            "duration": "all",
        },
    )
    for m in temporal_result.get("memories", []):
        content = m.get("content", "")
        if content:
            context["temporal"].append(content[:150])

    # Layer 5: Warnings (anti-patterns) via MCP
    if task_description:
        warn_result = mcp_call_tool(
            "search_memory",
            {
                "query": f"error mistake warning {task_description}",
                "user_id": "l9-shared",
                "scopes": _DEFAULT_SCOPES,
                "kinds": ["error", "lesson"],
                "top_k": 3,
                "threshold": 0.0,
                "duration": "all",
            },
        )
        for m in warn_result.get("memories", []):
            content = m.get("content", "")
            if content:
                context["warnings"].append(content[:150])

    total_items = sum(len(v) for v in context.values())

    output = {
        "task": task_description,
        "layers_loaded": {
            "preferences": len(context["preferences"]),
            "lessons": len(context["lessons"]),
            "domain": len(context["domain"]),
            "temporal": len(context["temporal"]),
            "warnings": len(context["warnings"]),
        },
        "total_items": total_items,
        "context": context,
        "message": f"🧠 Injected {total_items} context items across 5 layers",
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_temporal(query: str, since: str = "24h", until: str | None = None):
    """
    Temporal Context Windowing - time-scoped memory queries.

    Args:
        query: Search query
        since: Time window start (24h, 7d, 30d, or ISO date)
        until: Time window end (optional, defaults to now)

    Usage:
        python cursor_memory_client.py temporal "docker" --since 24h
        python cursor_memory_client.py temporal "migration" --since 7d
    All searches via MCP search_memory tool.
    """
    # Parse since into approximate time description
    time_desc = f"recent {since}" if since in ["24h", "7d", "30d"] else f"since {since}"

    # Search with temporal context in query via MCP
    result = mcp_call_tool(
        "search_memory",
        {
            "query": f"{query} {time_desc}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 15,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    memories = result.get("memories", [])

    output = {
        "query": query,
        "time_window": {"since": since, "until": until or "now"},
        "result_count": len(memories),
        "hits": memories[:10],
        "message": f"🕐 Found {len(memories)} results for '{query}' in {since} window",
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_fix_error(error_message: str):
    """
    Memory-Aware Error Recovery - search for past fixes when error occurs.

    Searches memory for similar errors and their solutions.
    All searches via MCP search_memory tool.

    Usage: python cursor_memory_client.py fix-error "connection refused port 5432"
    """
    # Search for similar errors via MCP
    error_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"error fix solution {error_message}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["error", "lesson"],
            "top_k": 10,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    # Search for lessons about this error type via MCP
    lesson_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"lesson {error_message}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "kinds": ["lesson"],
            "top_k": 5,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    fixes = []

    for m in error_result.get("memories", []):
        content = m.get("content", "")
        similarity = m.get("similarity", 0)
        kind = m.get("kind", "")

        if content and similarity > 0.02:
            fixes.append(
                {
                    "type": "🔧 FIX" if kind in ["lesson", "insight"] else "📝 RELATED",
                    "content": content[:400],
                    "relevance": round(similarity * 100, 1),
                    "source": kind,
                }
            )

    for m in lesson_result.get("memories", []):
        content = m.get("content", "")
        similarity = m.get("similarity", 0)

        if content and similarity > 0.02:
            if not any(f["content"][:100] == content[:100] for f in fixes):
                fixes.append(
                    {
                        "type": "📚 LESSON",
                        "content": content[:400],
                        "relevance": round(similarity * 100, 1),
                        "source": "lesson",
                    }
                )

    fixes.sort(key=lambda x: x["relevance"], reverse=True)

    output = {
        "error": error_message[:200],
        "fix_count": len(fixes),
        "fixes": fixes[:8],
        "message": f"🔍 Found {len(fixes)} potential fixes for: {error_message[:50]}...",
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_suggest(context: str | None = None):
    """
    Proactive Suggestion Engine - pattern-based next-step suggestions.

    Analyzes current context and suggests next actions based on patterns.
    All searches via MCP search_memory tool.

    Usage: python cursor_memory_client.py suggest "working on memory client"
    """
    # Search for patterns related to context via MCP
    if context:
        pattern_result = mcp_call_tool(
            "search_memory",
            {
                "query": f"pattern workflow next step {context}",
                "user_id": "l9-shared",
                "scopes": _DEFAULT_SCOPES,
                "top_k": 10,
                "threshold": 0.0,
                "duration": "all",
            },
        )
    else:
        # Get recent session context via MCP
        pattern_result = mcp_call_tool(
            "search_memory",
            {
                "query": "recent session TODO next step workflow",
                "user_id": "l9-shared",
                "scopes": _DEFAULT_SCOPES,
                "top_k": 10,
                "threshold": 0.0,
                "duration": "all",
            },
        )

    suggestions = []

    for m in pattern_result.get("memories", []):
        content = m.get("content", "")
        similarity = m.get("similarity", 0)
        kind = m.get("kind", "")

        if content and similarity > 0.02:
            suggestions.append(
                {
                    "suggestion": content[:300],
                    "confidence": round(similarity * 100, 1),
                    "source": kind,
                }
            )

    output = {
        "context": context,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions[:5],
        "message": f"💡 Generated {len(suggestions)} suggestions",
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_dedupe_check(content: str):
    """
    Semantic Deduplication - check if content already exists before writing.

    Returns similar existing content to prevent duplicates.
    Search via MCP search_memory tool.

    Usage: python cursor_memory_client.py dedupe-check "Igor prefers surgical edits"
    """
    # Search for semantically similar content via MCP
    result = mcp_call_tool(
        "search_memory",
        {
            "query": content,
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 5,
            "threshold": 0.5,  # High similarity threshold
            "duration": "all",
        },
    )

    memories = result.get("memories", [])

    # Check for high similarity matches
    duplicates = []
    for m in memories:
        similarity = m.get("similarity", 0)
        if similarity > 0.5:  # High similarity threshold
            existing_content = m.get("content", "")
            duplicates.append(
                {
                    "existing": existing_content[:200],
                    "similarity": round(similarity * 100, 1),
                    "memory_id": m.get("memory_id"),
                }
            )

    is_duplicate = len(duplicates) > 0

    output = {
        "content": content[:100],
        "is_duplicate": is_duplicate,
        "similar_count": len(duplicates),
        "similar_items": duplicates,
        "recommendation": ("SKIP - similar content exists" if is_duplicate else "OK - content is unique"),
        "message": f"{'⚠️ Duplicate detected' if is_duplicate else '✅ Content is unique'}",
    }

    logger.info("output", value=json.dumps(output, indent=2))


def cmd_session_diff():
    """
    Session Diff - compare current session to previous session.

    Shows what changed between sessions for continuity.
    All searches via MCP search_memory tool.
    """
    session_id = get_daily_session_id()
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    # Get current session content via MCP
    current_result = mcp_call_tool(
        "search_memory",
        {
            "query": f"session {today}",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 20,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    # Get previous session content (yesterday-ish) via MCP
    previous_result = mcp_call_tool(
        "search_memory",
        {
            "query": "session_anchor previous session",
            "user_id": "l9-shared",
            "scopes": _DEFAULT_SCOPES,
            "top_k": 10,
            "threshold": 0.0,
            "duration": "all",
        },
    )

    current_topics = set()
    for m in current_result.get("memories", []):
        content = m.get("content", "")
        if content:
            # Extract key words
            words = content.lower().split()[:5]
            current_topics.update(words)

    previous_topics = set()
    for m in previous_result.get("memories", []):
        content = m.get("content", "")
        if content:
            words = content.lower().split()[:5]
            previous_topics.update(words)

    new_topics = current_topics - previous_topics
    continued_topics = current_topics & previous_topics

    output = {
        "session_id": session_id,
        "session_date": today,
        "current_items": len(current_result.get("memories", [])),
        "previous_items": len(previous_result.get("memories", [])),
        "new_topics": list(new_topics)[:10],
        "continued_topics": list(continued_topics)[:10],
        "message": f"📊 Session diff: {len(new_topics)} new topics, {len(continued_topics)} continued",
    }

    logger.info("output", value=json.dumps(output, indent=2))


# =============================================================================
# Graph Operations (Neo4j via REST API) - FALLBACK METHOD
# No MCP tools available for graph operations
# =============================================================================


def cmd_graph_health():
    """Check Neo4j graph health via REST API (FALLBACK - no MCP tool)."""
    result = api_request("GET", "/api/v1/memory/graph/health")
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_graph_context(domain: str, limit: int = 10):
    """
    Get graph context for a domain.

    Usage: python cursor_memory_client.py graph-context memory
           python cursor_memory_client.py graph-context agents --limit 20
    """
    result = api_request("GET", f"/api/v1/memory/graph/context/{domain}?limit={limit}")
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_graph_query(query: str, params: str | None = None):
    """
    Run a Cypher query on Neo4j.

    Usage: python cursor_memory_client.py graph-query "MATCH (n) RETURN n LIMIT 5"
           python cursor_memory_client.py graph-query "MATCH (n:Agent) RETURN n" --params '{"name": "L"}'
    """
    data = {"query": query}
    if params:
        try:
            data["parameters"] = json.loads(params)
        except json.JSONDecodeError:
            logger.error("output", value=json.dumps({"error": f"Invalid JSON params: {params}"}))
            return

    result = api_request("POST", "/api/v1/memory/graph/query", data)
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_graph_entity(entity_type: str, entity_id: str):
    """
    Get an entity from the graph.

    Usage: python cursor_memory_client.py graph-entity Agent L-CTO
    """
    result = api_request("GET", f"/api/v1/memory/graph/entity/{entity_type}/{entity_id}")
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_graph_relationships(entity_type: str, entity_id: str, direction: str = "both"):
    """
    Get relationships for an entity.

    Usage: python cursor_memory_client.py graph-rels Agent L-CTO
           python cursor_memory_client.py graph-rels Session abc123 --direction outgoing
    """
    result = api_request(
        "GET",
        f"/api/v1/memory/graph/relationships/{entity_type}/{entity_id}?direction={direction}",
    )
    logger.info("output", value=json.dumps(result, indent=2))


# =============================================================================
# Cache Operations (Redis via REST API) - FALLBACK METHOD
# No MCP tools available for cache operations
# =============================================================================


def cmd_cache_health():
    """Check Redis cache health via REST API (FALLBACK - no MCP tool)."""
    result = api_request("GET", "/api/v1/memory/cache/health")
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_cache_get(key: str):
    """
    Get value from Redis cache.

    Usage: python cursor_memory_client.py cache-get mykey
    """
    result = api_request("GET", f"/api/v1/memory/cache/get/{key}")
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_cache_set(key: str, value: str, ttl: int | None = None):
    """
    Set value in Redis cache.

    Usage: python cursor_memory_client.py cache-set mykey "myvalue"
           python cursor_memory_client.py cache-set mykey "myvalue" --ttl 3600
    """
    data = {"key": key, "value": value}
    if ttl:
        data["ttl"] = ttl

    result = api_request("POST", "/api/v1/memory/cache/set", data)
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_cache_session_context(session_id: str | None = None):
    """
    Get session context from Redis.

    Usage: python cursor_memory_client.py cache-session
           python cursor_memory_client.py cache-session abc123
    """
    sid = session_id or get_daily_session_id()
    result = api_request("GET", f"/api/v1/memory/cache/session/context/{sid}")

    output = {"session_id": sid, "from_cache": True, **result}
    logger.info("output", value=json.dumps(output, indent=2))


def cmd_cache_set_session_context(context_json: str):
    """
    Set session context in Redis.

    Usage: python cursor_memory_client.py cache-set-session '{"summary": "Working on memory", "files": ["client.py"]}'
    """
    session_id = get_daily_session_id()

    try:
        context = json.loads(context_json)
    except json.JSONDecodeError:
        logger.error("output", value=json.dumps({"error": f"Invalid JSON: {context_json}"}))
        return

    data = {
        "session_id": session_id,
        "context": context,
        "ttl": 86400,  # 24 hours
    }

    result = api_request("POST", "/api/v1/memory/cache/session/context", data)
    logger.info("output", value=json.dumps(result, indent=2))


def cmd_cache_list_sessions():
    """
    List recent sessions from Redis.

    Usage: python cursor_memory_client.py cache-sessions
    """
    result = api_request("GET", "/api/v1/memory/cache/session/list")
    logger.info("output", value=json.dumps(result, indent=2))


# =============================================================================
# Main
# =============================================================================


def main():
    """
    Performs main execution flow for Cursor Memory Client CLI, parsing commands to interact with L9 Memory Substrate via MCP tools.

    Args:
        args: List of command-line arguments to process.

    Returns:
        None, executes command actions based on parsed arguments.

    Raises:
        SystemExit: If argument parsing fails or help is requested.
    """
    parser = argparse.ArgumentParser(description="Cursor Memory Client (PacketEnvelope v2.0)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # stats
    subparsers.add_parser("stats", help="Get memory stats")

    # health
    subparsers.add_parser("health", help="Check memory health")

    # session
    subparsers.add_parser("session", help="Show current daily session ID")

    # mcp-test (MCP round-trip test)
    subparsers.add_parser("mcp-test", help="MCP round-trip test (write + search via MCP tools)")

    # search (with confidence filtering and sorting)
    search_parser = subparsers.add_parser("search", help="Semantic search with filtering")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=10, help="Max results")
    search_parser.add_argument("--min-confidence", type=float, default=0.0, help="Min confidence 0.0-1.0")
    search_parser.add_argument(
        "--sort",
        default="relevance",
        choices=["relevance", "importance", "recency"],
        help="Sort order",
    )

    # write
    write_parser = subparsers.add_parser("write", help="Write to memory")
    write_parser.add_argument("content", help="Content to write")
    write_parser.add_argument(
        "--kind",
        default="note",
        help="Packet type (note, preference, lesson, insight, error)",
    )
    write_parser.add_argument(
        "--thread",
        default=None,
        help="Override thread UUID (default: daily session ID)",
    )
    write_parser.add_argument(
        "--scope",
        default="cursor",
        help="Memory scope (cursor, developer, global). Default: cursor",
    )
    write_parser.add_argument(
        "--tags",
        default="",
        help="Comma-separated tags and keywords (required for best retrieval; e.g. lesson,cursor,structlog)",
    )

    # session-close
    subparsers.add_parser("session-close", help="Close session and create embedding anchor")

    # session-resume
    resume_parser = subparsers.add_parser("session-resume", help="Resume session from previous context")
    resume_parser.add_argument("--task", default=None, help="Task description for context retrieval")

    # resume-for (alias for session-resume with task)
    resume_for_parser = subparsers.add_parser("resume-for", help="Resume for specific task")
    resume_for_parser.add_argument("task", help="Task description to find relevant session")

    # warn (proactive anti-pattern warning)
    warn_parser = subparsers.add_parser("warn", help="Surface past mistakes relevant to task")
    warn_parser.add_argument("task", help="Task description to find relevant warnings")

    # inject (layered context injection)
    inject_parser = subparsers.add_parser("inject", help="Inject context across 5 layers")
    inject_parser.add_argument("task", nargs="?", default=None, help="Task description for context")
    inject_parser.add_argument(
        "--layers",
        default="all",
        help="Layers to include (all, preferences, lessons, domain, temporal, warnings)",
    )

    # temporal (time-windowed queries)
    temporal_parser = subparsers.add_parser("temporal", help="Time-scoped memory queries")
    temporal_parser.add_argument("query", help="Search query")
    temporal_parser.add_argument("--since", default="24h", help="Time window (24h, 7d, 30d, or ISO date)")
    temporal_parser.add_argument("--until", default=None, help="End of time window")

    # fix-error (memory-aware error recovery)
    fix_error_parser = subparsers.add_parser("fix-error", help="Find past fixes for error")
    fix_error_parser.add_argument("error", help="Error message to find fixes for")

    # suggest (proactive suggestions)
    suggest_parser = subparsers.add_parser("suggest", help="Get pattern-based suggestions")
    suggest_parser.add_argument("context", nargs="?", default=None, help="Current context for suggestions")

    # dedupe-check (semantic deduplication)
    dedupe_parser = subparsers.add_parser("dedupe-check", help="Check if content already exists")
    dedupe_parser.add_argument("content", help="Content to check for duplicates")

    # session-diff (compare sessions)
    subparsers.add_parser("session-diff", help="Compare current session to previous")

    # --- Graph Operations (Neo4j) ---
    subparsers.add_parser("graph-health", help="Check Neo4j health")

    graph_context_parser = subparsers.add_parser("graph-context", help="Get graph context for domain")
    graph_context_parser.add_argument("domain", help="Domain name (memory, agents, tools, etc.)")
    graph_context_parser.add_argument("--limit", type=int, default=10, help="Max results")

    graph_query_parser = subparsers.add_parser("graph-query", help="Run Cypher query")
    graph_query_parser.add_argument("query", help="Cypher query string")
    graph_query_parser.add_argument("--params", default=None, help="JSON parameters")

    graph_entity_parser = subparsers.add_parser("graph-entity", help="Get entity from graph")
    graph_entity_parser.add_argument("entity_type", help="Entity type (Agent, Session, etc.)")
    graph_entity_parser.add_argument("entity_id", help="Entity ID")

    graph_rels_parser = subparsers.add_parser("graph-rels", help="Get entity relationships")
    graph_rels_parser.add_argument("entity_type", help="Entity type")
    graph_rels_parser.add_argument("entity_id", help="Entity ID")
    graph_rels_parser.add_argument("--direction", default="both", choices=["outgoing", "incoming", "both"])

    # --- Cache Operations (Redis) ---
    subparsers.add_parser("cache-health", help="Check Redis health")

    cache_get_parser = subparsers.add_parser("cache-get", help="Get value from cache")
    cache_get_parser.add_argument("key", help="Cache key")

    cache_set_parser = subparsers.add_parser("cache-set", help="Set value in cache")
    cache_set_parser.add_argument("key", help="Cache key")
    cache_set_parser.add_argument("value", help="Value to set")
    cache_set_parser.add_argument("--ttl", type=int, default=None, help="TTL in seconds")

    subparsers.add_parser("cache-session", help="Get current session context from cache")

    cache_set_session_parser = subparsers.add_parser("cache-set-session", help="Set session context in cache")
    cache_set_session_parser.add_argument("context", help="JSON context to store")

    subparsers.add_parser("cache-sessions", help="List recent sessions from cache")

    args = parser.parse_args()

    if args.command == "stats":
        cmd_stats()
    elif args.command == "health":
        cmd_health()
    elif args.command == "session":
        cmd_session()
    elif args.command == "mcp-test":
        cmd_mcp_test()
    elif args.command == "search":
        cmd_search(args.query, args.limit, args.min_confidence, args.sort)
    elif args.command == "write":
        tags_list = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
        cmd_write(args.content, args.kind, args.thread, args.scope, tags=tags_list or None)
    elif args.command == "session-close":
        cmd_session_close()
    elif args.command == "session-resume":
        cmd_session_resume(args.task)
    elif args.command == "resume-for":
        cmd_resume_for(args.task)
    elif args.command == "warn":
        cmd_warn(args.task)
    elif args.command == "inject":
        cmd_inject(args.task, args.layers)
    elif args.command == "temporal":
        cmd_temporal(args.query, args.since, args.until)
    elif args.command == "fix-error":
        cmd_fix_error(args.error)
    elif args.command == "suggest":
        cmd_suggest(args.context)
    elif args.command == "dedupe-check":
        cmd_dedupe_check(args.content)
    elif args.command == "session-diff":
        cmd_session_diff()
    # Graph commands
    elif args.command == "graph-health":
        cmd_graph_health()
    elif args.command == "graph-context":
        cmd_graph_context(args.domain, args.limit)
    elif args.command == "graph-query":
        cmd_graph_query(args.query, args.params)
    elif args.command == "graph-entity":
        cmd_graph_entity(args.entity_type, args.entity_id)
    elif args.command == "graph-rels":
        cmd_graph_relationships(args.entity_type, args.entity_id, args.direction)
    # Cache commands
    elif args.command == "cache-health":
        cmd_cache_health()
    elif args.command == "cache-get":
        cmd_cache_get(args.key)
    elif args.command == "cache-set":
        cmd_cache_set(args.key, args.value, args.ttl)
    elif args.command == "cache-session":
        cmd_cache_session_context()
    elif args.command == "cache-set-session":
        cmd_cache_set_session_context(args.context)
    elif args.command == "cache-sessions":
        cmd_cache_list_sessions()


if __name__ == "__main__":
    main()

# ============================================================================
# DORA FOOTER META - AUTO-GENERATED - DO NOT EDIT MANUALLY
# ============================================================================
__dora_footer__ = {
    "component_id": "AGE-INTE-001",
    "governance_level": "critical",
    "compliance_required": True,
    "audit_trail": True,
    "dependencies": [],
    "tags": [
        "agent-execution",
        "api",
        "auth",
        "cache",
        "caching",
        "cli",
        "event-driven",
        "filesystem",
        "intelligence",
        "messaging",
    ],
    "keywords": [
        "api",
        "cache",
        "check",
        "client",
        "close",
        "cmd",
        "compute",
        "cursor",
    ],
    "business_value": "Utility module for cursor memory client",
    "last_modified": "2026-01-17T23:47:56Z",
    "modified_by": "L9_Codegen_Engine",
    "change_summary": "Initial generation with DORA compliance",
}
# ============================================================================
# L9 DORA BLOCK - AUTO-UPDATED - DO NOT EDIT
# Runtime execution trace - updated automatically on every execution
# ============================================================================
__l9_trace__ = {
    "trace_id": "",
    "task": "",
    "timestamp": "",
    "patterns_used": [],
    "graph": {"nodes": [], "edges": []},
    "inputs": {},
    "outputs": {},
    "metrics": {"confidence": "", "errors_detected": [], "stability_score": ""},
}
# ============================================================================
# END L9 DORA BLOCK
# ============================================================================
