#!/usr/bin/env bash
# =============================================================================
# check_env.sh — Validate .env / .env.local
# Reads .env.required (one var name per line) and fails if any are missing/empty.
# Also warns on localhost-in-Docker patterns and placeholder values.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
ENV_FILE="${REPO_ROOT}/.env.local"
[[ ! -f "$ENV_FILE" ]] && ENV_FILE="${REPO_ROOT}/.env"
REQUIRED_FILE="${REPO_ROOT}/.env.required"

echo "🔍 Checking environment: $ENV_FILE"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ No .env or .env.local found. Run: cp .env.template .env.local" >&2
  exit 1
fi

source "$ENV_FILE" 2>/dev/null || true

ERRORS=0

# Check required vars
if [[ -f "$REQUIRED_FILE" ]]; then
  while IFS= read -r var; do
    [[ -z "$var" || "$var" == \#* ]] && continue
    val="${!var:-}"
    if [[ -z "$val" ]]; then
      echo "  ❌ MISSING: $var" >&2
      ((ERRORS++))
    elif [[ "$val" == "PLACEHOLDER"* || "$val" == "your_"* || "$val" == "TODO"* ]]; then
      echo "  ⚠️  PLACEHOLDER: $var=$val" >&2
      ((ERRORS++))
    else
      echo "  ✓ $var"
    fi
  done < "$REQUIRED_FILE"
fi

# Warn on localhost patterns (common Docker mistake)
if grep -qE 'localhost|127\.0\.0\.1' "$ENV_FILE" 2>/dev/null; then
  echo "  ⚠️  WARNING: 'localhost' detected — use Docker service names inside containers"
fi

if [[ $ERRORS -gt 0 ]]; then
  echo ""
  echo "❌ $ERRORS error(s) found in environment config." >&2
  exit 1
fi

echo "✅ Environment OK"
