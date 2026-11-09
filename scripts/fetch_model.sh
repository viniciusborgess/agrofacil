#!/usr/bin/env bash
# Baixa o modelo da Release indicada em model.lock.json e confere o SHA-256 de cada arquivo.
set -euo pipefail
cd "$(dirname "$0")/.."
LOCK=model.lock.json
REPO=$(python3 -c "import json; print(json.load(open('$LOCK'))['repo'])")
TAG=$(python3 -c "import json; print(json.load(open('$LOCK'))['tag'])")
mkdir -p weights
python3 -c "import json; [print(k, v) for k, v in json.load(open('$LOCK'))['sha256'].items()]" | while read -r name sum; do
  curl -fsSL -o "weights/$name" "https://github.com/$REPO/releases/download/$TAG/$name"
  echo "$sum  weights/$name" | shasum -a 256 -c -
done
