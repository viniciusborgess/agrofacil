"""Prepara o PlantDoc para o YOLO: extrai, valida, deduplica, separa e converte.

Lê os arquivos direto dos objetos do git porque o repositório original tem nomes
que só diferem por maiúsculas, o que corrompe o checkout em macOS e Windows.

Uso: python scripts/prepare_data.py --raw data/raw/plantdoc --out data/plantdoc_yolo
"""
import argparse
import collections
import hashlib
import io
import json
import random
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image, ImageOps

# Classes do escopo: hortaliças e grãos com doença identificável, mais a folha sadia.
# Fruteiras e classes sem amostra no teste ficam de fora (ver docs/ e relatório).
CLASSES = [
    "Tomato leaf", "Tomato Early blight leaf", "Tomato Septoria leaf spot",
    "Tomato leaf bacterial spot", "Tomato leaf late blight", "Tomato leaf mosaic virus",
    "Tomato leaf yellow virus", "Tomato mold leaf",
    "Corn Gray leaf spot", "Corn leaf blight", "Corn rust leaf",
    "Potato leaf early blight", "Potato leaf late blight",
    "Bell_pepper leaf", "Bell_pepper leaf spot",
    "Squash Powdery mildew leaf", "Soyabean leaf", "Strawberry leaf",
    "grape leaf", "grape leaf black rot",
]
CLASS_ID = {c: i for i, c in enumerate(CLASSES)}
IMAGE_RE = re.compile(r"\.(jpe?g|png)(\?.*)?$", re.I)
MAX_SIDE = 1024
PHASH_MAX_DIST = 4
VAL_FRACTION = 0.15
SEED = 42


def read_git_blobs(repo):
    """Devolve {caminho: bytes} de TRAIN/ e TEST/ sem depender do checkout."""
    listing = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.quotepath=off", "ls-tree", "-r", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    entries = []
    for line in listing:
        meta, path = line.split("\t", 1)
        if path.startswith(("TRAIN/", "TEST/")):
            entries.append((meta.split()[2], path))
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    blobs = {}
    for sha, path in entries:
        proc.stdin.write(f"{sha}\n".encode())
        proc.stdin.flush()
        size = int(proc.stdout.readline().split()[2])
        blobs[path] = proc.stdout.read(size)
        proc.stdout.read(1)
    proc.stdin.close()
    proc.wait()
    return blobs


def parse_annotation(xml_bytes):
    root = ET.fromstring(xml_bytes)
    size = root.find("size")
    width = int(float(size.findtext("width") or 0)) if size is not None else 0
    height = int(float(size.findtext("height") or 0)) if size is not None else 0
    boxes = []
    for obj in root.findall("object"):
        b = obj.find("bndbox")
        boxes.append((obj.findtext("name"), *(float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))))
    return width, height, boxes


def to_yolo_boxes(boxes, xml_w, xml_h, img_w, img_h):
    """Converte para YOLO. Devolve None se a anotação não casar com a imagem."""
    if xml_w <= 0 or xml_h <= 0:
        return None
    if abs(xml_w / xml_h - img_w / img_h) > 0.02:
        return None
    out = []
    for name, x1, y1, x2, y2 in boxes:
        x1, x2 = sorted((max(0.0, x1), min(float(xml_w), x2)))
        y1, y2 = sorted((max(0.0, y1), min(float(xml_h), y2)))
        if (x2 - x1) < 2 or (y2 - y1) < 2:
            continue
        out.append((CLASS_ID[name], (x1 + x2) / 2 / xml_w, (y1 + y2) / 2 / xml_h, (x2 - x1) / xml_w, (y2 - y1) / xml_h))
    return out or None


def base_name(name):
    """Remove extensões repetidas e sufixos de URL ("foto.JPG?123", "foto.jpg.jpg")."""
    while IMAGE_RE.search(name):
        name = IMAGE_RE.sub("", name)
    return name


def collect(blobs, count):
    """Pareia imagem e XML por nome exato e descarta o que não for utilizável."""
    by_stem = collections.defaultdict(dict)
    for path, data in blobs.items():
        name = path.split("/", 1)[1]
        if name.lower().endswith(".xml"):
            by_stem[(path.split("/")[0], base_name(name[:-4]))]["xml"] = data
        elif IMAGE_RE.search(name):
            by_stem[(path.split("/")[0], base_name(name))]["img"] = data
    items = []
    for (split, stem), pair in sorted(by_stem.items()):
        count[f"{split}: total"] += 1
        if "xml" not in pair or "img" not in pair:
            count[f"{split}: sem par imagem/xml"] += 1
            continue
        try:
            xml_w, xml_h, boxes = parse_annotation(pair["xml"])
        except (ET.ParseError, AttributeError, TypeError, ValueError):
            count[f"{split}: xml inválido"] += 1
            continue
        if not boxes:
            count[f"{split}: sem caixas"] += 1
            continue
        if any(name not in CLASS_ID for name, *_ in boxes):
            count[f"{split}: classe fora do escopo"] += 1
            continue
        try:
            img = ImageOps.exif_transpose(Image.open(io.BytesIO(pair["img"]))).convert("RGB")
        except OSError:
            count[f"{split}: imagem corrompida"] += 1
            continue
        yolo = to_yolo_boxes(boxes, xml_w, xml_h, *img.size)
        if yolo is None:
            count[f"{split}: anotação incompatível com a imagem"] += 1
            continue
        items.append({
            "split": split, "stem": stem, "image": img, "boxes": yolo,
            "phash": int(str(imagehash.phash(img, hash_size=8)), 16),
            "sha256": hashlib.sha256(pair["img"]).hexdigest(),
        })
    return items


