#!/bin/bash
set -euo pipefail

echo "🧪 Running local CI/CD simulation..."

# ------------------------------------------------------------------------------
# 1. Setup paths and env
# ------------------------------------------------------------------------------
CI_ENV=".env.ci"
mkdir -p keys airflow/keys airflow/logs airflow/artifacts airflow/tmp mlruns artifacts

# Clean old CI env
rm -f $CI_ENV
rm -f keys/gcs-service-account.json airflow/keys/gcs-service-account.json

# ------------------------------------------------------------------------------
# 2. Unit CI (simulates .github/workflows/ci.yml)
# ------------------------------------------------------------------------------
echo "🔹 Step 1: Running unit CI (lint + unit tests)..."

pip install -r requirements.txt
pip install -r requirements-dev.txt

black --check src tests
isort --profile black --check-only src tests
flake8 src tests
pytest -m "not integration" -v

echo "✅ Unit CI checks passed!"

# ------------------------------------------------------------------------------
# 3. Prepare CI env (simulates .github/workflows/ci-integration.yml)
# ------------------------------------------------------------------------------
echo "🔹 Step 2: Preparing integration CI environment..."

cat > $CI_ENV <<EOF
AIRFLOW_UID=0
GCS_BUCKET=dummy-ci-bucket
MLFLOW_TRACKING_URI=http://mlflow:5000
MLFLOW_ARTIFACT_URI=file:/opt/airflow/mlruns
GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/keys/gcs-service-account.json
EOF

echo '{"dummy":"true"}' > keys/gcs-service-account.json
echo '{"dummy":"true"}' > airflow/keys/gcs-service-account.json

chmod -R 777 airflow/logs airflow/artifacts airflow/tmp mlruns artifacts

# ------------------------------------------------------------------------------
# 4. Build and start stack (Postgres + Airflow + MLflow)
# ------------------------------------------------------------------------------
echo "🔹 Step 3: Building Docker images..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml build --no-cache

echo "🔹 Step 4: Starting Postgres..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml up -d postgres

echo "🔹 Step 5: Initializing Airflow DB..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml run --rm airflow-init

echo "🔹 Step 6: Starting Airflow + MLflow..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml up -d webserver scheduler mlflow

# ------------------------------------------------------------------------------
# 5. Bootstrap model + run integration tests
# ------------------------------------------------------------------------------
echo "🔹 Step 7: Bootstrapping dummy model in MLflow..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml run --rm webserver \
  python src/train_with_mlflow.py \
    --data_path /opt/airflow/data/loan_default_selected_features_clean.csv \
    --model_name loan_default_model --alias staging

echo "🔹 Step 8: Running integration tests..."
make integration-tests

echo "✅ Integration CI checks passed!"

# ------------------------------------------------------------------------------
# 6. Cleanup (mimics GitHub ephemeral runner)
# ------------------------------------------------------------------------------
echo "🔹 Step 9: Cleaning up CI environment..."
docker compose --env-file $CI_ENV -f airflow/docker-compose.yaml down -v

# Remove CI env + dummy keys
rm -f $CI_ENV
rm -f keys/gcs-service-account.json airflow/keys/gcs-service-account.json

# Remove CI-only artifacts/logs/mlruns (optional but keeps repo clean)
rm -rf airflow/logs/* airflow/artifacts/* mlruns/* artifacts/* airflow/tmp/* || true

echo "🎉 Local CI/CD simulation complete! All checks passed and cleaned."
