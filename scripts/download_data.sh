#!/usr/bin/env bash
# Baixa o PlantDoc (CC BY 4.0) só com os objetos do git, sem checkout.
# O checkout quebraria em macOS e Windows por causa de nomes que só diferem em maiúsculas.
set -euo pipefail
COMMIT="$(python3 -c "import json; print(json.load(open('docs/data_report.json'))['fonte_commit'])")"
git clone --no-checkout https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset data/raw/plantdoc
git -C data/raw/plantdoc reset --quiet "$COMMIT"
