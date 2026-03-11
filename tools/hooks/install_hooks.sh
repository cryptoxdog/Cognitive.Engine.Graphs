#!/usr/bin/env bash
# =============================================================================
# Git Hooks Installer (Repo-Agnostic)
#
# Discovers hook files in the same directory (or a configurable location)
# and installs them into the repo's .git/hooks directory.
#
# Usage: bash tools/hooks/install_hooks.sh
# =============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Resolve paths
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [[ -z "$REPO_ROOT" ]]; then
    echo "❌ ERROR: Not inside a git repository."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOKS_SOURCE="${HOOKS_SOURCE:-$SCRIPT_DIR}"
HOOKS_DEST="$REPO_ROOT/.git/hooks"

echo -e "${BLUE}📦 Installing Git Hooks...${NC}"
echo "   Source: $HOOKS_SOURCE"
echo "   Dest:   $HOOKS_DEST"
echo ""

mkdir -p "$HOOKS_DEST"

INSTALLED=0

# Install any file that matches a known git hook name
KNOWN_HOOKS="pre-commit post-merge pre-push commit-msg prepare-commit-msg post-checkout pre-rebase"

for hook_name in $KNOWN_HOOKS; do
    source_file="$HOOKS_SOURCE/$hook_name"
    if [[ -f "$source_file" ]]; then
        cp "$source_file" "$HOOKS_DEST/$hook_name"
        chmod +x "$HOOKS_DEST/$hook_name"
        echo -e "  ${GREEN}✓${NC} $hook_name"
        ((INSTALLED++))
    fi
done

if [[ $INSTALLED -eq 0 ]]; then
    echo -e "${YELLOW}⚠ No hook files found in $HOOKS_SOURCE${NC}"
    echo "  Place hook scripts (pre-commit, post-merge, pre-push, etc.) next to this installer."
    exit 1
fi

echo ""
echo -e "${GREEN}✅ $INSTALLED hook(s) installed!${NC}"
echo ""
echo "Dependencies (optional but recommended):"
echo ""
echo "  Python tools:"
echo "    pip install ruff mypy pytest"
echo ""
echo "  Secret scanning (gitleaks):"
echo "    macOS:  brew install gitleaks"
echo "    Linux:  https://github.com/gitleaks/gitleaks/releases"
echo ""
echo "Test hooks:"
echo "  git commit -m 'test'   # Triggers pre-commit"
echo "  git pull               # Triggers post-merge"
echo "  git push               # Triggers pre-push"
