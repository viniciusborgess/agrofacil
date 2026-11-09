"""Exporta o melhor checkpoint para ONNX e grava os metadados usados pela API.

Uso: python scripts/export_model.py --weights runs/agrofacil_yolo11n_480/weights/best.pt --conf-decision 0.4
"""
import argparse
import json
import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent


def export(weights, imgsz, conf_decision, conf_min=0.15, iou=0.5, out=ROOT / "weights"):
    model = YOLO(weights)
    onnx_path = model.export(format="onnx", imgsz=imgsz, simplify=False, dynamic=False, nms=False)
    out.mkdir(exist_ok=True)
    shutil.copy(onnx_path, out / "agrofacil.onnx")
    shutil.copy(weights, out / "agrofacil.pt")
    (out / "agrofacil.json").write_text(json.dumps({
        "version": "yolo11n-plantdoc20-v1",
        "classes": [model.names[i] for i in range(len(model.names))],
        "imgsz": imgsz,
        "conf_decision": conf_decision,
        "conf_min": conf_min,
        "iou": iou,
    }, ensure_ascii=False, indent=2))
    print("exportado para", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", type=Path, default=ROOT / "runs/agrofacil_yolo11n_480/weights/best.pt")
    ap.add_argument("--imgsz", type=int, default=480)
    ap.add_argument("--conf-decision", type=float, required=True, help="limiar calibrado na validação")
    ap.add_argument("--conf-min", type=float, default=0.15)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=ROOT / "weights")
    args = ap.parse_args()
    export(args.weights, args.imgsz, args.conf_decision, args.conf_min, args.iou, args.out)


if __name__ == "__main__":
    main()
