#!/usr/bin/env python3
"""
Cursor Neo4j Query — Query L9's Neo4j Graph Database
=====================================================

This script allows Cursor to query Neo4j's repo graph for:
- File locations
- Class definitions
- Import relationships
- Tool registrations

Usage:
    python scripts/cursor_neo4j_query.py "MATCH (n:Tool) RETURN n.name LIMIT 10"
    python scripts/cursor_neo4j_query.py --count-nodes
    python scripts/cursor_neo4j_query.py --find-class ToolRegistry
    python scripts/cursor_neo4j_query.py --find-file executor

Environment:
    NEO4J_URL: Neo4j HTTP API URL (default: http://localhost:7474)
    NEO4J_USER: Username (default: neo4j)
    Auth secret is read from the NEO4J_PASSWORD environment variable (see .env).
"""

# ============================================================================
__dora_meta__ = {
    "component_name": "Cursor Neo4J Query",
    "module_version": "1.0.0",
    "created_by": "Igor Beylin",
    "created_at": "2026-01-14T12:08:12Z",
    "updated_at": "2026-01-14T12:10:12Z",
    "layer": "intelligence",
    "domain": "agent_execution",
    "module_name": "cursor_neo4j_query",
    "type": "cli",
    "status": "active",
    "integrates_with": {
        "api_endpoints": [],
        "datasources": ["Neo4j"],
        "memory_layers": [],
        "imported_by": [],
    },
}
# ============================================================================

import argparse
import json
import os
import sys
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Try to load from .env
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Configuration
# VPS Neo4j accessible via SSH tunnel: ssh -L 7474:127.0.0.1:7474 root@157.180.73.53
# Default to VPS (production) - use --local for local Docker
VPS_NEO4J_URL = "http://127.0.0.1:7474"  # Via SSH tunnel
LOCAL_NEO4J_URL = "http://localhost:7474"  # Local Docker

# Check for --local flag in sys.argv before argparse runs
USE_LOCAL = "--local" in sys.argv or "-l" in sys.argv

NEO4J_URL = os.getenv("NEO4J_URL", LOCAL_NEO4J_URL if USE_LOCAL else VPS_NEO4J_URL)
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")
if not NEO4J_PASSWORD:
    logger.warning("NEO4J_PASSWORD env var not set — Neo4j queries will fail")


def query_neo4j(cypher: str) -> dict:
    """Execute a Cypher query against Neo4j."""
    import base64
    import urllib.request

    url = f"{NEO4J_URL}/db/neo4j/tx/commit"
    data = json.dumps({"statements": [{"statement": cypher}]}).encode()

    # Create auth header
    credentials = base64.b64encode(f"{NEO4J_USER}:{NEO4J_PASSWORD}".encode()).decode()

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {credentials}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.URLError as e:
        return {"error": str(e), "errors": [{"message": str(e)}]}


def format_results(result: dict) -> str:
    """Format Neo4j results for display."""
    if result.get("errors"):
        return f"❌ Error: {result['errors'][0].get('message', 'Unknown error')}"

    if "results" not in result or not result["results"]:
        return "No results"

    data = result["results"][0]
    columns = data.get("columns", [])
    rows = data.get("data", [])

    if not rows:
        return "No results"

    # Format as table
    output = []
    output.append(" | ".join(columns))
    output.append("-" * (len(" | ".join(columns)) + 10))

    for row_data in rows[:50]:  # Limit to 50 rows
        row = row_data.get("row", [])
        formatted_row = []
        for cell in row:
            if isinstance(cell, dict):
                cell = json.dumps(cell, default=str)[:50]
            elif isinstance(cell, list):
                cell = ", ".join(str(x) for x in cell)[:50]
            else:
                cell = str(cell)[:50]
            formatted_row.append(cell)
        output.append(" | ".join(formatted_row))

    if len(rows) > 50:
        output.append(f"... ({len(rows) - 50} more rows)")

    return "\n".join(output)


def main():
    """
    Performs main execution flow for querying Neo4j graph database with command-line arguments.

    Args:
        None

    Returns:
        None

    Raises:
        argparse.ArgumentError: If argument parsing fails.
        Exception: For general execution errors.
    """
    parser = argparse.ArgumentParser(description="Query L9's Neo4j graph database")
    parser.add_argument(
        "query",
        nargs="?",
        help="Cypher query to execute",
    )
    parser.add_argument(
        "--count-nodes",
        action="store_true",
        help="Count nodes by label",
    )
    parser.add_argument(
        "--find-class",
        type=str,
        help="Find a class by name",
    )
    parser.add_argument(
        "--find-file",
        type=str,
        help="Find files matching pattern",
    )
    parser.add_argument(
        "--find-tool",
        type=str,
        help="Find a tool by name",
    )
    parser.add_argument(
        "--list-tools",
        action="store_true",
        help="List all registered tools",
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="List all agents",
    )
    parser.add_argument(
        "--list-kernels",
        action="store_true",
        help="List all kernels",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw JSON",
    )
    parser.add_argument(
        "--local",
        "-l",
        action="store_true",
        help="Use local Docker Neo4j (default: VPS via SSH tunnel)",
    )
    parser.add_argument(
        "--vps",
        action="store_true",
        help="Use VPS Neo4j (requires SSH tunnel: ssh -L 7474:127.0.0.1:7474 root@157.180.73.53)",
    )

    args = parser.parse_args()

    # Build query based on args
    if args.count_nodes:
        cypher = "MATCH (n) RETURN labels(n) as type, count(*) as count ORDER BY count DESC"
    elif args.find_class:
        cypher = (
            f"MATCH (c:RepoClass) WHERE c.name CONTAINS '{args.find_class}' RETURN c.name, c.file, c.lines LIMIT 20"
        )
    elif args.find_file:
        cypher = f"MATCH (f:RepoFile) WHERE f.path CONTAINS '{args.find_file}' RETURN f.path, f.lines LIMIT 20"
    elif args.find_tool:
        cypher = (
            f"MATCH (t:Tool) WHERE t.name CONTAINS '{args.find_tool}' RETURN t.name, t.description, t.category LIMIT 20"
        )
    elif args.list_tools:
        cypher = "MATCH (t:Tool) RETURN t.name, t.category, t.description ORDER BY t.name LIMIT 100"
    elif args.list_agents:
        cypher = "MATCH (a:Agent) RETURN a.name, a.role, a.tools LIMIT 20"
    elif args.list_kernels:
        cypher = "MATCH (k:Kernel) RETURN k.name, k.ring, k.version LIMIT 20"
    elif args.query:
        cypher = args.query
    else:
        parser.print_help()
        return 1

    # Execute query
    result = query_neo4j(cypher)

    if args.raw:
        # Raw JSON output to stdout for programmatic use
        sys.stdout.write(json.dumps(result, indent=2, default=str) + "\n")
    else:
        logger.info("neo4j_query_result", query=cypher[:100], result=format_results(result))

    return 0


if __name__ == "__main__":
    sys.exit(main())

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
        "cli",
        "filesystem",
        "intelligence",
        "logging",
        "messaging",
        "serialization",
    ],
    "keywords": ["cursor", "format", "neo4j", "query", "results"],
    "business_value": "File locations Class definitions Import relationships Tool registrations python scripts/cursor_neo4j",
    "last_modified": "2026-01-14T12:10:12Z",
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
