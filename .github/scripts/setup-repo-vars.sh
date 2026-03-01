#!/usr/bin/env bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Universal CI/CD Pack — Automated Variable Setup
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# VERSION: 1.0.0
# USAGE: bash .github/scripts/setup-repo-vars.sh [path-to-env-file]
# REQUIRES: GitHub CLI (gh) authenticated
# INSTALL: https://cli.github.com/
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
set -euo pipefail

ENV_FILE="${1:-.github/env.template}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Universal CI/CD Pack — Repository Variable Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Check dependencies ──
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ File not found: $ENV_FILE"
  echo ""
  echo "Usage: $0 [path-to-env-file]"
  echo "Example: $0 .github/my-config.env"
  exit 1
fi

if ! command -v gh &> /dev/null; then
  echo "❌ GitHub CLI (gh) is required but not installed."
  echo ""
  echo "Install: https://cli.github.com/"
  echo "  macOS:   brew install gh"
  echo "  Linux:   sudo apt install gh"
  echo "  Windows: winget install --id GitHub.cli"
  exit 1
fi

# ── Get repository info ──
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || echo "")

if [ -z "$REPO" ]; then
  echo "❌ Not in a GitHub repository or gh not authenticated."
  echo ""
  echo "Authenticate: gh auth login"
  exit 1
fi

echo "📦 Target Repository: $REPO"
echo "📄 Config File:       $ENV_FILE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

COUNT=0
SKIPPED=0

while IFS= read -r line; do
  # Skip comments and empty lines
  [[ "$line" =~ ^#.*$ ]] && continue
  [[ "$line" =~ ^[[:space:]]*$ ]] && continue

  # Parse KEY=VALUE
  if [[ "$line" =~ ^([A-Z_]+)=(.*)$ ]]; then
    KEY="${BASH_REMATCH[1]}"
    VALUE="${BASH_REMATCH[2]}"

    # Skip if no value
    if [ -z "$VALUE" ]; then
      ((SKIPPED++))
      continue
    fi

    echo "  Setting: $KEY = $VALUE"
    
    if gh variable set "$KEY" --body "$VALUE" 2>/dev/null; then
      ((COUNT++))
    else
      echo "  ⚠️  Failed to set $KEY (may already exist or need permissions)"
    fi
  fi

done < "$ENV_FILE"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Results:"
echo "   Variables Set: $COUNT"
echo "   Skipped (empty): $SKIPPED"
echo ""
echo "🔍 Verify at: https://github.com/$REPO/settings/variables/actions"
echo ""
echo "🔐 Don't forget to set secrets manually:"
echo "   • KUBECONFIG (required for Kubernetes deployment)"
echo "   • SLACK_WEBHOOK_URL (optional, for notifications)"
echo ""
echo "🚀 Next: Push to trigger workflows"
echo ""
