#!/usr/bin/env bash
# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: graph
# layer: [scripts]
# tags: [L9_TEMPLATE, scripts, seed]
# owner: platform
# status: active
# --- /L9_META ---
# ============================================================================
# seed.sh — Seed Neo4j with sample data for a domain
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

set -a; source "$ROOT_DIR/.env" 2>/dev/null || true; set +a

DOMAIN="${1:?Usage: seed.sh <domain> [api_url]}"
API_URL="${2:-http://localhost:${API_PORT:-8000}}"
SEED_DIR="$ROOT_DIR/domains/${DOMAIN}/seeds"

if [ ! -d "$SEED_DIR" ]; then
  echo "⚠️  No seeds directory: ${SEED_DIR}"
  echo "   Create JSON seed files in domains/${DOMAIN}/seeds/"
  echo "   Example: domains/${DOMAIN}/seeds/suppliers.json"
  exit 1
fi

echo "🌱 Seeding ${DOMAIN} from ${SEED_DIR}"

for SEED_FILE in "$SEED_DIR"/*.json; do
  [ -f "$SEED_FILE" ] || continue
  ENTITY=$(basename "$SEED_FILE" .json)

  echo "  📦 Syncing ${ENTITY}..."
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}"     -X POST "${API_URL}/v1/sync/${ENTITY}"     -H "Content-Type: application/json"     -H "X-Domain-Key: ${DOMAIN}"     -d @"$SEED_FILE")

  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "  ✅ ${ENTITY} synced (${HTTP_CODE})"
  else
    echo "  ❌ ${ENTITY} failed (${HTTP_CODE})"
  fi
done

echo ""
echo "🌱 Seeding complete for ${DOMAIN}"
