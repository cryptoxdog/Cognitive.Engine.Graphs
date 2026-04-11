#!/usr/bin/env bash
# Bulk-upload Actions secrets from a dotenv file to one or more repositories.
#
# Requires: GitHub CLI (`brew install gh`), authenticated (`gh auth login`).
# File format: same as .env.local — KEY=value per line, # comments ignored by gh.
#
# Usage (from repo root, or set --file to an absolute path):
#   ./tools/sync_github_actions_secrets.sh -R myorg/repo-a -R myorg/repo-b
#   ./tools/sync_github_actions_secrets.sh --file "$HOME/.secrets/enrichment.env" -R myorg/repo-a
#
# Same secrets to many repos (typical):
#   repos=(myorg/svc-a myorg/svc-b myorg/svc-c)
#   for r in "${repos[@]}"; do ./tools/sync_github_actions_secrets.sh -R "$r"; done
#
# Organization secrets (one value shared by selected repos) — use GitHub UI or run per key:
#   gh secret set PERPLEXITY_API_KEY --org ORG --body "$VAL" --repos repo-a,repo-b --visibility selected
#
# Do not commit files containing real secret values.

set -euo pipefail

usage() {
  echo "Usage: $0 [-f FILE] -R owner/repo [-R owner/repo ...]" >&2
  echo "  -f, --file   Dotenv file (default: .env.local in current directory)" >&2
  echo "  -R, --repo   Target repository (repeat for multiple)" >&2
  exit 1
}

FILE=""
REPOS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f | --file)
      FILE=$2
      shift 2
      ;;
    -R | --repo)
      REPOS+=("$2")
      shift 2
      ;;
    -h | --help)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
done

if [[ ${#REPOS[@]} -eq 0 ]]; then
  echo "error: pass at least one -R owner/repo" >&2
  usage
fi

if [[ -z "$FILE" ]]; then
  FILE=".env.local"
fi

if [[ ! -f "$FILE" ]]; then
  echo "error: file not found: $FILE" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh (GitHub CLI) not installed" >&2
  exit 1
fi

for r in "${REPOS[@]}"; do
  echo "Uploading secrets from $FILE → $r ..."
  gh secret set -f "$FILE" -R "$r"
  echo "  done."
done

echo "All targets updated."
