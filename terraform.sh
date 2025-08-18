#!/bin/bash
set -euo pipefail

# === CONFIG ===
TERRAFORM_DIR="./infra/terraform"
KEY_FILE="./keys/gcs-service-account.json"
SERVICE_NAME="terraform"

# === GOOGLE CLOUD AUTH (host-side check) ===
if [[ ! -f "$KEY_FILE" ]]; then
  echo "❌ Service account key not found: $KEY_FILE"
  echo "   Make sure your gcs-service-account.json exists in ./keys/ (project root)"
  exit 1
fi

echo "🔑 Using credentials from $KEY_FILE (mounted inside container as /opt/airflow/keys/gcs-service-account.json)"

# === COMMAND HANDLING ===
cd "$TERRAFORM_DIR"

case "${1:-}" in
  init)
    docker compose run --rm -v $(pwd):/workspace -w /workspace $SERVICE_NAME init
    ;;
  plan)
    docker compose run --rm -v $(pwd):/workspace -w /workspace $SERVICE_NAME plan
    ;;
  apply)
    docker compose run --rm -v $(pwd):/workspace -w /workspace $SERVICE_NAME apply -auto-approve
    ;;
  destroy)
    docker compose run --rm -v $(pwd):/workspace -w /workspace $SERVICE_NAME destroy -auto-approve
    ;;
  *)
    echo "Usage: $0 {init|plan|apply|destroy}"
    exit 1
    ;;
esac
