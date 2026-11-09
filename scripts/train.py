"""Treino customizado do detector. Retome com --resume após qualquer interrupção.

Uso em Apple Silicon: python scripts/train.py
Uso com GPU (Colab):  python scripts/train.py --device 0 --model yolo11s.pt --imgsz 640 --batch 16 --epochs 100
"""
import argparse
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=str(ROOT / "weights/yolo11n.pt"))
    ap.add_argument("--data", default=str(ROOT / "data/plantdoc_yolo/data.yaml"))
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--imgsz", type=int, default=480)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--name", default="agrofacil_yolo11n_480")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    if args.resume:
        YOLO(ROOT / "runs" / args.name / "weights/last.pt").train(resume=True)
        return

    YOLO(args.model).train(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        device=args.device, workers=args.workers, seed=42,
        project=str(ROOT / "runs"), name=args.name, exist_ok=True,
        patience=12, cos_lr=True, close_mosaic=8,
        # Folhas não têm orientação fixa, então giros e inversões vertical são válidos.
        degrees=15, flipud=0.5, fliplr=0.5,
    )


if __name__ == "__main__":
    main()
