#!/usr/bin/env bash
# Publica weights/ como Release do GitHub e atualiza model.lock.json com os checksums.
# Uso: scripts/publish_model.sh modelo-v1 "Modelo final (40 épocas)" [--prerelease]
set -euo pipefail
cd "$(dirname "$0")/.."
TAG="$1"; TITLE="$2"; shift 2
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
FILES=(weights/agrofacil.onnx weights/agrofacil.json)
gh release create "$TAG" "${FILES[@]}" -t "$TITLE" -n "Modelo do AgroFácil Visão. Checksums em model.lock.json." "$@"
python3 - "$REPO" "$TAG" "${FILES[@]}" <<'PY'
import hashlib, json, sys
repo, tag, *files = sys.argv[1:]
sums = {f.split("/")[-1]: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
json.dump({"repo": repo, "tag": tag, "sha256": sums}, open("model.lock.json", "w"), indent=2)
print(open("model.lock.json").read())
PY
