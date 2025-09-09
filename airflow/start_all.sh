#!/bin/bash
set -euo pipefail

# Thin wrapper: just call the Makefile target
# Supports --fresh flag if passed
if [[ "${1:-}" == "--fresh" ]]; then
  make reset
else
  make start
fi
