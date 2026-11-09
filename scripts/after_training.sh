#!/usr/bin/env bash
# Espera o treino acabar e gera avaliação, testes, demo gravada e vídeo, nesta ordem.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
while pgrep -f "scripts/train.py" >/dev/null; do sleep 60; done
step() { echo "== $(date '+%F %T') $1"; shift; "$@" || { echo "FALHOU: $*"; exit 1; }; }
step "avaliação" $PY scripts/evaluate.py
step "testes" $PY -m pytest -q tests
step "amostras" $PY scripts/select_samples.py
rm -rf assets/video_build
step "gravação" $PY scripts/record_demo.py --seconds 45
step "vídeo" $PY scripts/build_video.py
echo "== $(date '+%F %T') CONCLUÍDO"
