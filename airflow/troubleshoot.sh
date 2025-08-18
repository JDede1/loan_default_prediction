#!/bin/bash
set -euo pipefail

echo "🔍 Airflow, MLflow & Serving Troubleshooting Script"

# ===== CONFIG (keep in sync with start_all.sh) =====
ROOT_ENV="../.env"   # Always point to root .env
MLRUNS_DIR="../mlruns"
ARTIFACTS_DIR="../artifacts"
LOGS_DIR="./airflow-logs"
AIRFLOW_ARTIFACTS_DIR="./artifacts"
AIRFLOW_LOGS_DIR="./logs"
KEYS_DIR="./keys"

echo
echo "🔍 STEP 1: Checking Docker Compose service status..."
docker compose ps

echo
echo "📋 STEP 2: Listing all services from docker-compose.yaml..."
services=$(docker compose config --services)

for service in $services; do
    status=$(docker inspect --format='{{.State.Status}}' $(docker compose ps -q $service) 2>/dev/null || echo "not_found")
    health=$(docker inspect --format='{{.State.Health.Status}}' $(docker compose ps -q $service) 2>/dev/null || echo "none")

    echo "➡️  Service: $service | Status: $status | Health: $health"

    if [[ "$status" != "running" || "$health" == "unhealthy" ]]; then
        echo "⚠️  Service $service is not healthy — showing last 20 logs..."
        docker compose logs --tail=20 $service || true

        case $service in
            webserver)
                echo "🛠  Fixing Airflow webserver..."
                docker compose exec --user root webserver bash -c "
                    rm -f /home/airflow/airflow-webserver.pid || true &&
                    mkdir -p /home/airflow/logs/scheduler /home/airflow/logs/dag_processor &&
                    chown -R airflow:root /home/airflow/logs &&
                    chmod -R 775 /home/airflow/logs
                "
                docker compose restart webserver
                ;;
            scheduler)
                echo "🛠  Fixing Airflow scheduler..."
                docker compose exec --user root scheduler bash -c "
                    mkdir -p /home/airflow/logs/scheduler /home/airflow/logs/dag_processor &&
                    chown -R airflow:root /home/airflow/logs &&
                    chmod -R 775 /home/airflow/logs
                "
                docker compose restart scheduler
                ;;
            postgres)
                echo "🛠  Restarting Postgres..."
                docker compose restart postgres
                ;;
            mlflow)
                echo "🛠  Fixing MLflow folder permissions..."
                if command -v sudo &>/dev/null; then
                    sudo chown -R "$(id -u):0" "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$AIRFLOW_ARTIFACTS_DIR" || true
                    sudo chmod -R 775 "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$AIRFLOW_ARTIFACTS_DIR" || true
                else
                    chmod -R 777 "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$AIRFLOW_ARTIFACTS_DIR" || true
                fi
                docker compose restart mlflow
                ;;
            serve)
                echo "🛠  Fixing Serve container permissions..."
                docker compose run --rm --user root serve bash -c "
                    mkdir -p /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts &&
                    chown -R $(id -u):0 /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts &&
                    chmod -R 777 /opt/airflow/mlruns /opt/airflow/artifacts /opt/airflow/keys /tmp/artifacts
                " || true
                docker compose restart serve
                ;;
            airflow-init)
                echo "ℹ️  airflow-init runs only during first start or DB reset."
                ;;
            *)
                echo "ℹ️  No automated fix for $service, skipping."
                ;;
        esac
    fi
done

echo
echo "🔹 STEP 3: Checking if Airflow DB is initialized..."
if ! docker compose exec webserver airflow db check >/dev/null 2>&1; then
    echo "⚙️  Airflow DB not initialized — running airflow-init..."
    docker compose run --rm airflow-init
else
    echo "✅ Airflow DB is already initialized."
fi

echo
echo "🔹 STEP 4: Verifying Airflow Webserver health..."
MAX_RETRIES=30
COUNTER=0
until curl --silent http://localhost:8080/health | grep -q '"status":"healthy"'; do
    COUNTER=$((COUNTER+1))
    if [ $COUNTER -ge $MAX_RETRIES ]; then
        echo "❌ Airflow Webserver did not become healthy in time."
        exit 1
    fi
    echo "   Waiting... ($COUNTER/$MAX_RETRIES)"
    sleep 5
done
echo "✅ Airflow Webserver is healthy!"

echo
echo "🔹 STEP 5: Verifying MLflow health..."
if curl --silent http://localhost:5000 >/dev/null; then
    echo "✅ MLflow UI is reachable!"
else
    echo "❌ MLflow UI not responding at http://localhost:5000"
fi

echo
echo "🔹 STEP 5.5: Verifying Serve API health..."
if curl --silent -X POST http://localhost:5001/invocations -H "Content-Type: application/json" -d '{"dataframe_split": {"columns": [], "data": []}}' | grep -q 'error_code'; then
    echo "✅ Serve API is responding!"
else
    echo "❌ Serve API not responding at http://localhost:5001/invocations"
fi

# === Phase 2: List relevant Airflow Variables ===
echo
echo "🔹 STEP 6: Listing Phase 2 & Phase 3 Airflow Variables..."
PHASE_VARS=("MODEL_ALIAS" "PREDICTION_INPUT_PATH" "PREDICTION_OUTPUT_PATH" "STORAGE_BACKEND" "GCS_BUCKET" "LATEST_PREDICTION_PATH" \
            "MODEL_NAME" "PROMOTE_FROM_ALIAS" "PROMOTE_TO_ALIAS" "PROMOTION_AUC_THRESHOLD" "PROMOTION_F1_THRESHOLD" \
            "PROMOTION_TRIGGER_SOURCE" "PROMOTION_TRIGGERED_BY" "SLACK_WEBHOOK_URL" "ALERT_EMAILS")

for var in "${PHASE_VARS[@]}"; do
    value=$(docker compose exec webserver airflow variables get "$var" 2>/dev/null || echo "(not set)")
    echo "   • $var = $value"
done

echo
echo "✅ STEP 7: Final service status:"
docker compose ps
