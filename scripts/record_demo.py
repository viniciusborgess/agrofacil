"""Grava a demonstração real: navegador, API e modelo, com uma câmera virtual.

A câmera virtual do Chrome recebe as fotos de teste em movimento. Todo o resto é o
produto rodando: os quadros vão para a API e as caixas voltam em tempo real.

Uso: python scripts/record_demo.py --seconds 45 --out assets/video_build
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "assets/samples"
PORT = 8765
W, H = 640, 480
FPS = 15


def build_feed(images, target, seconds_each=6):
    """Cria o Y4M da câmera virtual com um leve zoom, como uma mão segurando o celular."""
    process = subprocess.Popen(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-pix_fmt", "yuv420p", "-f", "yuv4mpegpipe", str(target)],
        stdin=subprocess.PIPE,
    )
    total = seconds_each * FPS
    for path in images:
        image = Image.open(path).convert("RGB")
        scale = max(W / image.width, H / image.height)
        image = image.resize((round(image.width * scale) + 2, round(image.height * scale) + 2))
        left, top = (image.width - W) // 2, (image.height - H) // 2
        base = image.crop((left, top, left + W, top + H))
        for i in range(total):
            zoom = 1 + 0.08 * i / total
            cw, ch = W / zoom, H / zoom
            box = ((W - cw) / 2, (H - ch) / 2, (W + cw) / 2, (H + ch) / 2)
            frame = base.resize((W, H), Image.BILINEAR, box=box)
            process.stdin.write(np.asarray(frame).tobytes())
    process.stdin.close()
    process.wait()


def wait_for_api():
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("API não subiu")


def record_live(browser, out, seconds):
    context = browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(out / "raw"),
                                  record_video_size={"width": 1280, "height": 720}, permissions=["camera"])
    page = context.new_page()
    started = time.time()
    page.goto(f"http://127.0.0.1:{PORT}/")
    page.click("#toggle")
    page.wait_for_function("document.getElementById('perf').textContent.length > 0", timeout=30000)
    offset = time.time() - started
    readings = []
    end = time.time() + seconds
    while time.time() < end:
        readings.append(page.inner_text("#perf"))
        time.sleep(2)
    video_path = page.video.path()
    context.close()
    shutil.move(video_path, out / "live.webm")
    return offset, readings


def record_upload(browser, out, name, image):
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.goto(f"http://127.0.0.1:{PORT}/")
    with page.expect_response("**/v1/detections") as response:
        page.set_input_files("#file", str(image))
    body = response.value.json()
    page.wait_for_function("!document.querySelector('#result .status').textContent.startsWith('Analisando')")
    page.wait_for_timeout(300)
    page.screenshot(path=str(out / f"{name}.png"))
    context.close()
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=45)
    ap.add_argument("--out", type=Path, default=ROOT / "assets/video_build")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((SAMPLES / "manifest.json").read_text())
    feed = args.out / "camera.y4m"
    build_feed([SAMPLES / item["arquivo"] for item in manifest["live"]], feed)

    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--port", str(PORT), "--log-level", "warning"],
                              cwd=ROOT, env=os.environ.copy())
    try:
        wait_for_api()
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome", headless=True, args=[
                "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
                f"--use-file-for-fake-video-capture={feed}",
            ])
            offset, readings = record_live(browser, args.out, args.seconds)
            uploads = {name: record_upload(browser, args.out, f"upload_{name}", SAMPLES / item["arquivo"])
                       for name, item in manifest["uploads"].items()}
            browser.close()
    finally:
        server.terminate()
        server.wait()
    feed.unlink()
    (args.out / "demo.json").write_text(json.dumps(
        {"inicio_ao_vivo_s": offset, "leituras_ao_vivo": readings, "respostas": uploads}, ensure_ascii=False, indent=2))
    print("ao vivo:", readings[-5:])
    print({k: v["status"] for k, v in uploads.items()})


if __name__ == "__main__":
    main()
