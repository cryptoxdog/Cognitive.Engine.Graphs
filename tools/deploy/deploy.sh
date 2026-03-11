#!/usr/bin/env bash
# =============================================================================
# VPS Deploy (Repo-Agnostic)
#
# GitHub SSOT + Env Sync + Selective Rebuild + Health Validation
#
# Behavior:
#   LOCAL: stages + commits + pushes current branch to origin
#   VPS:   git hard reset to origin/$BRANCH, env sync, docker rebuild
#   HEALTH: runs deep_mri.sh; optionally runs e2e smoke test
#
# ALL configuration pulled from .env.vps (or environment variables).
# You never edit this script — you edit your .env.vps.
#
# Required .env.vps vars:
#   VPS_HOST             — SSH hostname of your VPS
#   VPS_REPO             — Remote repo path (e.g. /opt/myapp)
#   COMPOSE_PROD         — Production compose overlay (e.g. docker-compose.prod.yml)
#   CORE_SERVICES        — Space-separated core services for --core flag
#   APP_API_KEY          — API key (used by health scripts on VPS)
#
# Optional .env.vps vars:
#   DEPLOY_BRANCH        — Required branch (default: main)
#   ALLOW_NON_MAIN       — Allow deploy from non-main (default: false)
#   ALLOW_DOCKER_PRUNE   — Allow docker prune (default: false)
#   HEALTH_SCRIPT        — Path to health script (default: scripts/deployment/deep_mri.sh)
#   E2E_SCRIPT           — Path to E2E script (default: scripts/e2e_test.sh)
#   APP_NAME             — Project name for display (default: APP)
#
# Usage: ./tools/deploy/deploy.sh [flags]
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Load config from .env.vps
# ---------------------------------------------------------------------------

MAC_REPO="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$MAC_REPO" ]] || { echo "❌ Run this from inside a git repo."; exit 1; }
cd "$MAC_REPO"

ENV_VPS="$MAC_REPO/.env.vps"
if [[ -f "$ENV_VPS" ]]; then
    set -a
    # shellcheck source=/dev/null
    source "$ENV_VPS"
    set +a
fi

# ---------------------------------------------------------------------------
# All config from env vars — fail fast on missing required ones
# ---------------------------------------------------------------------------

VPS_HOST="${VPS_HOST:?Set VPS_HOST in .env.vps}"
VPS_REPO="${VPS_REPO:?Set VPS_REPO in .env.vps}"
COMPOSE_BASE="${COMPOSE_BASE:-docker-compose.yml}"
COMPOSE_PROD="${COMPOSE_PROD:?Set COMPOSE_PROD in .env.vps}"
CORE_SERVICES="${CORE_SERVICES:?Set CORE_SERVICES in .env.vps (space-separated)}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
ALLOW_NON_MAIN="${ALLOW_NON_MAIN:-false}"
ALLOW_DOCKER_PRUNE="${ALLOW_DOCKER_PRUNE:-false}"
HEALTH_SCRIPT="${HEALTH_SCRIPT:-scripts/deployment/deep_mri.sh}"
E2E_SCRIPT="${E2E_SCRIPT:-scripts/e2e_test.sh}"
APP_NAME="${APP_NAME:-APP}"
ENV_EXAMPLE="${ENV_EXAMPLE:-.env.example}"
ENV_VPS_TEMPLATE="${ENV_VPS_TEMPLATE:-.env.vps.template}"
REMOTE_ENV_FILE="${REMOTE_ENV_FILE:-.env}"

SSH_OPTS="-o BatchMode=yes -o StrictHostKeyChecking=accept-new"

# Runtime flags
BRANCH="${BRANCH:-$DEPLOY_BRANCH}"
NO_CACHE=false
PRUNE_DOCKER=false
SYNC_ENV=true
DRY_RUN=false
NO_REBUILD=false
RUN_GODMODE=false
SERVICES=""
COMMIT_MSG="deploy: $(date +'%Y-%m-%d %H:%M:%S')"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

run() { if $DRY_RUN; then echo "DRY: $*"; else eval "$@"; fi; }
die() { echo "❌ $*" 1>&2; exit 1; }

usage() {
cat << EOF
Usage: ./tools/deploy/deploy.sh [flags]

Flags:
  --msg ""           Commit message
  --no-cache         Rebuild images without cache
  --prune-docker     docker system prune -af (NO volumes, gated by ALLOW_DOCKER_PRUNE)
  --no-sync-env      Do not sync .env.vps → VPS
  --no-rebuild       Skip container rebuild (git pull + env sync only)
  --services "a b"   Rebuild ONLY specified services
  --core             Rebuild ONLY core services (\$CORE_SERVICES)
  --godmode          Run E2E smoke test after deployment
  --dry-run          Print commands without executing
  -h, --help         Help

Examples:
  ./tools/deploy/deploy.sh --msg "full deploy"
  ./tools/deploy/deploy.sh --no-rebuild
  ./tools/deploy/deploy.sh --services "api postgres"
  ./tools/deploy/deploy.sh --core
  ./tools/deploy/deploy.sh --msg "critical hotfix" --godmode
EOF
}

