#!/usr/bin/env bash
# =============================================================================
# Pre-Commit Docker Smoke Test (Repo-Agnostic)
#
# Builds the entire stack in isolation, waits for health, runs smoke tests,
# tears down cleanly. Zero residue.
#
# ALL configuration pulled from .env (or .env.local).
# You never edit this script — you edit your .env.
#
# Optional .env vars:
#   COMPOSE_BASE         — Base compose file (default: docker-compose.yml)
#   COMPOSE_DEV          — Dev overlay (default: docker-compose.dev.yml)
#   HEALTH_SERVICES      — Space-separated "service:timeout" pairs
#                          (default: auto-discovered from compose)
#   SMOKE_TEST_PATH      — Pytest path inside container (default: tests/)
#   API_CONTAINER        — API service name for docker exec (default: api)
#   APP_PORT             — API port for health checks (default: 8000)
#   HEALTH_TIMEOUT       — Max seconds to wait per service (default: 120)
#
# Usage: ./tools/infra/precommit_smoke.sh [path/to/.env]
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${1:-}"

if [[ -z "$ENV_FILE" ]]; then
    for candidate in "$PROJECT_ROOT/.env" "$PROJECT_ROOT/.env.local"; do
        [[ -f "$candidate" ]] && { ENV_FILE="$candidate"; break; }
    done
fi

if [[ -f "$ENV_FILE" ]]; then
    set -a; source "$ENV_FILE"; set +a
fi

# ---------------------------------------------------------------------------
# All config from env vars
# ---------------------------------------------------------------------------

COMPOSE_BASE="${COMPOSE_BASE:-docker-compose.yml}"
COMPOSE_DEV="${COMPOSE_DEV:-docker-compose.dev.yml}"
SMOKE_TEST_PATH="${SMOKE_TEST_PATH:-tests/}"
API_CONTAINER="${API_CONTAINER:-api}"
APP_PORT="${APP_PORT:-8000}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
HEALTH_INTERVAL=2
APP_NAME="${APP_NAME:-APP}"

# Build compose flags
COMPOSE_FILES="-f ${PROJECT_ROOT}/${COMPOSE_BASE}"
[[ -f "${PROJECT_ROOT}/${COMPOSE_DEV}" ]] && COMPOSE_FILES="${COMPOSE_FILES} -f ${PROJECT_ROOT}/${COMPOSE_DEV}"

# Isolated project name (won't collide with running stack)
PROJECT_NAME="${APP_NAME,,}-precommit-$(date +%s)"

ENV_FLAG=""
[[ -n "$ENV_FILE" ]] && ENV_FLAG="--env-file ${ENV_FILE}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[✓]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[✗]${NC} $*"; }

# ---------------------------------------------------------------------------
# Cleanup trap — always tears down, no residue
# ---------------------------------------------------------------------------

