#!/usr/bin/env bash
# =============================================================================
# Environment Variable Checker (Repo-Agnostic)
#
# Validates that all required environment variables are set.
# Run before deployment to catch missing config early.
#
# Variable lists are read from config files:
#   .env.required     — one var per line (deployment fails without these)
#   .env.recommended  — one var per line (optional but recommended)
#
# Falls back to inline defaults if config files don't exist.
#
# Usage: ./tools/infra/check_env.sh [path/to/.env]
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve repo root from git or script location
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$REPO_ROOT/.env}"

if [[ -f "$ENV_FILE" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
fi

# ---------------------------------------------------------------------------
# Load variable lists from config files (one var name per line, # = comment)
# Falls back to empty if no config file exists.
# ---------------------------------------------------------------------------

load_var_list() {
    local config_file="$1"
    if [[ -f "$config_file" ]]; then
        grep -v '^\s*#' "$config_file" | grep -v '^\s*$' | tr '\n' ' '
    fi
}

REQUIRED_VARS=( $(load_var_list "$REPO_ROOT/.env.required") )
RECOMMENDED_VARS=( $(load_var_list "$REPO_ROOT/.env.recommended") )

if [[ ${#REQUIRED_VARS[@]} -eq 0 ]] && [[ ${#RECOMMENDED_VARS[@]} -eq 0 ]]; then
    echo -e "${YELLOW}⚠ No .env.required or .env.recommended found at repo root.${NC}"
    echo "  Create these files with one variable name per line."
    echo "  Example .env.required:"
    echo "    POSTGRES_PASSWORD"
    echo "    DATABASE_URL"
    exit 0
fi

ERRORS=0
WARNINGS=0

echo -e "${GREEN}Checking environment variables...${NC}"
echo ""

# ---------------------------------------------------------------------------
# Check required variables
# ---------------------------------------------------------------------------

if [[ ${#REQUIRED_VARS[@]} -gt 0 ]]; then
    echo -e "${YELLOW}Required Variables:${NC}"
    for var in "${REQUIRED_VARS[@]}"; do
        value="${!var:-}"
        if [[ -z "$value" ]]; then
            echo -e "  ${RED}✗${NC} $var — MISSING"
            ((ERRORS++))
        elif [[ "$value" == *"YOUR_"* ]] || [[ "$value" == *"_HERE"* ]]; then
            echo -e "  ${RED}✗${NC} $var — PLACEHOLDER (needs real value)"
            ((ERRORS++))
        else
            masked="${value:0:4}****${value: -4}"
            echo -e "  ${GREEN}✓${NC} $var = $masked"
        fi
    done
    echo ""
fi

# ---------------------------------------------------------------------------
# Check recommended variables
# ---------------------------------------------------------------------------

if [[ ${#RECOMMENDED_VARS[@]} -gt 0 ]]; then
    echo -e "${YELLOW}Recommended Variables:${NC}"
    for var in "${RECOMMENDED_VARS[@]}"; do
        value="${!var:-}"
        if [[ -z "$value" ]]; then
            echo -e "  ${YELLOW}○${NC} $var — not set (using default)"
            ((WARNINGS++))
        else
            echo -e "  ${GREEN}✓${NC} $var = (set)"
        fi
    done
    echo ""
fi

# ---------------------------------------------------------------------------
# Universal bug detection: localhost in DATABASE_URL inside Docker
# ---------------------------------------------------------------------------

if [[ -n "${DATABASE_URL:-}" ]]; then
    if [[ "$DATABASE_URL" == *"127.0.0.1"* ]] || [[ "$DATABASE_URL" == *"localhost"* ]]; then
        echo -e "${RED}⚠ WARNING: DATABASE_URL contains localhost!${NC}"
        echo -e "  This will fail inside Docker containers."
        echo -e "  Use the service name (e.g. 'postgres') instead of localhost."
        ((WARNINGS++))
    fi
fi

echo ""

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}✗ $ERRORS required variable(s) missing or invalid${NC}"
    echo -e "  Fix these before deploying!"
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo -e "${YELLOW}○ $WARNINGS warning(s) — check recommended variables${NC}"
    exit 0
else
    echo -e "${GREEN}✓ All environment variables OK${NC}"
    exit 0
fi
