#!/bin/bash
set -euo pipefail

# Resolve repo root dynamically (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

# Map old flags to Makefile targets
case "${1:-}" in
  --fresh)
    echo "⚠️ Fresh reset requested (equivalent to make stop-hard)"
    make stop-hard
    ;;
  --reset-vars)
    echo "⚠️ Resetting Airflow Variables (equivalent to make reset-vars)"
    make reset-vars
    ;;
  "" )
    echo "🛑 Stopping all services (equivalent to make stop)"
    make stop
    ;;
  * )
    echo "❌ Unknown option: $1"
    echo "Usage: $0 [--fresh] [--reset-vars]"
    exit 1
    ;;
esac
