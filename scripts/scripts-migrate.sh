#!/usr/bin/env bash
# ============================================================================
# migrate.sh — Create Neo4j constraints and indexes from domain spec
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

set -a; source "$ROOT_DIR/.env" 2>/dev/null || true; set +a

DOMAIN="${1:?Usage: migrate.sh <domain>}"
NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
NEO4J_USER="${NEO4J_USERNAME:-neo4j}"
NEO4J_PASS="${NEO4J_PASSWORD:-devpassword}"

echo "🔄 Running migrations for ${DOMAIN}"
echo "   Target: ${NEO4J_URI}"

# Run via cypher-shell if available
if command -v cypher-shell >/dev/null 2>&1; then
  CYPHER_CMD="cypher-shell -u $NEO4J_USER -p $NEO4J_PASS -a $NEO4J_URI"
else
  CYPHER_CMD="docker exec -i $(docker ps -qf name=neo4j) cypher-shell -u $NEO4J_USER -p $NEO4J_PASS"
fi

# Read constraints from domain spec or migration files
MIGRATION_DIR="$ROOT_DIR/domains/${DOMAIN}/migrations"

if [ -d "$MIGRATION_DIR" ]; then
  for CYPHER_FILE in "$MIGRATION_DIR"/*.cypher; do
    [ -f "$CYPHER_FILE" ] || continue
    echo "  📋 Running $(basename "$CYPHER_FILE")..."
    $CYPHER_CMD < "$CYPHER_FILE"
    echo "  ✅ $(basename "$CYPHER_FILE") applied"
  done
else
  echo "  ⚠️  No migrations directory: ${MIGRATION_DIR}"
  echo "  Creating default constraints..."

  # Default uniqueness constraints
  echo "CREATE CONSTRAINT IF NOT EXISTS FOR (n:${DOMAIN}) REQUIRE n.id IS UNIQUE;" | $CYPHER_CMD 2>/dev/null || true
  echo "  ✅ Default constraints applied"
fi

echo ""
echo "🔄 Migrations complete for ${DOMAIN}"
