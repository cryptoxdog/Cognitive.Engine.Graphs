#!/usr/bin/env bash
# ============================================================================
# setup.sh — One-shot local development environment setup
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔧 L9 Engine — Local Setup"
echo "=========================="

# --- Check prerequisites ---
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "❌ docker required"; exit 1; }
command -v docker compose >/dev/null 2>&1 || command -v docker-compose >/dev/null 2>&1 || { echo "❌ docker compose required"; exit 1; }

echo "✅ Prerequisites met"

# --- Create .env if missing ---
if [ ! -f "$ROOT_DIR/.env" ]; then
  cat > "$ROOT_DIR/.env" << 'EOF'
# L9 Engine — Environment Variables
# Consistent across all L9 repos

# Project
L9_PROJECT=l9-engine
L9_ENV=dev

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=devpassword
NEO4J_DATABASE=neo4j

# Redis
REDIS_URL=redis://localhost:6379/0

# API
API_PORT=8000
API_WORKERS=2
DOMAINS_ROOT=./domains
LOG_LEVEL=DEBUG
GDS_ENABLED=true
CORS_ORIGINS=*

# Secrets (dev only — use SSM in prod)
API_SECRET_KEY=dev-secret-key-change-in-prod
EOF
  echo "✅ Created .env (edit as needed)"
else
  echo "⏭️  .env already exists"
fi

# --- Install Python dependencies ---
if command -v poetry >/dev/null 2>&1; then
  echo "📦 Installing via Poetry..."
  cd "$ROOT_DIR" && poetry install
elif [ -f "$ROOT_DIR/requirements.txt" ]; then
  echo "📦 Installing via pip..."
  python3 -m pip install -r "$ROOT_DIR/requirements.txt"
else
  echo "⚠️  No poetry.lock or requirements.txt found — skipping Python deps"
fi

# --- Pull Docker images ---
echo "🐳 Pulling Docker images..."
docker pull neo4j:5.15-enterprise 2>/dev/null || docker pull neo4j:5.15
docker pull redis:7-alpine

# --- Create Docker network ---
docker network create l9-net 2>/dev/null || true

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  ./scripts/dev.sh        # Start local stack"
echo "  ./scripts/test.sh       # Run tests"
echo "  ./scripts/seed.sh       # Load sample data"
