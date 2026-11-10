"""Avaliação completa: calibra na validação, mede no teste e testa o modelo fora do cenário ideal.

O limiar de decisão é escolhido só com a validação. O teste é usado uma única vez para medir.

Uso: python scripts/evaluate.py --weights runs/agrofacil_yolo11n_480/weights/best.pt
"""
import argparse
import io
import json
import os
import random
import shutil
import statistics
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
DATA = ROOT / "data/plantdoc_yolo"
OUT = ROOT / "docs/results"
COCO128_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip"
PLANT_COCO_CLASSES = {"58"}  # "potted plant": a imagem contém planta de verdade


def calibrate(model, args):
    """Escolhe o limiar que maximiza o F1 médio entre as classes na validação."""
    val = model.val(data=args.data, split="val", imgsz=args.imgsz, batch=args.batch, device=args.device,
                    workers=args.workers, plots=False, verbose=False, project=str(OUT / "tmp"), name="val", exist_ok=True)
    f1 = val.box.f1_curve.mean(0)
    conf = float(val.box.px[int(f1.argmax())])
    return round(conf, 3), {"map50": float(val.box.map50), "map50_95": float(val.box.map), "melhor_f1": float(f1.max())}


def test_metrics(model, args):
    test = model.val(data=args.data, split="test", imgsz=args.imgsz, batch=args.batch, device=args.device,
                     workers=args.workers, plots=True, verbose=False, project=str(OUT), name="test", exist_ok=True)
    per_class = []
    for i, cls in enumerate(test.box.ap_class_index):
        per_class.append({
            "classe": model.names[int(cls)], "precisao": float(test.box.p[i]), "recall": float(test.box.r[i]),
            "map50": float(test.box.ap50[i]), "map50_95": float(test.box.ap[i]),
        })
    return {"map50": float(test.box.map50), "map50_95": float(test.box.map),
            "precisao": float(test.box.mp), "recall": float(test.box.mr), "por_classe": per_class}


