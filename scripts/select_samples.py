"""Escolhe, por critério fixo, as fotos de teste usadas na demonstração e no vídeo.

Inclui acertos, uma foto degradada, uma imagem sem planta e um erro real do modelo.
"""
import io
import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import main  # noqa: E402
from api.knowledge import CLASSES, DOENCA, SAUDAVEL  # noqa: E402

DATA = ROOT / "data/plantdoc_yolo"
OUT = ROOT / "assets/samples"
COCO128_URL = "https://github.com/ultralytics/assets/releases/download/v0.0.0/coco128.zip"
MIN_SIDE = 400
# Fotos com marca d'água de banco de imagens ficam de fora do material publicado.
# Revisadas a olho: o nome de arquivo nem sempre revela a origem.
EXCLUDE = {"DSCN1015_2ddd7bd0", "strawberry-leaves-isolated-white-34722259_b80bee15",
           "wild-strawberry-leaf-top-view-rotated-KTBXCY_ee56d281"}
# Códigos de catálogo no fim do nome (ex.: -34722259, -KTBXCY, -a1w1em) indicam banco de imagens.
STOCK_ID = re.compile(r"-(\d{6,}|(?=[a-z]*\d)(?=\d*[a-z])[a-z0-9]{6})_[0-9a-f]{8}$", re.IGNORECASE)
STOCK = ("stock", "depositphotos", "shutterstock", "featurepics", "dreamstime", "istock", "123rf", "alamy", "fotolia", "isolated")


def analyze(image):
    found = [main.describe(d) for d in main.detector.predict(image)]
    trusted = sorted((d for d in found if d["confiavel"]), key=lambda d: -d["confianca"])
    return main.decide(found), trusted


def main_():
    names = main.detector.names
    rows = []
    for path in sorted((DATA / "images/test").glob("*.jpg")):
        image = Image.open(path).convert("RGB")
        if min(image.size) < MIN_SIDE or path.stem in EXCLUDE or any(k in path.stem.lower() for k in STOCK) or STOCK_ID.search(path.stem):
            continue
        gt = {names[int(l.split()[0])] for l in (DATA / "labels/test" / f"{path.stem}.txt").read_text().splitlines()}
        status, trusted = analyze(image)
        rows.append({"path": path, "gt": gt, "status": status, "trusted": trusted})

    correct = [r for r in rows if r["trusted"] and all(d["classe"] in r["gt"] for d in r["trusted"])]
    wrong = [r for r in rows if r["trusted"] and r["trusted"][0]["classe"] not in r["gt"]]
    correct.sort(key=lambda r: -r["trusted"][0]["confianca"])
    wrong.sort(key=lambda r: -r["trusted"][0]["confianca"])

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = {"live": [], "uploads": {}}

    def save(row, name):
        target = OUT / f"{name}.jpg"
        Image.open(row["path"]).convert("RGB").save(target, quality=92)
        return {"arquivo": target.name, "origem": row["path"].stem, "rotulo_real": sorted(row["gt"]), "status": row["status"],
                "predito": [d["classe"] for d in row["trusted"]]}

    # Câmera virtual: o acerto mais confiante de cada cultura.
    seen = set()
    for row in correct:
        crop = CLASSES[row["trusted"][0]["classe"]][0]
        if crop not in seen and len(seen) < 5:  # cinco culturas com fotos sem marca d'água, revisadas a olho
            seen.add(crop)
            manifest["live"].append(save(row, f"live_{len(seen)}"))

    sick = next(r for r in correct if CLASSES[r["trusted"][0]["classe"]][2] == DOENCA and r["status"] == "possivel_doenca")
    healthy = next((r for r in correct if CLASSES[r["trusted"][0]["classe"]][2] == SAUDAVEL and r["status"] == "folha_saudavel"), None)
    manifest["uploads"]["doenca"] = save(sick, "upload_doenca")
    if healthy:
        manifest["uploads"]["saudavel"] = save(healthy, "upload_saudavel")
    if wrong:
        manifest["uploads"]["erro"] = save(wrong[0], "upload_erro")
        real = sorted(wrong[0]["gt"])[0]
        said = wrong[0]["trusted"][0]["classe"]
        nome = lambda c: f"{CLASSES[c][0].lower()} com {CLASSES[c][1].lower()}" if CLASSES[c][2] == DOENCA else f"{CLASSES[c][0].lower()} sadia"
        manifest["uploads"]["erro"]["descricao"] = f"a folha era de {nome(real)}, mas o modelo respondeu {nome(said)}"

    # Foto ruim: a primeira degradação que tira a certeza do modelo sobre o acerto acima.
    original = Image.open(sick["path"]).convert("RGB")
    degraded = None
    # Prefere a degradação em que o sistema pede outra foto; senão, a primeira em que não afirma nada.
    options = []
    for radius, light in ((4, 0.8), (6, 0.7), (8, 0.65), (10, 0.6), (13, 0.55), (16, 0.5), (24, 0.4)):
        candidate = ImageEnhance.Brightness(original.filter(ImageFilter.GaussianBlur(radius))).enhance(light)
        # Analisa a foto já salva em JPEG, exatamente como será enviada na demo.
        buffer = io.BytesIO()
        candidate.save(buffer, "JPEG", quality=92)
        candidate = Image.open(io.BytesIO(buffer.getvalue())).convert("RGB")
        status, trusted = analyze(candidate)
        if status in ("inconclusivo", "nada_detectado"):
            options.append((status != "inconclusivo", radius, light, status, candidate))
    if options:
        # Com folga: evita a degradação mais leve, que fica no limite da decisão.
        options.sort(key=lambda o: o[:2])
        _, radius, light, status, degraded = options[1] if len(options) > 1 and not options[1][0] else options[0]
        manifest["uploads"]["foto_ruim"] = {"arquivo": "upload_foto_ruim.jpg", "status": status, "blur": radius, "luz": light}
    if degraded is not None:
        degraded.save(OUT / "upload_foto_ruim.jpg", quality=92)

    # Imagem sem planta do COCO128.
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "c.zip"
        urllib.request.urlretrieve(COCO128_URL, archive)
        with zipfile.ZipFile(archive) as z:
            members = sorted(n for n in z.namelist() if n.endswith(".jpg"))
            for name in members:
                label = name.replace("images", "labels").replace(".jpg", ".txt")
                try:
                    classes = {l.split()[0] for l in z.read(label).decode().splitlines()}
                except KeyError:
                    continue
                # Só cenas sem pessoas (0) e sem plantas (58), para não publicar rostos.
                if {"0", "58"} & classes:
                    continue
                image = Image.open(io.BytesIO(z.read(name))).convert("RGB")
                status, _ = analyze(image)
                if status == "nada_detectado":
                    image.save(OUT / "upload_sem_planta.jpg", quality=92)
                    manifest["uploads"]["sem_planta"] = {"arquivo": "upload_sem_planta.jpg", "status": status}
                    break

    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main_()
