"""API de detecção do AgroFácil. As fotos são processadas em memória e nunca armazenadas."""
import io
import logging
import os
import secrets
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .detector import Detector
from .knowledge import AVISO, CLASSES, DOENCA, MENSAGENS, SAUDAVEL

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT / "weights/agrofacil.onnx"))
META_PATH = Path(os.getenv("META_PATH", ROOT / "weights/agrofacil.json"))
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "8")) * 1024 * 1024
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT", "4"))
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
Image.MAX_IMAGE_PIXELS = 40_000_000

log = logging.getLogger("agrofacil.vision")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="AgroFácil Vision API", version="1.0.0")
detector = Detector(MODEL_PATH, META_PATH)
slots = threading.BoundedSemaphore(MAX_CONCURRENT)

# Quatro sinais de ouro: latência, tráfego, erros (pelo status) e saturação.
REQUESTS = Counter("http_requests_total", "Requisições HTTP", ["method", "route", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Duração das requisições", ["route"],
                    buckets=(0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
IN_FLIGHT = Gauge("http_requests_in_flight", "Requisições em andamento")
INFERENCE = Histogram("model_inference_seconds", "Tempo de inferência do modelo",
                      buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1))
BUSY = Counter("inference_rejected_busy_total", "Requisições recusadas por falta de capacidade")
SLOTS_USED = Gauge("inference_slots_in_use", "Inferências simultâneas em execução")
SLOTS_MAX = Gauge("inference_slots_max", "Limite de inferências simultâneas")
OUTCOMES = Counter("detection_outcomes_total", "Resultado entregue ao produtor", ["status"])
SLOTS_MAX.set(MAX_CONCURRENT)


@app.middleware("http")
async def observe(request: Request, call_next):
    IN_FLIGHT.inc()
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    finally:
        IN_FLIGHT.dec()
        # Usa o molde da rota para não criar uma série por URL arbitrária.
        route = getattr(request.scope.get("route"), "path", "desconhecida")
        LATENCY.labels(route).observe(time.perf_counter() - start)
        REQUESTS.labels(request.method, route, str(status)).inc()


def describe(det):
    cultura, condicao, tipo, orientacao = CLASSES[det.class_name]
    return {
        "classe": det.class_name,
        "cultura": cultura,
        "condicao": condicao,
        "tipo": tipo,
        "confianca": round(det.confidence, 3),
        "confiavel": det.confidence >= detector.conf_decision,
        "caixa": {k: round(v, 4) for k, v in zip(("x1", "y1", "x2", "y2"), det.box)},
        "orientacao": orientacao,
    }


def decide(detections):
    """Só afirma algo acima do limiar calibrado; abaixo dele pede outra foto."""
    if not detections:
        return "nada_detectado"
    trusted = [d for d in detections if d["confiavel"]]
    if not trusted:
        return "inconclusivo"
    if any(d["tipo"] == DOENCA for d in trusted):
        return "possivel_doenca"
    return "folha_saudavel" if all(d["tipo"] == SAUDAVEL for d in trusted) else "inconclusivo"


def read_image(data):
    try:
        image = Image.open(io.BytesIO(data))
        return ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as exc:
        raise HTTPException(422, "O arquivo enviado não é uma imagem válida.") from exc


@app.get("/health")
def health():
    return {"status": "ok", "modelo": detector.version}


@app.get("/v1/classes")
def classes():
    return [
        {"classe": name, "cultura": info[0], "condicao": info[1], "tipo": info[2]}
        for name, info in CLASSES.items()
    ]


@app.post("/v1/detections")
def detections(imagem: UploadFile):
    data = imagem.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "A imagem é grande demais.")
    image = read_image(data)
    if not slots.acquire(blocking=False):
        BUSY.inc()
        raise HTTPException(503, "Serviço ocupado. Tente novamente em instantes.", headers={"Retry-After": "2"})
    SLOTS_USED.inc()
    try:
        start = time.perf_counter()
        found = [describe(d) for d in detector.predict(image)]
        elapsed = time.perf_counter() - start
    finally:
        SLOTS_USED.dec()
        slots.release()
    INFERENCE.observe(elapsed)
    elapsed_ms = round(elapsed * 1000, 1)

    status = decide(found)
    OUTCOMES.labels(status).inc()
    # Log operacional sem imagem, nome de arquivo ou dado do usuário.
    log.info("deteccao status=%s n=%d inferencia_ms=%.1f", status, len(found), elapsed_ms)
    return {
        "id": str(uuid.uuid4()),
        "modelo": detector.version,
        "status": status,
        "mensagem": MENSAGENS[status],
        "deteccoes": found,
        "revisao_humana_recomendada": status != "folha_saudavel",
        "aviso": AVISO,
        "inferencia_ms": elapsed_ms,
    }


@app.get("/metrics", include_in_schema=False)
def metrics(request: Request):
    """Métricas para o Prometheus. Em produção, exige o token definido em METRICS_TOKEN."""
    expected = f"Bearer {METRICS_TOKEN}"
    if METRICS_TOKEN and not secrets.compare_digest(request.headers.get("authorization", ""), expected):
        raise HTTPException(401, "Não autorizado.")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
def demo():
    return FileResponse(ROOT / "web/index.html")
