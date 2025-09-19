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
#!/bin/bash
set -euo pipefail

echo "🚀 Starting MLflow Tracking Server"
echo "   Backend URI: ${BACKEND_URI:-sqlite:///mlflow.db}"
echo "   Default Artifact Root: ${ARTIFACT_ROOT:-/mlflow/artifacts}"
echo "   Port: ${PORT:-5000}"

# If using Postgres, wait for the mlflow DB to be available
if [[ "${BACKEND_URI:-}" == postgresql* ]]; then
  echo "⏳ Waiting for Postgres and mlflow database..."
  until pg_isready -h postgres -U "${POSTGRES_USER:-airflow}" -d mlflow >/dev/null 2>&1; do
    echo "   Still waiting for mlflow database..."
    sleep 3
  done
  echo "✅ Postgres is ready and mlflow database is available"
fi

exec mlflow server \
    --backend-store-uri "${BACKEND_URI:-sqlite:///mlflow.db}" \
    --default-artifact-root "${ARTIFACT_ROOT:-/mlflow/artifacts}" \
    --host 0.0.0.0 \
    --port "${PORT:-5000}"
