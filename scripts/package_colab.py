"""Empacota dados, pesos iniciais e script de treino para treinar no Google Colab (GPU T4).

Uso: python scripts/package_colab.py   ->  colab/agrofacil_colab.zip e colab/treino_colab.ipynb
"""
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "colab"
COLAB_ROOT = "/content/agrofacil"


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="plantdoc_yolo", help="pasta dentro de data/ (ex.: plantdoc_yolo_neg)")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    data = ROOT / "data" / args.data
    yaml = (data / "data.yaml").read_text().replace(str(ROOT), COLAB_ROOT)
    with zipfile.ZipFile(OUT / "agrofacil_colab.zip", "w", zipfile.ZIP_STORED) as z:
        z.writestr(f"data/{args.data}/data.yaml", yaml)
        for f in sorted(data.rglob("*")):
            if f.is_file() and f.name != "data.yaml" and not f.name.endswith(".cache"):
                z.write(f, f.relative_to(ROOT))
        z.write(ROOT / "weights/yolo11n.pt", "weights/yolo11n.pt")
        z.write(ROOT / "scripts/train.py", "scripts/train.py")

    cells = [
        ("markdown", "# AgroFácil · treino na GPU\n\n1. Menu **Ambiente de execução → Alterar o tipo de ambiente** → **GPU T4**.\n"
                     "2. **Ambiente de execução → Executar tudo**.\n3. Quando pedir, envie `agrofacil_colab.zip`.\n"
                     "4. No fim, o navegador baixa `agrofacil_treino.zip`."),
        ("code", "!nvidia-smi --query-gpu=name,memory.total --format=csv"),
        ("code", "from google.colab import files\nimport os, zipfile\n"
                 "enviado = files.upload()\nnome = next(iter(enviado))\n"
                 f"os.makedirs('{COLAB_ROOT}', exist_ok=True)\nzipfile.ZipFile(nome).extractall('{COLAB_ROOT}')\n"
                 f"print(sorted(os.listdir('{COLAB_ROOT}')))"),
        ("code", "!pip -q install ultralytics==8.4.202"),
        ("code", f"%cd {COLAB_ROOT}\n!python scripts/train.py --device 0 --batch 16 --workers 4 --data {COLAB_ROOT}/data/{args.data}/data.yaml"),
        ("code", f"%cd {COLAB_ROOT}/runs\n!zip -qr /content/agrofacil_treino.zip agrofacil_yolo11n_480\n"
                 "!tail -3 agrofacil_yolo11n_480/results.csv\nfiles.download('/content/agrofacil_treino.zip')"),
    ]
    nb = {"nbformat": 4, "nbformat_minor": 5,
          "metadata": {"accelerator": "GPU", "colab": {"gpuType": "T4"}, "kernelspec": {"name": "python3", "display_name": "Python 3"}},
          "cells": [{"cell_type": t, "metadata": {}, "source": s, **({"outputs": [], "execution_count": None} if t == "code" else {})}
                    for t, s in cells]}
    (OUT / "treino_colab.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False))
    print("pronto:", OUT)


if __name__ == "__main__":
    main()
