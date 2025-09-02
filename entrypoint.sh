#!/bin/bash
set -e

# Defaults if not provided
MODEL_NAME=${MODEL_NAME:-loan_default_model}
MODEL_ALIAS=${MODEL_ALIAS:-staging}
PORT=${PORT:-5001}

echo "🚀 Starting MLflow model server"
echo "   MODEL_NAME: $MODEL_NAME"
echo "   MODEL_ALIAS: $MODEL_ALIAS"
echo "   PORT: $PORT"
echo "   MLFLOW_TRACKING_URI: $MLFLOW_TRACKING_URI"

mlflow models serve \
    -m "models:/${MODEL_NAME}@${MODEL_ALIAS}" \
    --host 0.0.0.0 \
    --port $PORT \
    --no-conda
