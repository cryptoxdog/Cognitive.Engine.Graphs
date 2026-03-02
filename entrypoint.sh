#
!/bin/sh
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [docker]
tags: [L9_TEMPLATE, docker, entrypoint]
owner: platform
status: active
--- /L9_META ---
─────────────────────────────────────────────────────────────
L9 Graph Cognitive Engine — Container Entrypoint
─────────────────────────────────────────────────────────────
set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║  L9 Graph Cognitive Engine                           ║"
echo "║  Starting uvicorn on 0.0.0.0:8000                   ║"
echo "╚══════════════════════════════════════════════════════╝"

Wait for Neo4j to be ready (belt + suspenders beyond depends_on)
echo "Waiting for Neo4j..."
for i in $(seq 1 30); do
    python -c "
from neo4j import GraphDatabase
import os
uri = os.getenv('PLASTICOS_NEO4J_URI', 'bolt://neo4j:7687')
user = os.getenv('PLASTICOS_NEO4J_USER', 'neo4j')
pw = os.getenv('PLASTICOS_NEO4J_PASSWORD', 'password')
d = GraphDatabase.driver(uri, auth=(user, pw))
d.verify_connectivity()
d.close()
print('Neo4j ready')
" 2>/dev/null && break
    echo "  attempt $i/30..."
    sleep 2
done

Launch uvicorn
exec uvicorn engine.api.app:create_app \
    --factory \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level ${PLASTICOS_LOG_LEVEL:-info} \
    --access-log \
    --timeout-keep-alive 30 \
    "$@"
