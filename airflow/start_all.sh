#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
# Resolve repo root dynamically (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"
COMPOSE_FILE="$REPO_ROOT/airflow/docker compose.yaml"

AIRFLOW_UID=$(grep -E '^AIRFLOW_UID=' "$ENV_FILE" | cut -d '=' -f2 || echo "50000")

MLRUNS_DIR="$REPO_ROOT/mlruns"
ARTIFACTS_DIR="$REPO_ROOT/artifacts"
LOGS_DIR="$REPO_ROOT/airflow/airflow-logs"
AIRFLOW_ARTIFACTS_DIR="$REPO_ROOT/airflow/artifacts"
AIRFLOW_LOGS_DIR="$REPO_ROOT/airflow/logs"
KEYS_DIR="$REPO_ROOT/airflow/keys"

# ===== FLAGS =====
FRESH_START=false
if [[ "${1:-}" == "--fresh" ]]; then
    FRESH_START=true
    echo "⚠️  Fresh start mode: will clear old MLflow runs, artifacts, logs, and volumes..."
fi

echo "ℹ️  Using AIRFLOW_UID=$AIRFLOW_UID"

# ===== STEP 1: Rebuild images =====
echo
echo "🔄 STEP 1: Rebuilding required images..."
docker compose -f "$COMPOSE_FILE" build webserver scheduler mlflow serve

# ===== STEP 1.5: Prepare host directories =====
mkdir -p "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$LOGS_DIR" \
         "$AIRFLOW_ARTIFACTS_DIR" "$AIRFLOW_LOGS_DIR" "$KEYS_DIR"

