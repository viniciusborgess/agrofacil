#!/usr/bin/env bash
# Depois do vídeo, gera o relatório em PDF com os números finais.
set -uo pipefail
cd "$(dirname "$0")/.."
until grep -qE "CONCLUÍDO|FALHOU" runs/pipeline.log 2>/dev/null; do
  pgrep -f after_training.sh >/dev/null || break
  sleep 60
done
grep -q "CONCLUÍDO" runs/pipeline.log && .venv/bin/python scripts/build_report.py && echo "== RELATÓRIO OK"
