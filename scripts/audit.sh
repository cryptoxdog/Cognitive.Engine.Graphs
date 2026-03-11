# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: graph
# layer: [scripts, audit]
# tags: [L9_TEMPLATE, scripts, audit]
# owner: platform
# status: active
# --- /L9_META ---
#
!/usr/bin/env bash
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [scripts, audit]
tags: [L9_TEMPLATE, scripts, audit]
owner: platform
status: active
--- /L9_META ---
set -euo pipefail
python tools/audit_engine.py
