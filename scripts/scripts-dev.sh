#!/usr/bin/env bash
# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: graph
# layer: [scripts]
# tags: [L9_TEMPLATE, scripts, dev]
# owner: platform
# status: active
# --- /L9_META ---
# ============================================================================
# dev.sh — Start local development stack
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Source env
set -a; source "$ROOT_DIR/.env" 2>/dev/null || true; set +a

ACTION="${1:-up}"

case "$ACTION" in
  up)
    echo "🚀 Starting L9 dev stack..."
    docker compose -f "$ROOT_DIR/docker-compose.yml" up -d

    echo ""
    echo "Waiting for Neo4j..."
    for i in $(seq 1 30); do
      if curl -sf http://localhost:7474 >/dev/null 2>&1; then
        echo "✅ Neo4j ready"
        break
      fi
      sleep 2
    done

    echo ""
    echo "Starting API..."
    cd "$ROOT_DIR"
    if command -v poetry >/dev/null 2>&1; then
      poetry run uvicorn engine.api.app:app --reload --host 0.0.0.0 --port "${API_PORT:-8000}" &
    else
      python3 -m uvicorn engine.api.app:app --reload --host 0.0.0.0 --port "${API_PORT:-8000}" &
    fi

    echo ""
    echo "🎉 Stack running:"
    echo "  API:    http://localhost:${API_PORT:-8000}"
    echo "  Neo4j:  http://localhost:7474 (bolt://localhost:7687)"
    echo "  Redis:  localhost:6379"
    echo ""
    echo "  Stop:   ./scripts/dev.sh down"
    ;;

  down)
    echo "🛑 Stopping L9 dev stack..."
    docker compose -f "$ROOT_DIR/docker-compose.yml" down
    pkill -f "uvicorn engine.api.app" 2>/dev/null || true
    echo "✅ Stopped"
    ;;

  logs)
    docker compose -f "$ROOT_DIR/docker-compose.yml" logs -f
    ;;

  *)
    echo "Usage: dev.sh [up|down|logs]"
    exit 1
    ;;
esac
