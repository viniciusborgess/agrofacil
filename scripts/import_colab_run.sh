#!/usr/bin/env bash
# Troca o treino local pelo treino feito no Colab e reinicia avaliação, vídeo e relatório.
# Uso: scripts/import_colab_run.sh ~/Downloads/agrofacil_treino.zip [data/plantdoc_yolo_neg/data.yaml]
set -euo pipefail
cd "$(dirname "$0")/.."
ZIP="${1:?informe o caminho de agrofacil_treino.zip}"
export EVAL_DATA="${2:-}"
unzip -l "$ZIP" | grep "agrofacil_yolo11n_480/weights/best.pt" >/dev/null || { echo "zip sem best.pt"; exit 1; }
pkill -f after_pipeline.sh || true
pkill -f after_training.sh || true
pkill -f "scripts/train.py" || true
# Etapas que a cadeia antiga possa ter deixado rodando.
pkill -f "scripts/(evaluate|select_samples|record_demo|build_video|build_report).py" || true
pkill -f "uvicorn api.main:app --host 127.0.0.1 --port 8765" || true
while pgrep -f "scripts/train.py" >/dev/null; do sleep 2; done
[ -d runs/agrofacil_yolo11n_480 ] && mv runs/agrofacil_yolo11n_480 "runs/agrofacil_yolo11n_480_anterior_$(date +%m%d_%H%M)"
unzip -q "$ZIP" -d runs/
rm -f runs/pipeline.log runs/report.log
nohup scripts/after_training.sh > runs/pipeline.log 2>&1 &
nohup scripts/after_pipeline.sh > runs/report.log 2>&1 &
disown -a
echo "Treino do Colab importado. Últimas épocas:"; tail -2 runs/agrofacil_yolo11n_480/results.csv | cut -c1-120