# ---------------------------------------------------------------------------
# .env.vps.template management
# ---------------------------------------------------------------------------

ensure_gitignore_allows_env_template() {
    [[ -f ".gitignore" ]] || return 0
    if grep -qE '^\s*\.env\.\*' .gitignore; then
        if ! grep -qE "^\s*!${ENV_VPS_TEMPLATE}" .gitignore; then
            echo " + Patching .gitignore to allow tracking ${ENV_VPS_TEMPLATE}"
            printf '\n# Allow committing env template (placeholders only)\n!%s\n' "$ENV_VPS_TEMPLATE" >> .gitignore
        fi
    fi
}

patch_env_template_from_example() {
    local example_path="$MAC_REPO/$ENV_EXAMPLE"
    local template_path="$MAC_REPO/$ENV_VPS_TEMPLATE"
    [[ -f "$example_path" ]] || { echo " = No $ENV_EXAMPLE found, skipping template patch"; return 0; }

    local tmp_out
    tmp_out="$(mktemp)"

    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*# ]] || [[ -z "$line" ]]; then
            echo "$line" >> "$tmp_out"; continue
        fi
        if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)= ]]; then
            local key="${BASH_REMATCH[1]}"
            if [[ -f "$template_path" ]]; then
                local existing
                existing="$(grep -E "^${key}=" "$template_path" 2>/dev/null | head -1 || true)"
                echo "${existing:-${key}=}" >> "$tmp_out"
            else
                echo "${key}=" >> "$tmp_out"
            fi
        else
            echo "$line" >> "$tmp_out"
        fi
    done < "$example_path"

    if [[ ! -f "$template_path" ]] || ! cmp -s "$tmp_out" "$template_path"; then
        mv "$tmp_out" "$template_path"
        echo " + Patched $ENV_VPS_TEMPLATE from $ENV_EXAMPLE"
    else
        rm -f "$tmp_out"
        echo " = $ENV_VPS_TEMPLATE already up-to-date"
    fi
}

# ---------------------------------------------------------------------------
# Deployment functions
# ---------------------------------------------------------------------------

sync_env_to_server() {
    $SYNC_ENV || { echo " = Env sync disabled"; return 0; }
    [[ -f "$ENV_VPS" ]] || die "Missing .env.vps — create it with real values."

    local remote_env="$VPS_REPO/$REMOTE_ENV_FILE"
    echo "[ENV] Syncing .env.vps → $VPS_HOST:$remote_env"

    local stamp
    stamp="$(date +%Y%m%d_%H%M%S)"

    ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && (test -f '$remote_env' && cp -a '$remote_env' '${remote_env}.bak.${stamp}' || true)"

    if $DRY_RUN; then
        echo "DRY: streaming .env.vps → $VPS_HOST:$remote_env"
    else
        ssh $SSH_OPTS "$VPS_HOST" "cat > '$remote_env' && chmod 600 '$remote_env'" < "$ENV_VPS"
    fi

    if ! $DRY_RUN; then
        local local_hash remote_hash
        local_hash="$(shasum -a 256 "$ENV_VPS" | awk '{print $1}')"
        remote_hash="$(ssh $SSH_OPTS "$VPS_HOST" "shasum -a 256 '$remote_env'" | awk '{print $1}')"
        [[ "$local_hash" == "$remote_hash" ]] || die "Env sync mismatch (local $local_hash != remote $remote_hash)"
        echo " ✅ Env synced (sha256 match)"
    fi
}

remote_git_hard_reset() {
    echo "[VPS] Hard reset to origin/$BRANCH (SSOT)"
    ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && git fetch origin '$BRANCH' && git reset --hard 'origin/$BRANCH' && git clean -fd"
}

