#!/bin/bash
set -euo pipefail

echo "🧪 Running local CI/CD simulation..."

# ------------------------------------------------------------------
# Cleanup trap (disabled when NO_CLEANUP=1)
# ------------------------------------------------------------------
if [ "${NO_CLEANUP:-0}" -eq 1 ]; then
  echo "⚠️ Cleanup disabled (NO_CLEANUP=1)"
else
  trap '{
    echo "🔹 Cleaning up CI environment..."
    docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml down -v || true
    rm -f $CI_ENV
    rm -f keys/gcs-service-account.json airflow/keys/gcs-service-account.json
    sudo rm -rf airflow/logs/* airflow/artifacts/* airflow/tmp/* mlruns/* artifacts/* || true
    echo "🎉 Local CI/CD simulation complete! (cleanup ensured)"
  }' EXIT
fi

# ------------------------------------------------------------------
# 1. Setup paths and env
# ------------------------------------------------------------------
CI_ENV=".env.ci"
mkdir -p keys airflow/keys airflow/logs airflow/artifacts airflow/tmp mlruns artifacts

# Clean old CI env
rm -f $CI_ENV
rm -f keys/gcs-service-account.json airflow/keys/gcs-service-account.json

# ------------------------------------------------------------------
# 2. Unit CI (lint + unit tests)
# ------------------------------------------------------------------
echo "🔹 Step 1: Running unit CI (lint + unit tests)..."

pip install -r requirements.txt
pip install -r requirements-dev.txt

black --check src tests
isort --profile black --check-only src tests
flake8 src tests
pytest -m "not integration" -v

echo "✅ Unit CI checks passed!"

# ------------------------------------------------------------------
# 3. Prepare CI env
# ------------------------------------------------------------------
echo "🔹 Step 2: Preparing integration CI environment..."

cat > $CI_ENV <<EOF
AIRFLOW_UID=0
PYTHONPATH=/opt/airflow:/opt/airflow/src
GCS_BUCKET=dummy-ci-bucket
MLFLOW_TRACKING_URI=http://mlflow:5000
# ✅ Unified path for MLflow artifacts inside containers
MLFLOW_ARTIFACT_URI=file:/opt/airflow/mlruns
GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/keys/gcs-service-account.json
EOF

echo '{"dummy":"true"}' > keys/gcs-service-account.json
echo '{"dummy":"true"}' > airflow/keys/gcs-service-account.json

chmod -R 777 airflow/logs airflow/artifacts airflow/tmp mlruns artifacts || true

# ------------------------------------------------------------------
# 4. Build and start stack (Postgres + Airflow + MLflow)
# ------------------------------------------------------------------
echo "🔹 Step 3: Building Docker images (cached build)..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml build

echo "🔹 Step 4: Starting Postgres..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml up -d postgres

echo "⏳ Waiting for Postgres..."
for i in {1..30}; do
  if docker exec airflow-postgres pg_isready -U airflow -d airflow; then
    echo "✅ Postgres is ready!"
    break
  fi
  sleep 2
done

# ------------------------------------------------------------------
# 5. Ensure MLflow DB exists
# ------------------------------------------------------------------
echo "🔹 Step 5: Ensuring MLflow database exists..."
make create-mlflow-db

# ------------------------------------------------------------------
# 6. Initialize Airflow DB
# ------------------------------------------------------------------
echo "🔹 Step 6: Initializing Airflow DB..."
for i in {1..3}; do
  if docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml run --rm airflow-init; then
    echo "✅ Airflow DB initialized"
    docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml run --rm webserver airflow db check || true
    break
  else
    echo "⚠️ Retry $i/3: Airflow init failed, retrying in 10s..."
    sleep 10
  fi
done

# ------------------------------------------------------------------
# 7. Start Airflow + MLflow
# ------------------------------------------------------------------
echo "🔹 Step 7: Starting Airflow + MLflow..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml up -d webserver scheduler mlflow

# ------------------------------------------------------------------
# 8. Health checks
# ------------------------------------------------------------------
echo "🔹 Step 8: Waiting for Airflow + MLflow..."

echo "⏳ Waiting for Airflow webserver..."
ok=0
for i in {1..100}; do
  if curl -sf http://localhost:8080/health | grep -q "healthy"; then ok=1; break; fi
  sleep 5
done
[ "$ok" -eq 1 ] || { echo "❌ Airflow webserver did not become healthy"; exit 1; }

echo "⏳ Waiting for MLflow..."
ok=0
for i in {1..100}; do
  if curl -sf http://localhost:5000 >/dev/null; then ok=1; break; fi
  sleep 3
done
if [ "$ok" -ne 1 ]; then
  echo "❌ MLflow did not become reachable"
  echo "==== Dumping MLflow logs for debugging ===="
  docker logs mlflow --tail=100 || true
  exit 1
fi

# ------------------------------------------------------------------
# 9. Fix mlflow-runs volume ownership
# ------------------------------------------------------------------
echo "🔹 Step 9: Fixing mlflow-runs volume permissions..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml run --rm fix-mlflow-runs

# ------------------------------------------------------------------
# 10. Bootstrap model + run integration tests
# ------------------------------------------------------------------
echo "🔹 Step 10: Bootstrapping dummy model in MLflow..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml run --rm \
  webserver \
  python src/train_with_mlflow.py \
    --data_path /opt/airflow/data/loan_default_selected_features_clean.csv \
    --model_name loan_default_model --alias staging

echo "🔹 Step 10b: Starting Serve..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml up -d serve

# ------------------------------------------------------------------
# 11. Run integration tests
# ------------------------------------------------------------------
echo "🔹 Step 11: Running integration tests..."
make integration-tests

echo "✅ Integration CI checks passed!"
