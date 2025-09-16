#!/bin/bash
set -euo pipefail

echo "🚀 Starting MLflow Tracking Server"
echo "   Backend URI: ${BACKEND_URI:-sqlite:///mlflow.db}"
echo "   Default Artifact Root: ${ARTIFACT_ROOT:-/mlflow/artifacts}"
echo "   Port: ${PORT:-5000}"

exec mlflow server \
    --backend-store-uri "${BACKEND_URI:-sqlite:///mlflow.db}" \
    --default-artifact-root "${ARTIFACT_ROOT:-/mlflow/artifacts}" \
    --host 0.0.0.0 \
    --port "${PORT:-5000}"