DEGRADATIONS = {
    "JPEG muito comprimido (q=20)": lambda im: _jpeg(im, 20),
    "Baixa resolução (1/4)": lambda im: im.resize((max(1, im.width // 4), max(1, im.height // 4))).resize(im.size),
    "Pouca luz (40%)": lambda im: ImageEnhance.Brightness(im).enhance(0.4),
    "Fora de foco (blur 3 px)": lambda im: im.filter(ImageFilter.GaussianBlur(3)),
}


def _jpeg(im, quality):
    buffer = io.BytesIO()
    im.save(buffer, "JPEG", quality=quality)
    return Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")


def robustness(model, args, baseline):
    results = {"Original": baseline}
    for label, transform in DEGRADATIONS.items():
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "images/test").mkdir(parents=True)
            shutil.copytree(DATA / "labels/test", tmp / "labels/test")
            for path in (DATA / "images/test").glob("*.jpg"):
                transform(Image.open(path).convert("RGB")).save(tmp / "images/test" / path.name, quality=95)
            yaml = tmp / "data.yaml"
            names = "\n".join(f"  {i}: {n}" for i, n in model.names.items())
            yaml.write_text(f"path: {tmp}\ntrain: images/test\nval: images/test\ntest: images/test\nnames:\n{names}\n")
            m = model.val(data=str(yaml), split="test", imgsz=args.imgsz, batch=args.batch, device=args.device,
                          workers=0, plots=False, verbose=False, project=str(OUT / "tmp"), name="rob", exist_ok=True)
            results[label] = float(m.box.map50)
    return results


def bootstrap_ci(hits, n=2000, seed=42):
    if not hits:
        return [None, None]
    rng = np.random.default_rng(seed)
    arr = np.array(hits, dtype=float)
    means = rng.choice(arr, size=(n, len(arr))).mean(1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def rate(hits):
    return {"valor": float(np.mean(hits)) if hits else None, "ic95": bootstrap_ci(hits), "n": len(hits)}


def statuses(images):
    """Roda o caminho real do produto: mesma inferência e mesmas regras da API."""
    from api import main
    for path in images:
        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        found = [main.describe(d) for d in main.detector.predict(image)]
        yield path, main.decide(found), found


def product_metrics():
    """Mede a decisão que o produtor recebe, por imagem, no conjunto de teste."""
    from api.knowledge import CLASSES, DOENCA
    from api import main
    names = main.detector.names
    sick_found, healthy_ok, crop_ok, class_ok, answered = [], [], [], [], []
    false_reassurance, false_alarm = [], []
    counts = {}
    for path, status, found in statuses(sorted((DATA / "images/test").glob("*.jpg"))):
        counts[status] = counts.get(status, 0) + 1
        labels = (DATA / "labels/test" / f"{path.stem}.txt").read_text().splitlines()
        gt = {names[int(line.split()[0])] for line in labels}
        is_sick = any(CLASSES[c][2] == DOENCA for c in gt)
        conclusive = status in ("possivel_doenca", "folha_saudavel")
        answered.append(conclusive)
        if is_sick:
            sick_found.append(status == "possivel_doenca")
            false_reassurance.append(status == "folha_saudavel")
        else:
            healthy_ok.append(status == "folha_saudavel")
            false_alarm.append(status == "possivel_doenca")
        trusted = [d for d in found if d["confiavel"]]
        if trusted:
            top = max(trusted, key=lambda d: d["confianca"])
            crop_ok.append(top["cultura"] in {CLASSES[c][0] for c in gt})
            class_ok.append(top["classe"] in gt)
    return {
        "imagens": sum(counts.values()), "status": counts,
        "doente_sinalizada": rate(sick_found),
        "doente_dita_saudavel": rate(false_reassurance),
        "sadia_reconhecida": rate(healthy_ok),
        "sadia_com_alarme_falso": rate(false_alarm),
        "resposta_conclusiva": rate(answered),
        "cultura_correta_quando_responde": rate(crop_ok),
        "classe_exata_quando_responde": rate(class_ok),
    }


def out_of_scope_crops():
    """Fotos oficiais de teste com culturas que o modelo nunca viu (maçã, pêssego etc.)."""
    from prepare_data import CLASS_ID, base_name, parse_annotation, read_git_blobs
    blobs = read_git_blobs(ROOT / "data/raw/plantdoc")
    images = {base_name(p.split("/", 1)[1]): d for p, d in blobs.items()
              if p.startswith("TEST/") and not p.lower().endswith(".xml")}
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for path, data in blobs.items():
            if not (path.startswith("TEST/") and path.lower().endswith(".xml")):
                continue
            stem = base_name(path.split("/", 1)[1][:-4])
            try:
                _, _, boxes = parse_annotation(data)
            except Exception:
                continue
            if boxes and stem in images and all(b[0] not in CLASS_ID for b in boxes):
                target = Path(tmp) / f"{len(paths)}.jpg"
                target.write_bytes(images[stem])
                paths.append(target)
        return _false_positive_summary(paths)


def non_plant_images():
    """Imagens do dia a dia, sem planta, para medir alarme falso fora do domínio."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        archive = tmp / "coco128.zip"
        urllib.request.urlretrieve(COCO128_URL, archive)
        with zipfile.ZipFile(archive) as z:
            z.extractall(tmp)
        paths = []
        for image in sorted((tmp / "coco128/images/train2017").glob("*.jpg")):
            label = tmp / "coco128/labels/train2017" / f"{image.stem}.txt"
            classes = {l.split()[0] for l in label.read_text().splitlines()} if label.exists() else set()
            if not classes & PLANT_COCO_CLASSES:
                paths.append(image)
        return _false_positive_summary(paths)


def _false_positive_summary(paths):
    counts, trusted = {}, []
    for _, status, _found in statuses(paths):
        counts[status] = counts.get(status, 0) + 1
        trusted.append(status in ("possivel_doenca", "folha_saudavel"))
    return {"imagens": len(paths), "status": counts, "resposta_indevida": rate(trusted)}


def team_photos():
    """Fotos de plantas da equipe guardadas fora do treino (ver scripts/add_negatives.py)."""
    folder = ROOT / "data/plantdoc_yolo_neg/holdout_equipe"
    paths = sorted(folder.glob("*.jpg")) if folder.exists() else []
    return _false_positive_summary(paths) if paths else None


def latency(args):
    """Mede inferência (com pré e pós-processamento) em uma imagem por vez."""
    from api.detector import Detector
    paths = sorted((DATA / "images/test").glob("*.jpg"))
    random.Random(42).shuffle(paths)
    images = [Image.open(p).convert("RGB") for p in paths[:100]]
    results = {}
    for threads in (1, 2, 4):
        detector = Detector(ROOT / "weights/agrofacil.onnx", ROOT / "weights/agrofacil.json", threads=threads)
        detector.predict(images[0])
        times = []
        for image in images:
            start = time.perf_counter()
            detector.predict(image)
            times.append((time.perf_counter() - start) * 1000)
        p50 = statistics.median(times)
        results[f"ONNX CPU, {threads} thread(s)"] = {
            "p50_ms": round(p50, 1), "p95_ms": round(float(np.percentile(times, 95)), 1), "fps": round(1000 / p50, 1)}
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, default=ROOT / "runs/agrofacil_yolo11n_480/weights/best.pt")
    ap.add_argument("--data", default=str(DATA / "data.yaml"))
    ap.add_argument("--imgsz", type=int, default=480)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.weights)
    conf, val_metrics = calibrate(model, args)
    print("limiar calibrado na validação:", conf, val_metrics, flush=True)
    test = test_metrics(model, args)
    print("teste:", test["map50"], test["map50_95"], flush=True)
    robust = robustness(model, args, test["map50"])
    print("robustez:", robust, flush=True)

    from export_model import export
    export(args.weights, args.imgsz, conf)

    results = {
        "conf_decisao": conf, "validacao": val_metrics, "teste": test, "robustez_map50": robust,
        "produto": product_metrics(), "culturas_fora_do_escopo": out_of_scope_crops(),
        "imagens_sem_planta": non_plant_images(), "plantas_da_equipe": team_photos(), "latencia": latency(args),
    }
    (OUT / "metrics.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    shutil.rmtree(OUT / "tmp", ignore_errors=True)
    print(json.dumps({k: v for k, v in results.items() if k != "teste"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
