#!/bin/bash
set -euo pipefail

# Wrapper: delegate troubleshooting logic to Makefile
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🔍 Running troubleshoot via Makefile..."
cd "$REPO_ROOT"
make troubleshoot
