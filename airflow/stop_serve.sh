#!/bin/bash
set -euo pipefail

echo "🛑 Stopping model serving (REST API)..."

# Stop and remove only the serving container
docker compose stop serve || true
docker compose rm -f serve || true

echo
echo "🧹 Cleaning up any dangling containers & networks..."
docker container prune -f || true
docker network prune -f || true

echo
echo "✅ Model serving stopped (volumes preserved)."
echo "👉 Use ./start_serve.sh to restart serving."