def cluster_near_duplicates(items):
    """Agrupa duplicatas exatas e quase idênticas (pHash) com union-find."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    hashes = np.array([it["phash"] for it in items], dtype=np.uint64)
    for i in range(len(items)):
        dist = np.bitwise_count(hashes[i + 1:] ^ hashes[i])
        for j in np.nonzero(dist <= PHASH_MAX_DIST)[0]:
            parent[find(i)] = find(i + 1 + int(j))
    groups = collections.defaultdict(list)
    for i in range(len(items)):
        groups[find(i)].append(i)
    return list(groups.values())


def dedupe(items, count):
    """Mantém uma imagem por grupo, priorizando o teste oficial para preservá-lo."""
    keep = []
    for group in cluster_near_duplicates(items):
        members = [items[i] for i in group]
        if len(members) > 1:
            labels = {tuple(sorted({b[0] for b in m["boxes"]})) for m in members}
            if len(labels) > 1:
                count["grupos de duplicatas com rótulos conflitantes"] += 1
            if {m["split"] for m in members} == {"TRAIN", "TEST"}:
                count["grupos com vazamento treino/teste"] += 1
        tests = [m for m in members if m["split"] == "TEST"]
        winner = tests[0] if tests else members[0]
        count["imagens removidas por duplicidade"] += len(members) - 1
        keep.append(winner)
    return keep


def stratified_val(train, rng):
    """Separa a validação estratificando pela classe mais frequente de cada imagem."""
    by_class = collections.defaultdict(list)
    for it in train:
        primary = collections.Counter(b[0] for b in it["boxes"]).most_common(1)[0][0]
        by_class[primary].append(it)
    tr, val = [], []
    for cls in sorted(by_class):
        group = sorted(by_class[cls], key=lambda x: x["stem"])
        rng.shuffle(group)
        n_val = max(2, round(len(group) * VAL_FRACTION))
        val += group[:n_val]
        tr += group[n_val:]
    return tr, val


def write_split(items, split, out):
    (out / "images" / split).mkdir(parents=True, exist_ok=True)
    (out / "labels" / split).mkdir(parents=True, exist_ok=True)
    for it in items:
        safe = re.sub(r"[^A-Za-z0-9_-]+", "_", it["stem"])[:80]
        name = f"{safe}_{it['sha256'][:8]}"
        img = it["image"]
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        img.save(out / "images" / split / f"{name}.jpg", quality=92)
        lines = [f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for c, x, y, w, h in it["boxes"]]
        (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines) + "\n")


def split_stats(items):
    boxes, images = collections.Counter(), collections.Counter()
    for it in items:
        ids = [b[0] for b in it["boxes"]]
        boxes.update(ids)
        images.update(set(ids))
    return {
        "imagens": len(items),
        "caixas": sum(boxes.values()),
        "por_classe": {CLASSES[i]: {"caixas": boxes[i], "imagens": images[i]} for i in range(len(CLASSES))},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("data/raw/plantdoc"))
    ap.add_argument("--out", type=Path, default=Path("data/plantdoc_yolo"))
    args = ap.parse_args()

    count = collections.Counter()
    items = collect(read_git_blobs(args.raw), count)
    items = dedupe(items, count)
    train = [it for it in items if it["split"] == "TRAIN"]
    test = [it for it in items if it["split"] == "TEST"]
    tr, val = stratified_val(train, random.Random(SEED))

    for split, group in (("train", tr), ("val", val), ("test", test)):
        write_split(group, split, args.out)
    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(CLASSES))
    (args.out / "data.yaml").write_text(
        f"path: {args.out.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n"
    )
    commit = subprocess.run(["git", "-C", str(args.raw), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    report = {
        "fonte_commit": commit,
        "contagens": dict(sorted(count.items())),
        "train": split_stats(tr), "val": split_stats(val), "test": split_stats(test),
    }
    (args.out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    Path("docs").mkdir(exist_ok=True)
    Path("docs/data_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report["contagens"], ensure_ascii=False, indent=1))
    print("train/val/test:", len(tr), len(val), len(test))
    for c in CLASSES:
        print(f"{c:32s} {report['train']['por_classe'][c]['caixas']:5d} {report['val']['por_classe'][c]['caixas']:5d} {report['test']['por_classe'][c]['caixas']:5d}")


if __name__ == "__main__":
    main()
