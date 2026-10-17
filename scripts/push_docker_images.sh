#!/usr/bin/env bash
# ==============================================================================
# Urban Environmental Intelligence & Prediction Platform
# Docker Hub Image Tagging and Publishing Script
# ==============================================================================
set -euo pipefail

DOCKERHUB_USER="${1:-akash123cyber}"
TAG="${2:-latest}"

echo "============================================================"
echo " Preparing Docker Images for Docker Hub user: ${DOCKERHUB_USER}"
echo " Image Tag: ${TAG}"
echo "============================================================"

SERVICES=(
  "data-collector"
  "data-processor"
  "analytics-service"
  "api-service"
  "web-dashboard"
)

for svc in "${SERVICES[@]}"; do
  LOCAL_IMG="urbaneipp/${svc}:latest"
  TARGET_IMG_1="${DOCKERHUB_USER}/${svc}:${TAG}"
  TARGET_IMG_2="${DOCKERHUB_USER}/urban-${svc}:${TAG}"

  echo "==> Tagging ${LOCAL_IMG} -> ${TARGET_IMG_1} & ${TARGET_IMG_2}"
  docker tag "${LOCAL_IMG}" "${TARGET_IMG_1}"
  docker tag "${LOCAL_IMG}" "${TARGET_IMG_2}"

  echo "==> Pushing ${TARGET_IMG_1}..."
  docker push "${TARGET_IMG_1}" || echo "Notice: docker push ${TARGET_IMG_1} failed (run 'docker login' first if pushing to remote Hub)."

  echo "==> Pushing ${TARGET_IMG_2}..."
  docker push "${TARGET_IMG_2}" || echo "Notice: docker push ${TARGET_IMG_2} failed (run 'docker login' first if pushing to remote Hub)."
done

echo "============================================================"
echo " Docker image preparation complete!"
echo "============================================================"
