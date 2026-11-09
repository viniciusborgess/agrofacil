"""Inferência com ONNX Runtime, sem PyTorch, para rodar em CPU barata."""
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image


@dataclass
class Detection:
    class_name: str
    confidence: float
    box: tuple  # x1, y1, x2, y2 normalizados entre 0 e 1


def _iou(box, boxes):
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / (area + areas - inter + 1e-9)


def nms(boxes, scores, iou_threshold):
    """NMS sem separar por classe: cada folha recebe um único diagnóstico."""
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        best = order[0]
        keep.append(int(best))
        order = order[1:][_iou(boxes[best], boxes[order[1:]]) <= iou_threshold]
    return keep


class Detector:
    def __init__(self, model_path, meta_path, threads=2):
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(model_path), options, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        meta = json.loads(Path(meta_path).read_text())
        self.names = meta["classes"]
        self.imgsz = meta["imgsz"]
        self.conf_decision = meta["conf_decision"]
        self.conf_min = meta["conf_min"]
        self.iou = meta["iou"]
        self.version = meta["version"]

    def _letterbox(self, image):
        w, h = image.size
        scale = self.imgsz / max(w, h)
        nw, nh = round(w * scale), round(h * scale)
        canvas = np.full((self.imgsz, self.imgsz, 3), 114, dtype=np.uint8)
        pad_x, pad_y = (self.imgsz - nw) // 2, (self.imgsz - nh) // 2
        canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = np.asarray(image.resize((nw, nh), Image.BILINEAR))
        return canvas, scale, pad_x, pad_y

    def predict(self, image):
        """Recebe uma imagem PIL RGB e devolve as detecções, da mais confiante para a menos."""
        w, h = image.size
        canvas, scale, pad_x, pad_y = self._letterbox(image)
        blob = (canvas.transpose(2, 0, 1)[None].astype(np.float32)) / 255.0
        output = self.session.run(None, {self.input_name: blob})[0][0]  # (4 + nc, N)

        xywh, class_scores = output[:4].T, output[4:].T
        ids = class_scores.argmax(1)
        scores = class_scores[np.arange(len(ids)), ids]
        mask = scores >= self.conf_min
        xywh, ids, scores = xywh[mask], ids[mask], scores[mask]
        if not len(scores):
            return []

        boxes = np.stack([
            (xywh[:, 0] - xywh[:, 2] / 2 - pad_x) / scale / w,
            (xywh[:, 1] - xywh[:, 3] / 2 - pad_y) / scale / h,
            (xywh[:, 0] + xywh[:, 2] / 2 - pad_x) / scale / w,
            (xywh[:, 1] + xywh[:, 3] / 2 - pad_y) / scale / h,
        ], axis=1).clip(0, 1)

        return [
            Detection(self.names[int(ids[i])], float(scores[i]), tuple(float(v) for v in boxes[i]))
            for i in nms(boxes, scores, self.iou)
        ]
