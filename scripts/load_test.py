"""Teste de carga: envia fotos em paralelo para provocar saturação e disparar os alertas.

Uso: python scripts/load_test.py --url https://<app> --concurrency 24 --seconds 240
"""
import argparse
import asyncio
import collections
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent


async def worker(client, url, image, deadline, counts, latencies):
    while time.monotonic() < deadline:
        start = time.perf_counter()
        try:
            response = await client.post(f"{url}/v1/detections", files={"imagem": ("folha.jpg", image, "image/jpeg")})
            counts[response.status_code] += 1
        except httpx.HTTPError as exc:
            counts[type(exc).__name__] += 1
        latencies.append(time.perf_counter() - start)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--concurrency", type=int, default=24)
    ap.add_argument("--seconds", type=int, default=240)
    ap.add_argument("--image", type=Path, default=next((ROOT / "assets/samples").glob("*.jpg"), None))
    args = ap.parse_args()

    image = args.image.read_bytes()
    counts, latencies = collections.Counter(), []
    deadline = time.monotonic() + args.seconds
    async with httpx.AsyncClient(timeout=30) as client:
        await asyncio.gather(*(worker(client, args.url.rstrip("/"), image, deadline, counts, latencies)
                               for _ in range(args.concurrency)))
    latencies.sort()
    total = sum(counts.values())
    print(f"{total} requisições em {args.seconds}s ({total / args.seconds:.1f}/s)")
    print("por status:", dict(counts))
    if latencies:
        print(f"latência p50={latencies[len(latencies) // 2] * 1000:.0f} ms p95={latencies[int(len(latencies) * 0.95)] * 1000:.0f} ms")


if __name__ == "__main__":
    asyncio.run(main())
