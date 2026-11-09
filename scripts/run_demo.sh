#!/usr/bin/env bash
# Sobe a API e a demo em http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")/.."
echo "Abra http://localhost:8000 no Chrome. Ctrl+C para parar."
exec .venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000
