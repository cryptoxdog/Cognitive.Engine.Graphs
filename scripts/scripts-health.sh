#
!/usr/bin/env bash
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [scripts]
tags: [L9_TEMPLATE, scripts, health]
owner: platform
status: active
--- /L9_META ---
============================================================================
health.sh — Health check all services
============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

set -a; source "$ROOT_DIR/.env" 2>/dev/null || true; set +a

API_URL="${1:-http://localhost:${API_PORT:-8000}}"
NEO4J_URL="http://localhost:7474"
REDIS_HOST="${REDIS_HOST:-localhost}"

echo "🏥 L9 Health Check"
echo "=================="

--- API ---
printf "  API (%s)... " "$API_URL"
if HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "${API_URL}/v1/health" 2>/dev/null); then
  if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ UP (${HTTP_CODE})"
  else
    echo "⚠️  DEGRADED (${HTTP_CODE})"
  fi
else
  echo "❌ DOWN"
fi

--- Neo4j ---
printf "  Neo4j (%s)... " "$NEO4J_URL"
if curl -sf "$NEO4J_URL" >/dev/null 2>&1; then
  echo "✅ UP"
else
  echo "❌ DOWN"
fi

--- Redis ---
printf "  Redis (%s:6379)... " "$REDIS_HOST"
if redis-cli -h "$REDIS_HOST" ping 2>/dev/null | grep -q PONG; then
  echo "✅ UP"
elif docker exec "$(docker ps -qf name=redis 2>/dev/null)" redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "✅ UP (via docker)"
else
  echo "❌ DOWN"
fi

echo ""
