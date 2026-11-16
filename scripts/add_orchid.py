"""Cria data/plantdoc_yolo_orq: o dataset com negativos mais duas classes novas da orquídea da equipe.

Classes novas (ids 20 e 21):
  Orchid leaf       folha de orquídea sem mancha visível
  Orchid leaf spot  folha de orquídea com mancha escura

As caixas estão em data/orquidea/anotacoes.json (feitas à mão sobre as 40 fotos da equipe).
Divisão: as 28 fotos que já estavam no treino continuam no treino (repetidas REPEAT vezes, porque são
poucas perto das ~1.900 do PlantDoc); das 12 guardadas, metade vai para a validação e metade para o teste.
O resto do dataset (PlantDoc e negativos) não muda.

Uso: python scripts/add_orchid.py
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data/plantdoc_yolo_neg"
OUT = ROOT / "data/plantdoc_yolo_orq"
ANN = ROOT / "data/orquidea/anotacoes.json"
NEW_CLASSES = ["Orchid leaf", "Orchid leaf spot"]
REPEAT = 3


def yolo_lines(boxes, class_id):
    lines = []
    for b in boxes:
        x1, y1, x2, y2 = (min(max(b[k], 0.0), 1.0) for k in ("x1", "y1", "x2", "y2"))
        lines.append(f"{class_id[b['classe']]} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}")
    return "\n".join(lines) + "\n"


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    shutil.copytree(SRC, OUT, ignore=shutil.ignore_patterns("*.cache", "holdout_equipe"))

    yaml = (SRC / "data.yaml").read_text().replace(str(SRC), str(OUT)).rstrip("\n")
    base = sum(1 for line in yaml.splitlines() if line.startswith("  ") and ":" in line)
    class_id = {name: base + i for i, name in enumerate(NEW_CLASSES)}
    yaml += "".join(f"\n  {i}: {name}" for name, i in class_id.items()) + "\n"
    (OUT / "data.yaml").write_text(yaml)

    images = json.loads(ANN.read_text())["imagens"]
    holdout = sorted(p.name for p in (SRC / "holdout_equipe").glob("*.jpg"))
    split_of = {name: ("val" if i % 2 == 0 else "test") for i, name in enumerate(holdout)}
    count = {"train": 0, "val": 0, "test": 0}
    for name, boxes in sorted(images.items()):
        stem = Path(name).stem
        label = yolo_lines(boxes, class_id)
        if name in split_of:
            split = split_of[name]
            shutil.copy(SRC / "holdout_equipe" / name, OUT / "images" / split / name)
            (OUT / "labels" / split / f"{stem}.txt").write_text(label)
            count[split] += 1
            continue
        # Já está no treino como negativo (rótulo vazio): troca pelo rótulo com caixas e repete.
        (OUT / "labels/train" / f"{stem}.txt").write_text(label)
        for r in range(2, REPEAT + 1):
            shutil.copy(OUT / "images/train" / name, OUT / "images/train" / f"{stem}_r{r}.jpg")
            (OUT / "labels/train" / f"{stem}_r{r}.txt").write_text(label)
        count["train"] += 1

    report = {"classes_novas": class_id, "fotos_orquidea": count, "repeticoes_no_treino": REPEAT,
              "caixas": sum(len(b) for b in images.values()),
              "caixas_com_mancha": sum(1 for b in images.values() for x in b if x["classe"] == NEW_CLASSES[1])}
    (OUT / "orquidea.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
