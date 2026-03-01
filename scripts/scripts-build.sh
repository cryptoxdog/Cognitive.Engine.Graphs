#!/usr/bin/env bash
# ============================================================================
# build.sh — Build and push Docker image to ECR
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

set -a; source "$ROOT_DIR/.env" 2>/dev/null || true; set +a

PROJECT="${L9_PROJECT:-l9-engine}"
ENV="${L9_ENV:-dev}"
REGION="${L9_REGION:-us-east-1}"
TAG="${1:-latest}"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "000000000000")
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE="${REGISTRY}/${PROJECT}:${TAG}"

echo "🐳 Building ${PROJECT}:${TAG}"
echo "   Registry: ${REGISTRY}"

# --- Build ---
docker build -t "${PROJECT}:${TAG}"   --build-arg L9_PROJECT="$PROJECT"   --build-arg L9_ENV="$ENV"   -f "$ROOT_DIR/Dockerfile"   "$ROOT_DIR"

echo "✅ Built ${PROJECT}:${TAG}"

# --- Tag & Push ---
if [ "$ACCOUNT_ID" != "000000000000" ]; then
  echo "📤 Pushing to ECR..."
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"

  # Create repo if not exists
  aws ecr describe-repositories --repository-names "$PROJECT" --region "$REGION" 2>/dev/null ||     aws ecr create-repository --repository-name "$PROJECT" --region "$REGION"

  docker tag "${PROJECT}:${TAG}" "$IMAGE"
  docker push "$IMAGE"

  echo "✅ Pushed ${IMAGE}"
else
  echo "⚠️  No AWS credentials — skipping push (local build only)"
fi
