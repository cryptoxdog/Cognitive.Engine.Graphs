#!/usr/bin/env bash
# =============================================================================
# Deep MRI — Production VPS Diagnostics (Repo-Agnostic)
#
# 10-section diagnostic scan. ALL configuration pulled from .env.
# You never edit this script — you edit your .env.
#
# Required .env vars:
#   POSTGRES_USER        — Postgres user
#   POSTGRES_DB          — Postgres database name
#
# Optional .env vars:
#   APP_PORT             — API port (default: 8000)
#   APP_API_KEY          — API key for authenticated health checks
#   REDIS_PASSWORD       — Redis password (omit for no-auth)
#   NEO4J_PASSWORD       — Neo4j password
#   NEO4J_PORT           — Neo4j HTTP port (default: 7474)
#   NEO4J_BOLT_PORT      — Neo4j Bolt port (default: 7687)
#   PROMETHEUS_PORT      — Prometheus port (default: 9090)
#   GRAFANA_PORT         — Grafana port (default: 3000)
#   JAEGER_PORT          — Jaeger UI port (default: 16686)
#   MCP_MEMORY_PORT      — MCP Memory health port (default: 9002)
#   POSTGRES_CONTAINER   — Postgres service name (default: postgres)
#   REDIS_CONTAINER      — Redis service name (default: redis)
#   APP_NAME             — Project name for display (default: APP)
#
# Usage: ./tools/infra/deep_mri.sh [path/to/.env]
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ENV_FILE="${1:-}"

if [[ -z "$ENV_FILE" ]]; then
    if [[ -f "$REPO_ROOT/.env" ]]; then
        ENV_FILE="$REPO_ROOT/.env"
    elif [[ -f "$REPO_ROOT/.env.local" ]]; then
        ENV_FILE="$REPO_ROOT/.env.local"
    fi
fi

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

# ---------------------------------------------------------------------------
# All config from env vars
# ---------------------------------------------------------------------------

APP_NAME="${APP_NAME:-APP}"
APP_PORT="${APP_PORT:-8000}"
APP_API_KEY="${APP_API_KEY:-}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_DB="${POSTGRES_DB:-postgres}"
PG_CONTAINER="${POSTGRES_CONTAINER:-postgres}"
REDIS_PW="${REDIS_PASSWORD:-}"
REDIS_CTR="${REDIS_CONTAINER:-redis}"
NEO4J_PW="${NEO4J_PASSWORD:-}"
NEO4J_HTTP="${NEO4J_PORT:-7474}"
NEO4J_BOLT="${NEO4J_BOLT_PORT:-7687}"
PROM_PORT="${PROMETHEUS_PORT:-9090}"
GRAF_PORT="${GRAFANA_PORT:-3000}"
JAEG_PORT="${JAEGER_PORT:-16686}"
MCP_PORT="${MCP_MEMORY_PORT:-9002}"

# Build port list dynamically from what's configured
MRI_PORTS="${APP_PORT} 5432 6379"
[[ "${NEO4J_HTTP}" != "0" ]] && MRI_PORTS="${MRI_PORTS} ${NEO4J_HTTP} ${NEO4J_BOLT}"
[[ "${PROM_PORT}" != "0" ]] && MRI_PORTS="${MRI_PORTS} ${PROM_PORT}"
[[ "${GRAF_PORT}" != "0" ]] && MRI_PORTS="${MRI_PORTS} ${GRAF_PORT}"
[[ "${JAEG_PORT}" != "0" ]] && MRI_PORTS="${MRI_PORTS} ${JAEG_PORT}"
[[ "${MCP_PORT}" != "0" ]] && MRI_PORTS="${MRI_PORTS} ${MCP_PORT}"

# ---------------------------------------------------------------------------

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              ${APP_NAME} Deep MRI — Production VPS"
echo "║              Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "╚══════════════════════════════════════════════════════════════╝"

# ==========================================================================
echo ""
echo "━━━ 1. SYSTEM OVERVIEW ━━━"
echo ""
echo "Hostname:      $(hostname)"
echo "Uptime:        $(uptime -p 2>/dev/null || uptime)"
echo "Kernel:        $(uname -r)"
echo "Load Average:  $(uptime | awk -F'load average:' '{print $2}')"

# ==========================================================================
echo ""
echo "━━━ 2. DOCKER INFRASTRUCTURE ━━━"
echo ""
cd "$REPO_ROOT"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}" 2>/dev/null | column -t || echo "docker compose ps failed"
echo ""
echo "Docker Daemon Status:"
systemctl status docker --no-pager 2>/dev/null | grep -E "Active|Memory|Tasks" || echo "N/A"

# ==========================================================================
echo ""
echo "━━━ 3. CONTAINER RESOURCE USAGE ━━━"
echo ""
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" \
    $(docker ps --filter "label=com.docker.compose.project" --format "{{.Names}}" 2>/dev/null) 2>/dev/null || echo "N/A"

# ==========================================================================
echo ""
echo "━━━ 4. NETWORK CONNECTIVITY (127.0.0.1 Ports) ━━━"
echo ""
for port in $MRI_PORTS; do
    if nc -z 127.0.0.1 "$port" 2>/dev/null; then
        echo "  Port $port: OPEN"
    else
        echo "  Port $port: CLOSED"
    fi
done

# ==========================================================================
echo ""
echo "━━━ 5. DATABASE SUBSTRATE HEALTH ━━━"
echo ""

echo "PostgreSQL:"
docker compose exec -T "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" \
    -c "SELECT version();" 2>/dev/null | head -3 || echo "  Query failed"
