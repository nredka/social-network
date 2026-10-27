#!/usr/bin/env bash
# Start the API locally with auto-reload. Usage: ./scripts/dev.sh
set -euo pipefail

# Run from the project root regardless of where the script is invoked from.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

exec uv run uvicorn app.main:app --reload --host 127.0.0.1 --port "${PORT:-8000}"
