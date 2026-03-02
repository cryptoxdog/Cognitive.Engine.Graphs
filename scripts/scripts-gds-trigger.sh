#
!/usr/bin/env bash
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [scripts]
tags: [L9_TEMPLATE, scripts, gds]
owner: platform
status: active
--- /L9_META ---
============================================================================
gds-trigger.sh — Manually trigger GDS algorithm jobs
============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

set -a; source "$ROOT_DIR/.env" 2>/dev/null || true; set +a

API_URL="${API_URL:-http://localhost:${API_PORT:-8000}}"
DOMAIN="${1:?Usage: gds-trigger.sh <domain> [job_name]}"
JOB="${2:-all}"

echo "⚙️  Triggering GDS jobs for ${DOMAIN}"

if [ "$JOB" = "all" ]; then
  curl -sf -X POST "${API_URL}/v1/admin/gds/trigger-all"     -H "X-Domain-Key: ${DOMAIN}" | python3 -m json.tool
else
  curl -sf -X POST "${API_URL}/v1/admin/gds/trigger/${JOB}"     -H "X-Domain-Key: ${DOMAIN}" | python3 -m json.tool
fi
