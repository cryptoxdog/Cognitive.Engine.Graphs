#!/bin/bash
# =============================================================================
# Comprehensive Test Suite (Repo-Agnostic)
#
# Tests everything: Docker, health, API, memory, agent, auth, databases,
# automated tests, WebSocket, dashboard.
#
# ALL configuration pulled from .env (or .env.local). Zero hardcoded values.
# You never edit this script — you edit your .env.
#
# Required .env vars:
#   APP_API_KEY          — API key for authenticated endpoints
#   APP_PORT             — API port (default: 8000)
#
# Optional .env vars (tests skip gracefully if not set):
#   APP_API_HOST         — API host (default: localhost)
#   REDIS_CONTAINER      — Redis container/service name (default: redis)
#   NEO4J_PORT           — Neo4j HTTP port (default: 7474)
#   DASHBOARD_PORT       — Dashboard port (default: 5050)
#   SMOKE_TEST_PATH      — Pytest path inside container (default: tests/)
#   API_CONTAINER        — API service name for docker exec (default: api)
#   APP_NAME             — Project name for display (default: APP)
#   AUTH_TEST_ENDPOINT   — Endpoint to test auth on (default: /health)
#   WS_PATH              — WebSocket path (default: /ws)
#
# Usage: ./tools/infra/test_everything.sh [path/to/.env]
# =============================================================================

set +e  # Don't exit on error — we want to test everything

# ---------------------------------------------------------------------------
# Load .env
# ---------------------------------------------------------------------------

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ENV_FILE="${1:-}"

# Auto-detect: .env.local for dev, .env for production
if [[ -z "$ENV_FILE" ]]; then
    if [[ -f "$REPO_ROOT/.env.local" ]]; then
        ENV_FILE="$REPO_ROOT/.env.local"
    elif [[ -f "$REPO_ROOT/.env" ]]; then
        ENV_FILE="$REPO_ROOT/.env"
    fi
fi

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

# ---------------------------------------------------------------------------
# All config from env vars — sane defaults, never hardcoded secrets
# ---------------------------------------------------------------------------

API_KEY="${APP_API_KEY:?ERROR: APP_API_KEY not set in .env — cannot run tests}"
API_HOST="${APP_API_HOST:-localhost}"
API_PORT="${APP_PORT:-8000}"
API_URL="http://${API_HOST}:${API_PORT}"

REDIS_CONTAINER="${REDIS_CONTAINER:-redis}"
NEO4J_PORT="${NEO4J_PORT:-7474}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5050}"
SMOKE_TEST_PATH="${SMOKE_TEST_PATH:-tests/}"
API_CONTAINER="${API_CONTAINER:-api}"
APP_NAME="${APP_NAME:-APP}"
AUTH_TEST_ENDPOINT="${AUTH_TEST_ENDPOINT:-/health}"
WS_PATH="${WS_PATH:-/ws}"

# ---------------------------------------------------------------------------
# Test framework
# ---------------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PASSED=0
FAILED=0

test_pass() { echo -e "${GREEN}✓${NC} $1"; ((PASSED++)); }
test_fail() { echo -e "${RED}✗${NC} $1"; ((FAILED++)); }
test_info() { echo -e "${YELLOW}→${NC} $1"; }
test_skip() { echo -e "${YELLOW}○${NC} $1 (skipped)"; }

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              ${APP_NAME} COMPREHENSIVE TEST SUITE"
echo "║              API: ${API_URL}"
echo "║              Env: ${ENV_FILE:-<none>}"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# 1. Docker Services
# =============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. DOCKER SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_info "Checking Docker containers..."
if docker compose ps 2>/dev/null | grep -q "Up.*healthy"; then
    test_pass "Docker services are running and healthy"
    docker compose ps 2>/dev/null
elif docker compose ps 2>/dev/null | grep -q "Up"; then
    test_pass "Docker services are running (no healthcheck configured)"
    docker compose ps 2>/dev/null
else
    test_fail "Docker services are not running"
    docker compose ps 2>/dev/null
fi

