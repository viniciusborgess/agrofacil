"""Gera um MP4 anotado pelo modelo, a partir de um vídeo ou de uma pasta de fotos.

Os resultados mostrados saem do mesmo detector da API, com o tempo medido em cada quadro.

Uso:
  python scripts/make_demo_video.py --video minha_gravacao.mp4 --out assets/demo_campo.mp4
  python scripts/make_demo_video.py --images assets/samples --out assets/demo_fotos.mp4
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.detector import Detector  # noqa: E402
from api.knowledge import CLASSES, DOENCA  # noqa: E402

W, H = 1280, 720
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
BRAND, RED, GREEN, YELLOW = (31, 92, 52), (255, 90, 54), (61, 220, 132), (242, 211, 107)


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default(size)


def fit(image):
    scale = min(W / image.width, H / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)))
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.paste(resized, ((W - resized.width) // 2, (H - resized.height) // 2))
    return canvas


def annotate(canvas, source_size, detections, conf_decision, footer):
    scale = min(W / source_size[0], H / source_size[1])
    iw, ih = source_size[0] * scale, source_size[1] * scale
    ox, oy = (W - iw) / 2, (H - ih) / 2
    draw = ImageDraw.Draw(canvas)
    for d in detections:
        crop, condition, kind, _ = CLASSES[d.class_name]
        trusted = d.confidence >= conf_decision
        color = YELLOW if not trusted else RED if kind == DOENCA else GREEN
        x1, y1, x2, y2 = d.box[0] * iw + ox, d.box[1] * ih + oy, d.box[2] * iw + ox, d.box[3] * ih + oy
        draw.rectangle([x1, y1, x2, y2], outline=color, width=4)
        label = f"{crop}: {condition} {d.confidence:.0%}"
        f = font(24)
        tw = draw.textlength(label, font=f)
        ty = y1 - 32 if y1 > 32 else y1
        draw.rectangle([x1, ty, x1 + tw + 12, ty + 32], fill=color)
        draw.text((x1 + 6, ty + 2), label, fill=(0, 0, 0), font=f)
    draw.rectangle([0, H - 44, W, H], fill=(0, 0, 0))
    draw.text((16, H - 37), footer, fill=(255, 255, 255), font=font(24))
    return canvas


def title_card(lines):
    card = Image.new("RGB", (W, H), BRAND)
    draw = ImageDraw.Draw(card)
    y = H // 2 - 50 * len(lines) // 2
    for i, line in enumerate(lines):
        f = font(56 if i == 0 else 32)
        draw.text(((W - draw.textlength(line, font=f)) / 2, y), line, fill=(255, 255, 255), font=f)
        y += 76 if i == 0 else 50
    return card


def writer(path, fps):
    gen = imageio_ffmpeg.write_frames(str(path), (W, H), fps=fps, codec="libx264", pix_fmt_out="yuv420p", quality=7, macro_block_size=1)
    gen.send(None)
    return gen


def from_images(detector, folder, out):
    fps = 10
    gen = writer(out, fps)
    for _ in range(fps * 4):
        gen.send(np.asarray(title_card([
            "AgroFácil Visão", "Modelo aplicado a fotos do conjunto de teste",
            "Fotos que o modelo nunca viu no treino",
        ])).tobytes())
    for path in sorted(folder.glob("*.jpg")):
        image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
        start = time.perf_counter()
        detections = detector.predict(image)
        ms = (time.perf_counter() - start) * 1000
        frame = annotate(fit(image), image.size, detections, detector.conf_decision, f"ONNX em CPU: {ms:.0f} ms")
        for _ in range(fps * 3):
            gen.send(np.asarray(frame).tobytes())
    gen.close()


def from_video(detector, video, out):
    capture = cv2.VideoCapture(str(video))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    gen = writer(out, fps)
    last, smoothed = [], None
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        start = time.perf_counter()
        last = detector.predict(image)
        ms = (time.perf_counter() - start) * 1000
        smoothed = ms if smoothed is None else 0.9 * smoothed + 0.1 * ms
        footer = f"ONNX em CPU: {smoothed:.0f} ms por quadro ({1000 / smoothed:.0f} FPS)"
        gen.send(np.asarray(annotate(fit(image), image.size, last, detector.conf_decision, footer)).tobytes())
    capture.release()
    gen.close()


def main():
    ap = argparse.ArgumentParser()
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--video", type=Path)
    group.add_argument("--images", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    detector = Detector(ROOT / "weights/agrofacil.onnx", ROOT / "weights/agrofacil.json")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.video:
        from_video(detector, args.video, args.out)
    else:
        from_images(detector, args.images, args.out)
    print("vídeo gravado em", args.out)


if __name__ == "__main__":
    main()
