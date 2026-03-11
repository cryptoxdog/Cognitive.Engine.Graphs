#!/bin/sh
# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: "*"
# layer: [scripts]
# tags: [L9_TEMPLATE, scripts, entrypoint, engine-agnostic]
# owner: platform
# status: active
# --- /L9_META ---
# ─────────────────────────────────────────────────────────────
# L9 Chassis — Container Entrypoint (engine-agnostic)
# ─────────────────────────────────────────────────────────────
set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║  L9 Chassis                                          ║"
echo "║  Starting uvicorn on 0.0.0.0:${API_PORT:-8000}                    ║"
echo "╚══════════════════════════════════════════════════════╝"

# Optional: wait for Neo4j if L9_WAIT_FOR_NEO4J is set
if [ "${L9_WAIT_FOR_NEO4J:-false}" = "true" ]; then
    echo "Waiting for Neo4j..."
    for i in $(seq 1 30); do
        python -c "
from neo4j import GraphDatabase
import os
uri = os.getenv('NEO4J_URI', 'bolt://neo4j:7687')
user = os.getenv('NEO4J_USERNAME', 'neo4j')
pw = os.getenv('NEO4J_PASSWORD', 'password')
d = GraphDatabase.driver(uri, auth=(user, pw))
d.verify_connectivity()
d.close()
print('Neo4j ready')
" 2>/dev/null && break
        echo "  attempt $i/30..."
        sleep 2
    done
fi

# Launch uvicorn — chassis.app:create_app resolves engine via L9_LIFECYCLE_HOOK
exec uvicorn chassis.app:create_app \
    --factory \
    --host 0.0.0.0 \
    --port ${API_PORT:-8000} \
    --log-level ${LOG_LEVEL:-info} \
    --access-log \
    --timeout-keep-alive 30 \
    "$@"