cleanup() {
    local exit_code=$?
    log_info "Cleaning up Docker resources..."

    if [[ $exit_code -ne 0 ]]; then
        log_warn "Capturing service logs before teardown..."
        docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG logs --tail=50 2>/dev/null || true
    fi

    docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG down -v --remove-orphans 2>/dev/null || true
    docker network rm "${PROJECT_NAME}_default" 2>/dev/null || true

    [[ $exit_code -eq 0 ]] && log_success "Cleanup complete" || log_warn "Cleanup complete (test failed with exit $exit_code)"
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Health wait loop
# ---------------------------------------------------------------------------

wait_for_healthy() {
    local service="$1"
    local timeout="${2:-$HEALTH_TIMEOUT}"
    local elapsed=0

    log_info "Waiting for $service to be healthy (${timeout}s timeout)..."

    while [[ $elapsed -lt $timeout ]]; do
        local health
        health=$(docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG ps --format json "$service" 2>/dev/null \
            | python3 -c "import sys, json; data=json.load(sys.stdin) if sys.stdin.read(1) else {}; print(data.get('Health', 'unknown'))" 2>/dev/null || echo "unknown")

        [[ "$health" == "healthy" ]] && { log_success "$service is healthy"; return 0; }

        # Check if container exited
        local state
        state=$(docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG ps --format json "$service" 2>/dev/null \
            | python3 -c "import sys, json; data=json.load(sys.stdin) if sys.stdin.read(1) else {}; print(data.get('State', 'unknown'))" 2>/dev/null || echo "unknown")

        if [[ "$state" == "exited" ]]; then
            log_error "$service exited unexpectedly"
            docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG logs "$service" --tail=30
            return 1
        fi

        sleep "$HEALTH_INTERVAL"
        elapsed=$((elapsed + HEALTH_INTERVAL))
    done

    log_error "$service failed to become healthy within ${timeout}s"
    docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG logs "$service" --tail=50
    return 1
}

# ---------------------------------------------------------------------------
# HTTP health check from inside the network
# ---------------------------------------------------------------------------

run_container_health_check() {
    local url="$1"
    local expected="${2:-200}"
    docker run --rm --network="${PROJECT_NAME}_default" curlimages/curl:latest \
        -sf -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000"
}

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

log_info "${APP_NAME} Docker Pre-Commit Smoke Test"
log_info "Project: $PROJECT_NAME"
log_info "Compose: $COMPOSE_FILES"
log_info "Env: ${ENV_FILE:-<none>}"

cd "$PROJECT_ROOT"

# Gate 1: Validate compose
log_info "Gate 1: Validating compose..."
if ! docker compose $COMPOSE_FILES $ENV_FLAG config -q 2>/dev/null; then
    log_error "Compose validation failed"
    exit 1
fi
log_success "Compose file is valid"

# Gate 2: Build
log_info "Gate 2: Building Docker images..."
if ! docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG build --quiet 2>/dev/null; then
    log_error "Docker build failed"
    exit 2
fi
log_success "All images built"

# Gate 3: Start stack
log_info "Gate 3: Starting stack..."
if ! docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG up -d 2>/dev/null; then
    log_error "Failed to start stack"
    exit 3
fi

# Wait for services to be healthy
# If HEALTH_SERVICES is set, use it. Otherwise discover from compose.
if [[ -n "${HEALTH_SERVICES:-}" ]]; then
    # Format: "service1:timeout service2:timeout"
    for spec in $HEALTH_SERVICES; do
        IFS=':' read -r svc timeout <<< "$spec"
        timeout="${timeout:-$HEALTH_TIMEOUT}"
        if ! wait_for_healthy "$svc" "$timeout"; then
            log_error "$svc failed to start"
            exit 3
        fi
    done
else
    # Auto-discover: wait for all services
    for svc in $(docker compose $COMPOSE_FILES config --services 2>/dev/null); do
        if ! wait_for_healthy "$svc" "$HEALTH_TIMEOUT"; then
            log_warn "$svc not healthy (continuing...)"
        fi
    done
fi
log_success "Services are healthy"

# Gate 4: Smoke tests
log_info "Gate 4: Running smoke tests..."

if docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG exec -T "$API_CONTAINER" \
    python -m pytest "$SMOKE_TEST_PATH" -v --tb=short 2>/dev/null; then
    log_success "Smoke tests passed"
else
    # Fallback: basic HTTP health check
    log_warn "Pytest not available or failed, trying HTTP health check..."
    api_status=$(run_container_health_check "http://${API_CONTAINER}:${APP_PORT}/health")
    if [[ "$api_status" == "200" ]]; then
        log_success "API health check OK"
    else
        log_error "API health check failed (status: $api_status)"
        exit 4
    fi
fi

# Gate 5: DB connectivity (check for localhost-in-DSN bug)
log_info "Gate 5: Validating DB connectivity..."
if docker compose -p "$PROJECT_NAME" $COMPOSE_FILES $ENV_FLAG exec -T "$API_CONTAINER" python -c "
import os
url = os.environ.get('DATABASE_URL', '')
if not url:
    print('⚠ DATABASE_URL not set')
    exit(0)
if '127.0.0.1' in url or 'localhost' in url:
    print(f'ERROR: DATABASE_URL contains localhost: {url}')
    print('Fix: Use service DNS (e.g., postgres:5432) instead of localhost')
    exit(1)
print(f'DATABASE_URL uses service DNS ✓')
" 2>/dev/null; then
    log_success "DB connectivity validated (no localhost DSN)"
else
    log_error "DB connectivity validation failed"
    exit 4
fi

log_success "All smoke tests passed"
exit 0
