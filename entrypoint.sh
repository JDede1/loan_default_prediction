#!/bin/bash
set -euo pipefail

# Defaults if not provided
MODEL_NAME="${MODEL_NAME:-loan_default_model}"
MODEL_ALIAS="${MODEL_ALIAS:-staging}"
PORT="${PORT:-5001}"

echo "🚀 Starting MLflow model server"
echo "   MODEL_NAME: ${MODEL_NAME}"
echo "   MODEL_ALIAS: ${MODEL_ALIAS}"
echo "   PORT: ${PORT}"
echo "   MLFLOW_TRACKING_URI: ${MLFLOW_TRACKING_URI:-not_set}"

# Check that mlflow CLI is available
if ! command -v mlflow >/dev/null 2>&1; then
  echo "❌ mlflow command not found in PATH"
  exit 1
fi

# Start MLflow model serving
exec mlflow models serve \
    -m "models:/${MODEL_NAME}@${MODEL_ALIAS}" \
    --host 0.0.0.0 \
    --port "${PORT}" \
    --no-conda