if $FRESH_START; then
    echo "🧹 Clearing old runs/artifacts/logs..."
    rm -rf "$MLRUNS_DIR"/* "$ARTIFACTS_DIR"/* \
           "$AIRFLOW_ARTIFACTS_DIR"/* "$AIRFLOW_LOGS_DIR"/* \
           "$LOGS_DIR"/* /tmp/artifacts/* || true
    echo "🧹 Removing old Docker volumes..."
    docker compose -f "$COMPOSE_FILE" down -v
fi

# Fix local permissions (host side) — portable for Codespaces & local dev
if command -v sudo &>/dev/null; then
    sudo chown -R "$AIRFLOW_UID":0 \
        "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$LOGS_DIR" \
        "$AIRFLOW_ARTIFACTS_DIR" "$AIRFLOW_LOGS_DIR" "$KEYS_DIR" || true
    sudo chmod -R 775 \
        "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$LOGS_DIR" \
        "$AIRFLOW_ARTIFACTS_DIR" "$AIRFLOW_LOGS_DIR" "$KEYS_DIR" || true
else
    chmod -R 777 \
        "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$LOGS_DIR" \
        "$AIRFLOW_ARTIFACTS_DIR" "$AIRFLOW_LOGS_DIR" "$KEYS_DIR" || true
fi
echo "✅ Local directories ready."

# ===== STEP 2: Start Postgres =====
echo
echo "🚀 STEP 2: Starting Postgres..."
docker compose -f "$COMPOSE_FILE" up -d postgres

echo "⏳ Waiting for Postgres..."
counter=0
until [ "$(docker inspect --format='{{.State.Health.Status}}' airflow-postgres)" == "healthy" ]; do
    sleep 3
    counter=$((counter+1))
    if [ $counter -gt 20 ]; then
        echo "❌ Postgres did not become healthy."
        exit 1
    fi
done
echo "✅ Postgres is healthy!"

# ===== STEP 3: Init Airflow DB =====
echo
echo "🗄 STEP 3: Initializing Airflow DB..."
docker compose -f "$COMPOSE_FILE" run --rm airflow-init

# ===== STEP 4: Fix container permissions BEFORE starting Airflow =====
echo
echo "🔧 STEP 4: Ensuring container permissions..."
for service in webserver scheduler mlflow serve; do
    docker compose -f "$COMPOSE_FILE" run --rm --user root $service bash -c "
        mkdir -p /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts &&
        chown -R ${AIRFLOW_UID}:0 /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts &&
        chmod -R 777 /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts
    " || true
done

# ===== STEP 4.5: Remove stale PID files =====
echo
echo "🧹 STEP 4.5: Removing stale Airflow PID files..."
rm -f "$REPO_ROOT/airflow/airflow-webserver.pid" "$REPO_ROOT/airflow/airflow-scheduler.pid" || true
find "$AIRFLOW_LOGS_DIR" -type f -name "*.pid" -exec rm -f {} \; || true
find "$LOGS_DIR" -type f -name "*.pid" -exec rm -f {} \; || true
echo "✅ PID files cleaned."

# ===== STEP 5: Start Airflow =====
echo
echo "🚀 STEP 5: Starting Airflow webserver and scheduler..."
docker compose -f "$COMPOSE_FILE" up -d webserver scheduler

echo "⏳ Waiting for Airflow webserver to become healthy..."
counter=0
until [ "$(docker inspect --format='{{.State.Health.Status}}' airflow-webserver)" == "healthy" ]; do
    sleep 5
    counter=$((counter+1))
    if [ $counter -gt 60 ]; then
        echo "❌ Airflow Webserver did not become healthy."
        echo "💡 Tip: Run ./troubleshoot.sh for details."
        exit 1
    fi
done
echo "✅ Airflow Webserver is healthy!"

# Create default Airflow admin user if missing
echo "👤 Ensuring default Airflow admin user exists..."
docker compose -f "$COMPOSE_FILE" exec webserver bash -c "
    airflow users list | grep -q 'admin' || bash /opt/airflow/create_airflow_user.sh
" || {
    echo "⚠️ Could not verify/create admin user automatically."
}

# ===== STEP 5.5: Sync .env → Airflow Variables =====
echo
echo "📌 STEP 5.5: Syncing .env values to Airflow Variables..."
ENV_VARS_P2=("MODEL_ALIAS" "TRAIN_DATA_PATH" "PREDICTION_INPUT_PATH" "PREDICTION_OUTPUT_PATH" "STORAGE_BACKEND" "GCS_BUCKET")
ENV_VARS_P3=("MODEL_NAME" "PROMOTE_FROM_ALIAS" "PROMOTE_TO_ALIAS" "PROMOTION_AUC_THRESHOLD" "PROMOTION_F1_THRESHOLD" "PROMOTION_TRIGGER_SOURCE" "PROMOTION_TRIGGERED_BY" "SLACK_WEBHOOK_URL" "ALERT_EMAILS")

for var in "${ENV_VARS_P2[@]}" "${ENV_VARS_P3[@]}"; do
    value="$(grep -E "^$var=" "$ENV_FILE" | sed -E "s/^$var=//")" || value=""
    if [ -n "${value:-}" ]; then
        docker compose -f "$COMPOSE_FILE" exec webserver airflow variables set "$var" "$value" >/dev/null
        echo "   • Set Airflow Variable: $var=${value:0:80}${value:+$( [ ${#value} -gt 80 ] && echo '…' )}"
    else
        echo "   • Skipped: $var (not set in $ENV_FILE)"
    fi
done
echo "✅ Airflow Variables synced."

# ===== STEP 6: Start MLflow =====
echo
echo "🚀 STEP 6: Starting MLflow..."
docker compose -f "$COMPOSE_FILE" up -d mlflow

echo "⏳ Waiting for MLflow..."
counter=0
until [ "$(docker inspect --format='{{.State.Running}}' mlflow 2>/dev/null)" == "true" ]; do
    sleep 3
    counter=$((counter+1))
    if [ $counter -gt 20 ]; then
        echo "❌ MLflow did not start."
        exit 1
    fi
done
echo "✅ MLflow is running!"

# ===== STEP 7: Done =====
echo
echo "🎉 All core services are up!"
echo "🌐 Airflow UI:  http://localhost:8080"
echo "🌐 MLflow UI:   http://localhost:5000"
echo "👉 Next: Train a model in Airflow, then run ./start_serve.sh to deploy it."
