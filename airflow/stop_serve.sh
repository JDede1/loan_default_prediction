#!/bin/bash
set -euo pipefail

# ===== CONFIG =====
# Resolve repo root dynamically (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$REPO_ROOT/airflow/docker compose.yaml"

echo "🛑 Stopping model serving (REST API)..."

# Stop and remove only the serving container
docker compose -f "$COMPOSE_FILE" stop serve || true
docker compose -f "$COMPOSE_FILE" rm -f serve || true

echo
echo "🧹 Cleaning up any dangling containers & networks..."
docker container prune -f || true
docker network prune -f || true

echo
echo "✅ Model serving stopped (volumes preserved)."
echo "👉 Use ./start_serve.sh to restart serving."