remote_rebuild_stack() {
    local build_opts=""
    $NO_CACHE && build_opts="--no-cache"

    if [[ -n "$SERVICES" ]]; then
        echo "[VPS] Selective rebuild: $SERVICES (no-cache=$NO_CACHE)"
        ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && docker compose -f $COMPOSE_BASE -f $COMPOSE_PROD stop $SERVICES"
        ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && docker compose -f $COMPOSE_BASE -f $COMPOSE_PROD build $build_opts $SERVICES"
        ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && docker compose -f $COMPOSE_BASE -f $COMPOSE_PROD up -d --force-recreate $SERVICES"
    else
        echo "[VPS] Full rebuild (all services) no-cache=$NO_CACHE"
        [[ "$RUN_GODMODE" == "false" ]] && { echo "[VPS] Full rebuild → GOD MODE enabled automatically"; RUN_GODMODE=true; }
        ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && docker compose -f $COMPOSE_BASE -f $COMPOSE_PROD down --remove-orphans"
        ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && docker compose -f $COMPOSE_BASE -f $COMPOSE_PROD build $build_opts"
        ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && docker compose -f $COMPOSE_BASE -f $COMPOSE_PROD up -d --force-recreate --remove-orphans"
    fi

    if $PRUNE_DOCKER; then
        if [[ "$ALLOW_DOCKER_PRUNE" == "true" ]]; then
            echo "[VPS] Prune docker (no volumes)"
            ssh $SSH_OPTS "$VPS_HOST" "docker system prune -af"
        else
            echo "[VPS] --prune-docker requested but ALLOW_DOCKER_PRUNE!=true, skipping."
        fi
    fi
}

remote_health() {
    echo ""
    echo "┌─────────────────────────────────────────────────────────────┐"
    echo "│ HEALTH VALIDATION                                           │"
    echo "└─────────────────────────────────────────────────────────────┘"
    echo ""

    echo "⏳ Waiting for services to initialize (15s)..."
    sleep 15

    echo ""
    echo "═══ PHASE 1: Deep MRI ($HEALTH_SCRIPT) ═══"
    echo ""

    ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && chmod +x '$HEALTH_SCRIPT' && './$HEALTH_SCRIPT'"
    local mri_exit=$?
    [[ $mri_exit -eq 0 ]] && echo "✅ Deep MRI passed" || echo "⚠️ Deep MRI completed with warnings (exit $mri_exit)"

    if $RUN_GODMODE; then
        echo ""
        echo "═══ PHASE 2: E2E Smoke ($E2E_SCRIPT) ═══"
        echo ""

        ssh $SSH_OPTS "$VPS_HOST" "cd '$VPS_REPO' && chmod +x '$E2E_SCRIPT' && './$E2E_SCRIPT' smoke"
        local e2e_exit=$?
        [[ $e2e_exit -eq 0 ]] && echo "✅ E2E validation PASSED" || echo "❌ E2E validation FAILED (exit $e2e_exit)"
    else
        echo ""
        echo "ℹ️ GOD MODE skipped (use --godmode for E2E validation)"
    fi
}

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --msg)          COMMIT_MSG="$2"; shift 2 ;;
        --no-cache)     NO_CACHE=true; shift ;;
        --prune-docker) PRUNE_DOCKER=true; shift ;;
        --no-sync-env)  SYNC_ENV=false; shift ;;
        --no-rebuild)   NO_REBUILD=true; shift ;;
        --services)     SERVICES="$2"; shift 2 ;;
        --core)         SERVICES="$CORE_SERVICES"; shift ;;
        --godmode)      RUN_GODMODE=true; shift ;;
        --dry-run)      DRY_RUN=true; shift ;;
        -h|--help)      usage; exit 0 ;;
        *)              die "Unknown flag: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  ${APP_NAME} Deploy (GitHub SSOT + Selective + Health)"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "[LOCAL] Repo:   $MAC_REPO"
echo "[LOCAL] Branch: $(git rev-parse --abbrev-ref HEAD)"
echo "[LOCAL] Commit: $(git rev-parse --short HEAD)"
echo "[VPS]   Host:   $VPS_HOST"
echo "[VPS]   Repo:   $VPS_REPO"

if [[ -n "$SERVICES" ]]; then
    echo "[MODE]  Selective rebuild: $SERVICES"
elif $NO_REBUILD; then
    echo "[MODE]  No rebuild (git pull + env sync only)"
else
    echo "[MODE]  Full rebuild (all containers)"
fi

$RUN_GODMODE && echo "[HEALTH] Deep MRI + E2E" || echo "[HEALTH] Deep MRI only"
echo ""

# Branch safety
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$DEPLOY_BRANCH" && "$ALLOW_NON_MAIN" != "true" ]]; then
    die "Refusing deploy from '$current_branch'. Expected '$DEPLOY_BRANCH' or ALLOW_NON_MAIN=true."
fi

echo "[LOCAL] Git status:"
git status --porcelain || true
echo ""

# 0) Template management
ensure_gitignore_allows_env_template
patch_env_template_from_example

# 1) Stage + commit + push
git add -A
if git diff --cached --quiet; then
    echo " = Nothing staged; skipping commit/push"
else
    git commit --no-verify -m "${COMMIT_MSG}"
    git push --no-verify origin HEAD
fi

# 2) VPS: hard reset, sync env, rebuild
remote_git_hard_reset
sync_env_to_server

if $NO_REBUILD; then
    echo "[VPS] Skipping container rebuild (--no-rebuild)"
else
    remote_rebuild_stack
fi

# 3) Health validation
remote_health

echo ""
echo "✅ Done."
