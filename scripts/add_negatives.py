"""Cria uma cópia do dataset com exemplos negativos: plantas que não são das 20 classes, marcadas como "nada a detectar".

Fontes de negativos:
  1. PlantDoc TRAIN com culturas fora do escopo (maçã, pêssego, mirtilo, framboesa etc.).
     Quase-duplicatas de qualquer imagem do TEST são descartadas, para não vazar para as métricas.
  2. Fotos da equipe (--extra): 70% vão para o treino e 30% ficam guardadas para medir o resultado.
     Fotos quase idênticas ficam sempre do mesmo lado da divisão.

O conjunto de teste original não muda, então as métricas antigas e novas são comparáveis.

Uso: python scripts/add_negatives.py [--extra ~/Desktop/minhas_plantas]
"""
import argparse
import collections
import hashlib
import io
import json
import random
import re
import shutil
from pathlib import Path

import imagehash
from PIL import Image, ImageOps

from prepare_data import (CLASS_ID, IMAGE_RE, MAX_SIDE, PHASH_MAX_DIST, base_name, parse_annotation,
                          read_git_blobs)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/plantdoc_yolo"
OUT = ROOT / "data/plantdoc_yolo_neg"
VAL_FRACTION = 0.15
HOLDOUT_FRACTION = 0.30
SEED = 42


def phash(img):
    return int(str(imagehash.phash(img, hash_size=8)), 16)


def near(h, hashes):
    return any(bin(h ^ other).count("1") <= PHASH_MAX_DIST for other in hashes)


def load(data):
    return ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")


def plantdoc_negatives(count):
    blobs = read_git_blobs(ROOT / "data/raw/plantdoc")
    pairs = collections.defaultdict(dict)
    for path, data in blobs.items():
        split, name = path.split("/", 1)
        if name.lower().endswith(".xml"):
            pairs[(split, base_name(name[:-4]))]["xml"] = data
        elif IMAGE_RE.search(name):
            pairs[(split, base_name(name))]["img"] = data
    # Todas as imagens de teste (dentro e fora do escopo) servem de referência contra vazamento.
    test_hashes = []
    for (split, _), pair in pairs.items():
        if split == "TEST" and "img" in pair:
            try:
                test_hashes.append(phash(load(pair["img"])))
            except OSError:
                pass
    out, seen = [], []
    for (split, stem), pair in sorted(pairs.items()):
        if split != "TRAIN" or "xml" not in pair or "img" not in pair:
            continue
        try:
            _, _, boxes = parse_annotation(pair["xml"])
            img = load(pair["img"])
        except Exception:
            continue
        if not boxes or any(name in CLASS_ID for name, *_ in boxes):
            continue
        h = phash(img)
        if near(h, test_hashes):
            count["negativos PlantDoc descartados por semelhança com o teste"] += 1
            continue
        if near(h, seen):
            count["negativos PlantDoc duplicados"] += 1
            continue
        seen.append(h)
        out.append((f"neg_{stem}", img, pair["img"]))
    count["negativos PlantDoc"] = len(out)
    return out, test_hashes


def team_photos(folder, test_hashes, count):
    files = sorted(p for p in Path(folder).expanduser().rglob("*")
                   if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic", ".webp"})
    items = []
    for p in files:
        try:
            img = load(p.read_bytes())
        except Exception:
            count["fotos da equipe ilegíveis"] += 1
            continue
        items.append((f"equipe_{p.stem}", img, p.read_bytes(), phash(img)))
    # Agrupa quase-duplicatas para que fiquem do mesmo lado da divisão.
    groups = []
    for it in items:
        for g in groups:
            if near(it[3], [m[3] for m in g]):
                g.append(it)
                break
        else:
            groups.append([it])
    random.Random(SEED).shuffle(groups)
    n_hold = max(1, round(len(groups) * HOLDOUT_FRACTION)) if len(groups) > 1 else 0
    hold = [m for g in groups[:n_hold] for m in g]
    train = [m for g in groups[n_hold:] for m in g]
    count["fotos da equipe no treino"] = len(train)
    count["fotos da equipe guardadas para avaliação"] = len(hold)
    return [m[:3] for m in train], [m[:3] for m in hold]


def save(img, raw, stem, folder, label_folder=None):
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", stem)[:80]
    name = f"{safe}_{hashlib.sha256(raw).hexdigest()[:8]}"
    img = img.copy()
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    folder.mkdir(parents=True, exist_ok=True)
    img.save(folder / f"{name}.jpg", quality=92)
    if label_folder is not None:
        label_folder.mkdir(parents=True, exist_ok=True)
        (label_folder / f"{name}.txt").write_text("")  # sem caixas: nada a detectar


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", type=Path, help="pasta com fotos de plantas que não são das 20 classes")
    args = ap.parse_args()
    count = collections.Counter()
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT)

    negatives, test_hashes = plantdoc_negatives(count)
    rng = random.Random(SEED)
    rng.shuffle(negatives)
    n_val = round(len(negatives) * VAL_FRACTION)
    groups = {"val": negatives[:n_val], "train": negatives[n_val:]}
    hold = []
    if args.extra:
        team_train, hold = team_photos(args.extra, test_hashes, count)
        groups["train"] += team_train
    for split, items in groups.items():
        for stem, img, raw in items:
            save(img, raw, stem, OUT / "images" / split, OUT / "labels" / split)
    for stem, img, raw in hold:
        save(img, raw, stem, OUT / "holdout_equipe")

    yaml = (SRC / "data.yaml").read_text().replace(str(SRC), str(OUT))
    (OUT / "data.yaml").write_text(yaml)
    report = {"contagens": dict(count), "negativos_treino": len(groups["train"]), "negativos_validacao": len(groups["val"])}
    (OUT / "negativos.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
