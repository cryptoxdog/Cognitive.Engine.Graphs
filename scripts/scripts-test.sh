#
!/usr/bin/env bash
--- L9_META ---
l9_schema: 1
origin: l9-template
engine: graph
layer: [scripts]
tags: [L9_TEMPLATE, scripts, test]
owner: platform
status: active
--- /L9_META ---
============================================================================
test.sh — Run test suite with coverage
============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$ROOT_DIR"

SUITE="${1:-all}"
COV_THRESHOLD="${COV_THRESHOLD:-70}"

run_pytest() {
  local args=("$@")
  if command -v poetry >/dev/null 2>&1; then
    poetry run pytest "${args[@]}"
  else
    python3 -m pytest "${args[@]}"
  fi
}

case "$SUITE" in
  unit)
    echo "🧪 Running unit tests..."
    run_pytest tests/unit/ -v --tb=short
    ;;

  compliance)
    echo "🔒 Running compliance tests (CRITICAL)..."
    run_pytest tests/compliance/ -v --strict-markers --tb=long
    ;;

  integration)
    echo "🔗 Running integration tests..."
    run_pytest tests/integration/ -v --tb=short
    ;;

  performance)
    echo "⚡ Running performance benchmarks..."
    run_pytest tests/performance/ -v -m performance --tb=short
    ;;

  all)
    echo "🧪 Running full test suite..."
    run_pytest tests/ -v       --cov=engine       --cov-report=term-missing       --cov-report=html:htmlcov       --cov-fail-under="$COV_THRESHOLD"       --tb=short

    echo ""
    echo "📊 Coverage report: open htmlcov/index.html"
    ;;

  *)
    echo "Usage: test.sh [all|unit|compliance|integration|performance]"
    exit 1
    ;;
esac
