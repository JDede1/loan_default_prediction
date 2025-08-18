#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
# Resolve repo root dynamically (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$REPO_ROOT/.env"
COMPOSE_FILE="$REPO_ROOT/airflow/docker-compose.yaml"

MLRUNS_DIR="$REPO_ROOT/mlruns"
ARTIFACTS_DIR="$REPO_ROOT/artifacts"
LOGS_DIR="$REPO_ROOT/airflow/airflow-logs"
AIRFLOW_ARTIFACTS_DIR="$REPO_ROOT/airflow/artifacts"
AIRFLOW_LOGS_DIR="$REPO_ROOT/airflow/logs"
KEYS_DIR="$REPO_ROOT/airflow/keys"

FRESH_RESET=false
RESET_VARS=false

# ===== FLAGS =====
for arg in "$@"; do
  case $arg in
    --fresh)
      FRESH_RESET=true
      ;;
    --reset-vars)
      RESET_VARS=true
      ;;
    *)
      echo "❌ Unknown option: $arg"
      echo "Usage: $0 [--fresh] [--reset-vars]"
      exit 1
      ;;
  esac
done

if $FRESH_RESET; then
  echo "⚠️  Fresh reset: stopping Airflow + MLflow + Serve, removing volumes, and clearing host folders."
fi
if $RESET_VARS; then
  echo "⚠️  Will clear Phase 2 & Phase 3 Airflow Variables."
fi

# ===== STEP 1: Stop core infra =====
echo "🛑 STEP 1: Stop services (Airflow + MLflow + Serve)..."
if $FRESH_RESET; then
  docker compose -f "$COMPOSE_FILE" stop webserver scheduler mlflow postgres serve
  docker compose -f "$COMPOSE_FILE" rm -f webserver scheduler mlflow postgres serve
  docker compose -f "$COMPOSE_FILE" down -v
else
  docker compose -f "$COMPOSE_FILE" stop webserver scheduler mlflow postgres serve
  docker compose -f "$COMPOSE_FILE" rm -f webserver scheduler mlflow postgres serve
fi

# ===== STEP 2: Clean PID files =====
echo
echo "🧹 STEP 2: Clean host PID files..."
rm -f "$REPO_ROOT/airflow/airflow-webserver.pid" "$REPO_ROOT/airflow/airflow-scheduler.pid" || true
find "$AIRFLOW_LOGS_DIR" -type f -name "*.pid" -exec rm -f {} \; || true
find "$LOGS_DIR" -type f -name "*.pid" -exec rm -f {} \; || true
echo "✅ PID files cleaned."

# ===== STEP 3: Ensure local logs dir exists and is writable =====
echo
echo "🔧 STEP 3: Ensure local logs dir exists and is writable..."
mkdir -p "$AIRFLOW_LOGS_DIR"
chmod -R 775 "$AIRFLOW_LOGS_DIR" || true
chown -R "$(id -u):$(id -g)" "$AIRFLOW_LOGS_DIR" || true

# ===== STEP 4: Prune dangling containers & networks =====
echo
echo "🧽 STEP 4: Prune dangling containers & networks (safe to run)..."
docker container prune -f || true
docker network prune -f || true

# ===== STEP 5: Fresh reset of local folders =====
if $FRESH_RESET; then
  echo
  echo "🗑 STEP 5: Clearing bind-mount folders for a clean slate..."

  if command -v sudo &>/dev/null; then
    sudo rm -rf \
      "$MLRUNS_DIR"/* \
      "$ARTIFACTS_DIR"/* \
      "$AIRFLOW_ARTIFACTS_DIR"/* \
      "$AIRFLOW_LOGS_DIR"/* \
      "$LOGS_DIR"/* \
      "$KEYS_DIR"/* \
      /tmp/artifacts/* || true

    echo
    echo "🔧 STEP 6: Reset ownership & permissions on bind-mount roots..."
    sudo chown -R "$(id -u):0" \
      "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$AIRFLOW_ARTIFACTS_DIR" \
      "$AIRFLOW_LOGS_DIR" "$LOGS_DIR" "$KEYS_DIR" /tmp/artifacts || true
    sudo chmod -R 777 \
      "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$AIRFLOW_ARTIFACTS_DIR" \
      "$AIRFLOW_LOGS_DIR" "$LOGS_DIR" "$KEYS_DIR" /tmp/artifacts || true
  else
    rm -rf \
      "$MLRUNS_DIR"/* \
      "$ARTIFACTS_DIR"/* \
      "$AIRFLOW_ARTIFACTS_DIR"/* \
      "$AIRFLOW_LOGS_DIR"/* \
      "$LOGS_DIR"/* \
      "$KEYS_DIR"/* \
      /tmp/artifacts/* || true

    chmod -R 777 \
      "$MLRUNS_DIR" "$ARTIFACTS_DIR" "$AIRFLOW_ARTIFACTS_DIR" \
      "$AIRFLOW_LOGS_DIR" "$LOGS_DIR" "$KEYS_DIR" /tmp/artifacts || true
  fi
fi

# ===== STEP 6.5: Clear Airflow Variables if requested =====
if $RESET_VARS; then
  echo
  echo "🗑 STEP 6.5: Clearing Phase 2 & Phase 3 Airflow Variables..."
  ENV_VARS=("MODEL_ALIAS" "PREDICTION_INPUT_PATH" "PREDICTION_OUTPUT_PATH" "STORAGE_BACKEND" "GCS_BUCKET" "LATEST_PREDICTION_PATH" \
            "MODEL_NAME" "PROMOTE_FROM_ALIAS" "PROMOTE_TO_ALIAS" "PROMOTION_AUC_THRESHOLD" "PROMOTION_F1_THRESHOLD" \
            "PROMOTION_TRIGGER_SOURCE" "PROMOTION_TRIGGERED_BY" "SLACK_WEBHOOK_URL" "ALERT_EMAILS")

  for var in "${ENV_VARS[@]}"; do
    echo "   • Removing Airflow Variable: $var"
    docker compose -f "$COMPOSE_FILE" run --rm webserver airflow variables delete "$var" || true
  done
  echo "✅ Airflow Variables cleared."
fi

# ===== STEP 7: Done =====
echo
if $FRESH_RESET; then
  echo "✅ Done. Environment fully reset (Airflow + MLflow + Serve stopped, volumes cleared)."
else
  echo "✅ Done. Services stopped (Airflow + MLflow + Serve) and workspace cleaned (volumes preserved)."
fi
