#!/usr/bin/env bash
# =============================================================================
# Local Development Launcher (Repo-Agnostic)
#
# Brings up a FastAPI/uvicorn server with correct env, venv, and dev behavior.
#
# Configuration (override via dev.conf at repo root or env vars):
#   APP_MODULE   — uvicorn app:module path (e.g. "api.main:app")
#   APP_PORT     — port to listen on (default: 8000)
#   APP_HOST     — host to bind to (default: 127.0.0.1)
#   ENV_FILE     — env file to load (default: .env.local)
#   DEV_FLAG     — env var name to set for dev mode (default: LOCAL_DEV)
#   SHOW_VARS    — grep pattern for env vars to display (default: none)
#
# Usage: ./tools/dev/dev_up.sh
# =============================================================================

set -e

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

# Load dev.conf if present (project-specific overrides)
[[ -f "$REPO_ROOT/dev.conf" ]] && source "$REPO_ROOT/dev.conf"

# Defaults (overridden by dev.conf or env vars)
APP_MODULE="${APP_MODULE:?Set APP_MODULE in dev.conf (e.g. 'api.main:app')}"
APP_PORT="${APP_PORT:-8000}"
APP_HOST="${APP_HOST:-127.0.0.1}"
ENV_FILE="${ENV_FILE:-.env.local}"
DEV_FLAG="${DEV_FLAG:-LOCAL_DEV}"
SHOW_VARS="${SHOW_VARS:-}"

echo "🔧 Starting local development environment..."
echo "📁 Repo root: $REPO_ROOT"

# --- Check venv existence ---
if [[ ! -d "venv" ]]; then
    echo "❌ ERROR: venv/ not found. Create it first:"
    echo "   python3 -m venv venv"
    exit 1
fi

echo "🐍 Activating virtual environment..."
source venv/bin/activate

# --- Check env file existence ---
if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ ERROR: $ENV_FILE not found in repo root."
    echo "   Create it with your local development variables."
    exit 1
fi

echo "🔑 Loading environment variables from $ENV_FILE..."
set -a
source "$ENV_FILE"
set +a

# Set dev mode flag
export "${DEV_FLAG}=true"
echo "🔧 $DEV_FLAG=true"

# Show selected env vars (masked)
if [[ -n "$SHOW_VARS" ]]; then
    echo "🔍 Environment loaded:"
    env | grep -E "$SHOW_VARS" | sed 's/=.*/=*** (hidden)/'
fi

# Launch server
echo "🚀 Launching $APP_MODULE on $APP_HOST:$APP_PORT..."
uvicorn "$APP_MODULE" --reload --host "$APP_HOST" --port "$APP_PORT"