docker compose exec -T "$PG_CONTAINER" psql -U "$PG_USER" -d "$PG_DB" \
    -c "SELECT count(*) as tables FROM information_schema.tables WHERE table_schema='public';" \
    2>/dev/null | tail -2 || echo "  Table count failed"

echo ""
echo "Redis:"
REDIS_CLI_AUTH=""
[[ -n "$REDIS_PW" ]] && REDIS_CLI_AUTH="-a $REDIS_PW --no-auth-warning"
docker compose exec -T "$REDIS_CTR" redis-cli $REDIS_CLI_AUTH PING 2>/dev/null || echo "  PING failed"
docker compose exec -T "$REDIS_CTR" redis-cli $REDIS_CLI_AUTH INFO stats 2>/dev/null \
    | grep -E "total_commands_processed|instantaneous_ops_per_sec" || echo "  Stats failed"

if [[ "${NEO4J_HTTP}" != "0" ]]; then
    echo ""
    echo "Neo4j:"
    if [[ -n "$NEO4J_PW" ]]; then
        curl -s -u "neo4j:${NEO4J_PW}" "http://127.0.0.1:${NEO4J_HTTP}" 2>/dev/null \
            | grep -q "neo4j_version" && echo "  HTTP endpoint: responsive" || echo "  HTTP endpoint: failed"
    else
        curl -s "http://127.0.0.1:${NEO4J_HTTP}" >/dev/null 2>&1 && echo "  HTTP endpoint: responsive" || echo "  HTTP endpoint: failed"
    fi
fi

if [[ "${MCP_PORT}" != "0" ]]; then
    echo ""
    echo "MCP Memory Server:"
    curl -s "http://127.0.0.1:${MCP_PORT}/health" 2>/dev/null | jq -r '.status' 2>/dev/null || echo "  Health check failed"
fi

# ==========================================================================
echo ""
echo "━━━ 6. API HEALTH (Core Endpoints) ━━━"
echo ""

echo "GET /             $(curl -s "http://127.0.0.1:${APP_PORT}/" 2>/dev/null | jq -r '.status // .name // "?"' 2>/dev/null || echo "Failed")"
echo "GET /health       $(curl -s "http://127.0.0.1:${APP_PORT}/health" 2>/dev/null | jq -r '.status // "?"' 2>/dev/null || echo "Failed")"

# Authenticated endpoints (only if key is set)
if [[ -n "$APP_API_KEY" ]]; then
    HEALTH_SUBS="${HEALTH_ENDPOINTS:-/health/startup /health/services}"
    for ep in $HEALTH_SUBS; do
        echo "GET ${ep}  $(curl -s "http://127.0.0.1:${APP_PORT}${ep}" \
            -H "Authorization: Bearer ${APP_API_KEY}" 2>/dev/null | jq -r '.status // "?"' 2>/dev/null || echo "Failed")"
    done
fi

# ==========================================================================
echo ""
echo "━━━ 7. GIT STATE ━━━"
echo ""
cd "$REPO_ROOT"
echo "Branch:      $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'N/A')"
echo "Commit:      $(git rev-parse --short HEAD 2>/dev/null || echo 'N/A')"
echo "Commit Date: $(git log -1 --format='%cd' --date=iso 2>/dev/null || echo 'N/A')"
echo "Status:      $(git status --short 2>/dev/null | head -10 || echo 'Clean working tree')"

# ==========================================================================
echo ""
echo "━━━ 8. DISK USAGE ━━━"
echo ""
df -h / | tail -1
echo ""
echo "Docker Volumes:"
docker volume ls --format "table {{.Name}}\t{{.Driver}}" 2>/dev/null || echo "  No volumes found"
echo ""
echo "Docker System Usage:"
docker system df 2>/dev/null || echo "  N/A"

# ==========================================================================
echo ""
echo "━━━ 9. RECENT LOGS (Last 10 lines per service) ━━━"
echo ""
# Dynamic: get all services from docker compose
for service in $(docker compose config --services 2>/dev/null); do
    echo "--- ${service} ---"
    docker compose logs --tail=10 "${service}" 2>/dev/null || echo "  No logs available"
done

# ==========================================================================
echo ""
echo "━━━ 10. OBSERVABILITY STACK ━━━"
echo ""

if [[ "${PROM_PORT}" != "0" ]]; then
    echo "Prometheus:  $(curl -s "http://127.0.0.1:${PROM_PORT}/-/healthy" >/dev/null 2>&1 && echo "Healthy" || echo "Unhealthy")"
fi
if [[ "${GRAF_PORT}" != "0" ]]; then
    echo "Grafana:     $(curl -s "http://127.0.0.1:${GRAF_PORT}/api/health" 2>/dev/null | jq -r '.database' 2>/dev/null || echo "Check failed")"
fi
if [[ "${JAEG_PORT}" != "0" ]]; then
    echo "Jaeger:      $(curl -s "http://127.0.0.1:${JAEG_PORT}" 2>/dev/null | grep -q "Jaeger" && echo "UI responsive" || echo "UI failed")"
fi

# ==========================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  MRI COMPLETE"
echo "║"
echo "║  Services:          $(docker compose config --services 2>/dev/null | wc -l | tr -d ' ')"
echo "║  Healthy:           $(docker compose ps --format '{{.Health}}' 2>/dev/null | grep -c 'healthy' || echo '0')"
echo "║  Open Ports:        $(for p in $MRI_PORTS; do nc -z 127.0.0.1 "$p" 2>/dev/null && echo -n "1"; done | wc -c | tr -d ' ')/${echo $MRI_PORTS | wc -w | tr -d ' '}"
echo "║  Timestamp:         $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "╚══════════════════════════════════════════════════════════════╝"
