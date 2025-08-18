#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
# Resolve repo root dynamically (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"
COMPOSE_FILE="$REPO_ROOT/airflow/docker-compose.yaml"

AIRFLOW_UID=$(grep -E '^AIRFLOW_UID=' "$ENV_FILE" | cut -d '=' -f2 || echo "50000")

echo "ℹ️ Using AIRFLOW_UID=$AIRFLOW_UID"

# ===== STEP 1: Rebuild serving image =====
echo
echo "🔄 STEP 1: Rebuilding serving image..."
docker compose -f "$COMPOSE_FILE" build serve

# ===== STEP 2: Fix permissions for serving container =====
echo
echo "🔧 STEP 2: Ensuring serving container permissions..."
docker compose -f "$COMPOSE_FILE" run --rm --user root serve bash -c "
    mkdir -p /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts &&
    chown -R ${AIRFLOW_UID}:0 /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts &&
    chmod -R 777 /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts
" || true

# ===== STEP 3: Start model serving =====
echo
echo "🚀 STEP 3: Starting model serving (REST API)..."
docker compose -f "$COMPOSE_FILE" up -d serve

echo "⏳ Waiting for model serving container..."
counter=0
until [ "$(docker inspect --format='{{.State.Running}}' model-serve 2>/dev/null)" == "true" ]; do
    sleep 3
    counter=$((counter+1))
    if [ $counter -gt 20 ]; then
        echo "❌ Model serving did not start."
        exit 1
    fi
done

echo "✅ Model serving is running!"
echo "🌐 Model Serving API: http://localhost:5001/invocations"