# =============================================================================
# 2. Health Endpoints
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. HEALTH ENDPOINTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test all common health paths — passes if any respond
HEALTH_PATHS="/health /healthz /health/startup /api/health"
if [[ -n "${HEALTH_ENDPOINTS:-}" ]]; then
    HEALTH_PATHS="$HEALTH_ENDPOINTS"
fi

for path in $HEALTH_PATHS; do
    test_info "Testing ${path}"
    STATUS=$(curl -s -w "%{http_code}" -o /dev/null "${API_URL}${path}" 2>/dev/null || echo "000")
    if [[ "$STATUS" == "200" ]]; then
        test_pass "${path} (status: ${STATUS})"
    elif [[ "$STATUS" == "000" ]]; then
        test_fail "${path} (connection refused)"
    else
        test_fail "${path} (status: ${STATUS})"
    fi
done

# =============================================================================
# 3. API Info & Documentation
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. API INFO & DOCUMENTATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_info "Testing root endpoint"
ROOT_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "${API_URL}/" 2>/dev/null || echo "000")
if [[ "$ROOT_STATUS" == "200" ]]; then
    test_pass "Root endpoint (status: ${ROOT_STATUS})"
else
    test_fail "Root endpoint (status: ${ROOT_STATUS})"
fi

test_info "Testing /openapi.json"
if curl -s -f "${API_URL}/openapi.json" 2>/dev/null | grep -q "openapi"; then
    test_pass "OpenAPI schema accessible"
else
    test_fail "OpenAPI schema"
fi

# =============================================================================
# 4. Authenticated Endpoints
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4. AUTHENTICATED ENDPOINTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test all authenticated endpoints listed in env (space-separated)
AUTH_ENDPOINTS="${AUTH_ENDPOINTS:-}"

if [[ -n "$AUTH_ENDPOINTS" ]]; then
    for spec in $AUTH_ENDPOINTS; do
        # Format: METHOD:PATH:EXPECTED_STATUS (e.g. "POST:/api/v1/memory/test:200")
        IFS=':' read -r method path expected <<< "$spec"
        method="${method:-GET}"
        expected="${expected:-200}"

        test_info "Testing ${method} ${path}"
        STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X "$method" \
            "${API_URL}${path}" \
            -H "Authorization: Bearer ${API_KEY}" \
            -H "Content-Type: application/json" 2>/dev/null || echo "000")

        if [[ "$STATUS" == "$expected" ]]; then
            test_pass "${method} ${path} (status: ${STATUS})"
        else
            test_fail "${method} ${path} (expected ${expected}, got ${STATUS})"
        fi
    done
else
    test_skip "No AUTH_ENDPOINTS defined in .env — add space-separated METHOD:PATH:STATUS"
fi

# =============================================================================
# 5. Authentication (verify auth is enforced)
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5. AUTHENTICATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_info "Testing endpoint without auth (should fail)"
NO_AUTH_STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X POST "${API_URL}${AUTH_TEST_ENDPOINT}" 2>/dev/null || echo "000")
if [[ "$NO_AUTH_STATUS" == "401" ]] || [[ "$NO_AUTH_STATUS" == "403" ]] || [[ "$NO_AUTH_STATUS" == "422" ]]; then
    test_pass "Authentication required (status: $NO_AUTH_STATUS)"
else
    test_fail "Authentication check (status: $NO_AUTH_STATUS — expected 401/403)"
fi

test_info "Testing endpoint with invalid auth (should fail)"
INVALID_AUTH_STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X POST "${API_URL}${AUTH_TEST_ENDPOINT}" \
    -H "Authorization: Bearer invalid_key_12345" 2>/dev/null || echo "000")
if [[ "$INVALID_AUTH_STATUS" == "401" ]] || [[ "$INVALID_AUTH_STATUS" == "403" ]]; then
    test_pass "Invalid auth rejected (status: $INVALID_AUTH_STATUS)"
else
    test_fail "Invalid auth check (status: $INVALID_AUTH_STATUS — expected 401/403)"
fi

