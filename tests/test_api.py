"""Testes do contrato da API. Exigem weights/agrofacil.onnx e weights/agrofacil.json."""
import io
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import main  # noqa: E402
from api.detector import Detection, nms  # noqa: E402
from api.knowledge import CLASSES, DOENCA, SAUDAVEL  # noqa: E402

client = TestClient(main.app)
SAMPLES = sorted((ROOT / "assets/samples").glob("*.jpg"))


def jpeg(size=(320, 240), color=(40, 120, 40)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, "JPEG")
    return buffer.getvalue()


def post(data, name="folha.jpg", mime="image/jpeg"):
    return client.post("/v1/detections", files={"imagem": (name, data, mime)})


def det(tipo_class, conf):
    return {"classe": tipo_class, "tipo": CLASSES[tipo_class][2], "confiavel": conf >= main.detector.conf_decision}


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_every_model_class_has_guidance():
    assert set(main.detector.names) == set(CLASSES)
    assert all(info[2] in (DOENCA, SAUDAVEL) and info[3] for info in CLASSES.values())


def test_contract_on_valid_image():
    r = post(jpeg())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"possivel_doenca", "folha_saudavel", "inconclusivo", "nada_detectado"}
    assert body["mensagem"] and body["aviso"] and body["modelo"]
    assert isinstance(body["deteccoes"], list)


@pytest.mark.parametrize("sample", SAMPLES, ids=lambda p: p.stem)
def test_boxes_are_normalized_on_real_photos(sample):
    body = post(sample.read_bytes()).json()
    for d in body["deteccoes"]:
        box = d["caixa"]
        assert 0 <= box["x1"] <= box["x2"] <= 1 and 0 <= box["y1"] <= box["y2"] <= 1
        assert 0 <= d["confianca"] <= 1 and d["orientacao"]


def test_rejects_non_image():
    r = post(b"isto nao e uma imagem", "a.txt", "text/plain")
    assert r.status_code == 422


def test_rejects_truncated_image():
    assert post(jpeg()[:100]).status_code == 422


def test_rejects_oversized_upload():
    assert post(b"0" * (main.MAX_BYTES + 1)).status_code == 413


def test_missing_file_is_rejected():
    assert client.post("/v1/detections").status_code == 422


def test_busy_service_answers_503(monkeypatch):
    class Busy:
        def acquire(self, blocking=True):
            return False
    monkeypatch.setattr(main, "slots", Busy())
    r = post(jpeg())
    assert r.status_code == 503 and r.headers["retry-after"]


def test_decision_rules():
    high, low = 0.99, 0.01
    sick, healthy = "Tomato leaf late blight", "Tomato leaf"
    assert main.decide([]) == "nada_detectado"
    assert main.decide([det(sick, low)]) == "inconclusivo"
    assert main.decide([det(healthy, high)]) == "folha_saudavel"
    assert main.decide([det(sick, high), det(healthy, high)]) == "possivel_doenca"


def test_human_review_flag_follows_status(monkeypatch):
    monkeypatch.setattr(main.detector, "predict", lambda img: [Detection("Tomato leaf late blight", 0.99, (0, 0, 1, 1))])
    body = post(jpeg()).json()
    assert body["status"] == "possivel_doenca" and body["revisao_humana_recomendada"] is True
    monkeypatch.setattr(main.detector, "predict", lambda img: [Detection("Tomato leaf", 0.99, (0, 0, 1, 1))])
    assert post(jpeg()).json()["revisao_humana_recomendada"] is False


def test_logs_do_not_contain_filename(caplog):
    with caplog.at_level(logging.INFO, logger="agrofacil.vision"):
        post(jpeg(), name="joao-da-silva-sitio-boa-vista.jpg")
    assert "joao" not in caplog.text


def test_nothing_is_written_to_disk(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    post(jpeg())
    assert list(tmp_path.iterdir()) == []


def test_nms_keeps_one_box_per_leaf_across_classes():
    boxes = np.array([[0, 0, 1, 1], [0.01, 0.01, 1, 1], [2, 2, 3, 3]], dtype=float)
    assert nms(boxes, np.array([0.9, 0.8, 0.7]), 0.5) == [0, 2]
    assert json.dumps(client.get("/v1/classes").json(), ensure_ascii=False)


def test_metrics_expose_golden_signals():
    post(jpeg())
    text = client.get("/metrics").text
    for name in ("http_requests_total", "http_request_duration_seconds", "inference_slots_in_use", "model_inference_seconds"):
        assert name in text
    assert 'route="/v1/detections"' in text


def test_metrics_require_token_when_configured(monkeypatch):
    monkeypatch.setattr(main, "METRICS_TOKEN", "segredo-de-teste")
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer errado"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer segredo-de-teste"}).status_code == 200
