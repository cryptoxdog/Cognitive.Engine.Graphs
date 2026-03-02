#!/usr/bin/env bash
# --- L9_META ---
# l9_schema: 1
# origin: l9-template
# engine: graph
# layer: [scripts]
# tags: [L9_TEMPLATE, scripts, deploy]
# owner: platform
# status: active
# --- /L9_META ---
# ============================================================================
# deploy.sh — Deploy infrastructure via Terraform
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
IAC_DIR="$ROOT_DIR/iac"

ENV="${1:-dev}"
ACTION="${2:-apply}"

echo "🚀 L9 Deploy — env=${ENV}, action=${ACTION}"

if [ ! -d "$IAC_DIR" ]; then
  echo "❌ iac/ directory not found"
  exit 1
fi

cd "$IAC_DIR"

# --- Init ---
terraform init   -backend-config="key=${L9_PROJECT:-l9-engine}/${ENV}/terraform.tfstate"

# --- Select workspace ---
terraform workspace select "$ENV" 2>/dev/null || terraform workspace new "$ENV"

# --- Plan or Apply ---
case "$ACTION" in
  plan)
    terraform plan       -var="env=${ENV}"       -var-file="${ENV}.tfvars" 2>/dev/null ||     terraform plan -var="env=${ENV}"
    ;;

  apply)
    terraform plan       -var="env=${ENV}"       -var-file="${ENV}.tfvars"       -out=plan.out 2>/dev/null ||     terraform plan -var="env=${ENV}" -out=plan.out

    echo ""
    read -p "Apply? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      terraform apply plan.out
      rm -f plan.out
      echo "✅ Deployed to ${ENV}"

      echo ""
      echo "Outputs:"
      terraform output
    fi
    ;;

  destroy)
    echo "⚠️  DESTROYING ${ENV} environment"
    read -p "Are you sure? Type env name to confirm: " CONFIRM
    if [ "$CONFIRM" = "$ENV" ]; then
      terraform destroy -var="env=${ENV}" -auto-approve
      echo "✅ Destroyed ${ENV}"
    else
      echo "❌ Aborted"
    fi
    ;;

  *)
    echo "Usage: deploy.sh <env> [plan|apply|destroy]"
    exit 1
    ;;
esac
