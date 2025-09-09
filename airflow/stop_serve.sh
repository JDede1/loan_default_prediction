#!/bin/bash
set -euo pipefail

# Resolve repo root dynamically (works from anywhere)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$REPO_ROOT"

echo "🛑 Stopping model serving (equivalent to make stop-serve)..."
make stop-serve