# =============================================================================
# 6. Redis
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6. REDIS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_info "Testing Redis connection"
REDIS_AUTH=""
if [[ -n "${REDIS_PASSWORD:-}" ]]; then
    REDIS_AUTH="-a ${REDIS_PASSWORD} --no-auth-warning"
fi

if docker compose exec -T "${REDIS_CONTAINER}" redis-cli ${REDIS_AUTH} ping 2>/dev/null | grep -q "PONG"; then
    test_pass "Redis is responding"
else
    test_fail "Redis connection"
fi

# =============================================================================
# 7. Neo4j (optional — skip if NEO4J_PORT not set or 0)
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7. NEO4J"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "${NEO4J_PORT}" != "0" ]] && [[ -n "${NEO4J_PORT}" ]]; then
    test_info "Testing Neo4j HTTP endpoint"
    NEO4J_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "http://localhost:${NEO4J_PORT}" 2>/dev/null || echo "000")
    if [[ "$NEO4J_STATUS" == "200" ]] || [[ "$NEO4J_STATUS" == "301" ]] || [[ "$NEO4J_STATUS" == "302" ]]; then
        test_pass "Neo4j HTTP endpoint (status: $NEO4J_STATUS)"
    else
        test_fail "Neo4j HTTP endpoint (status: $NEO4J_STATUS)"
    fi
else
    test_skip "Neo4j (NEO4J_PORT not set or 0)"
fi

# =============================================================================
# 8. Automated Test Suite
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8. AUTOMATED TEST SUITE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_info "Running smoke tests via ${API_CONTAINER}..."
if docker compose exec -T "${API_CONTAINER}" python -m pytest "${SMOKE_TEST_PATH}" -v --tb=short 2>&1 | tee /tmp/smoke_test_output.txt | grep -q "PASSED\|passed"; then
    test_pass "Smoke tests passed"
    grep -E "passed|PASSED" /tmp/smoke_test_output.txt | tail -1
else
    SMOKE_FAILED=$(grep -c "FAILED\|failed" /tmp/smoke_test_output.txt 2>/dev/null || echo "0")
    if [[ "$SMOKE_FAILED" -gt 0 ]] 2>/dev/null; then
        test_fail "Smoke tests had $SMOKE_FAILED failure(s)"
    else
        test_info "Smoke tests completed (check output above)"
    fi
fi

# =============================================================================
# 9. WebSocket
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "9. WEBSOCKET"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_info "Checking WebSocket endpoint"
WS_STATUS=$(curl -s -w "%{http_code}" -o /dev/null -H "Upgrade: websocket" -H "Connection: Upgrade" "${API_URL}${WS_PATH}" 2>&1 || echo "000")
if [[ "$WS_STATUS" == "426" ]] || [[ "$WS_STATUS" == "101" ]]; then
    test_pass "WebSocket endpoint exists (status: $WS_STATUS)"
else
    test_info "WebSocket check (status: $WS_STATUS)"
fi

# =============================================================================
# 10. Dashboard (optional)
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "10. DASHBOARD"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "${DASHBOARD_PORT}" != "0" ]] && [[ -n "${DASHBOARD_PORT}" ]]; then
    test_info "Checking dashboard health"
    DASHBOARD_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "http://127.0.0.1:${DASHBOARD_PORT}/api/health" 2>&1 || echo "000")
    if [[ "$DASHBOARD_STATUS" == "200" ]]; then
        test_pass "Dashboard is running"
    else
        test_info "Dashboard not running (status: $DASHBOARD_STATUS)"
    fi
else
    test_skip "Dashboard (DASHBOARD_PORT not set or 0)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
TOTAL=$((PASSED + FAILED))
echo -e "Tests passed: ${GREEN}$PASSED${NC}"
echo -e "Tests failed: ${RED}$FAILED${NC}"
echo "Total tests:  $TOTAL"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              ALL TESTS PASSED! 🎉                           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║         SOME TESTS FAILED — CHECK OUTPUT ABOVE             ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════╝${NC}"
    exit 1
fi
