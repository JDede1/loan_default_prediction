#!/bin/bash
set -e

echo "🔍 Airflow & MLflow Troubleshooting Script"

echo
echo "🔄 STEP 1: Ensuring monitor-image is up to date..."
docker compose build monitor-image

echo
echo "🔍 STEP 2: Checking Docker Compose service status..."
docker compose ps

echo
echo "📋 STEP 3: Listing all services from docker-compose.yaml..."
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
                sudo chown -R "$(id -u):0" ../mlruns ../artifacts ./artifacts || true
                chmod -R 775 ../mlruns ../artifacts ./artifacts || true
                docker compose restart mlflow
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
echo "🔹 STEP 4: Checking if Airflow DB is initialized..."
if ! docker compose exec webserver airflow db check >/dev/null 2>&1; then
    echo "⚙️  Airflow DB not initialized — running airflow-init..."
    docker compose run --rm airflow-init
else
    echo "✅ Airflow DB is already initialized."
fi

echo
echo "🔹 STEP 5: Verifying Airflow Webserver health..."
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

# === Phase 2: List relevant Airflow Variables ===
echo
echo "🔹 STEP 6: Listing Phase 2 Airflow Variables..."
PHASE2_VARS=("MODEL_ALIAS" "PREDICTION_INPUT_PATH" "PREDICTION_OUTPUT_PATH" "STORAGE_BACKEND" "GCS_BUCKET" "LATEST_PREDICTION_PATH")

for var in "${PHASE2_VARS[@]}"; do
    value=$(docker compose exec webserver airflow variables get "$var" 2>/dev/null || echo "(not set)")
    echo "   • $var = $value"
done

echo
echo "✅ STEP 7: Final service status:"
docker compose ps
