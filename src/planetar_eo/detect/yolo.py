"""YOLO-based vessel detector.

Wraps Ultralytics YOLO and filters to vessel-relevant COCO classes. Default
is yolo11n.pt (boat is class 8 in COCO). Fine-tuned marine checkpoints can be
swapped in by passing model=<path>.

A Detection is the per-vessel record we publish on the bus.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np

log = logging.getLogger(__name__)

# COCO classes that are vessels or near-vessel (we accept boat; surfboard etc.
# are intentionally excluded). Custom marine checkpoints may extend this.
VESSEL_CLASS_IDS: set[int] = {8}  # boat


@dataclass
class Detection:
    source_id: str
    ts_ns: int
    frame_seq: int
    cls: int
    cls_name: str
    conf: float
    bbox_xyxy: tuple[float, float, float, float]  # normalized 0..1
    crop_jpeg: bytes | None = field(default=None, repr=False)

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "ts_ns": self.ts_ns,
            "frame_seq": self.frame_seq,
            "cls": self.cls,
            "cls_name": self.cls_name,
            "conf": round(self.conf, 4),
            "bbox_xyxy": [round(v, 5) for v in self.bbox_xyxy],
        }


class YoloVesselDetector:
    def __init__(
        self,
        model: str = "yolo11n.pt",
        conf: float = 0.25,
        iou: float = 0.45,
        imgsz: int = 640,
        device: str | None = None,
        keep_classes: Iterable[int] | None = None,
        emit_crops: bool = False,
    ) -> None:
        self.model_path = model
        self.conf = conf
        self.iou = iou
        self.imgsz = imgsz
        self.device = device
        self.keep_classes = set(keep_classes) if keep_classes is not None else VESSEL_CLASS_IDS
        self.emit_crops = emit_crops
        self._model = None  # lazy

    def _ensure_loaded(self):
        if self._model is None:
            try:
                from ultralytics import YOLO  # type: ignore[import-not-found]
            except ImportError as e:  # pragma: no cover
                raise RuntimeError(
                    "ultralytics not installed. `pip install -e .[ml]` to enable detection."
                ) from e
            log.info("loading YOLO model %s", self.model_path)
            self._model = YOLO(self.model_path)
        return self._model

    def infer(self, source_id: str, ts_ns: int, frame_seq: int, img_bgr: np.ndarray) -> list[Detection]:
        model = self._ensure_loaded()
        h, w = img_bgr.shape[:2]
        results = model.predict(
            img_bgr,
            conf=self.conf,
            iou=self.iou,
            imgsz=self.imgsz,
            device=self.device,
            verbose=False,
        )
        out: list[Detection] = []
        if not results:
            return out
        r = results[0]
        boxes = getattr(r, "boxes", None)
        if boxes is None or len(boxes) == 0:
            return out
        names = r.names if hasattr(r, "names") else {}
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.asarray(boxes.xyxy)
        cls = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else np.asarray(boxes.cls)
        conf = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.asarray(boxes.conf)
        for i in range(len(xyxy)):
            c = int(cls[i])
            if c not in self.keep_classes:
                continue
            x1, y1, x2, y2 = (float(v) for v in xyxy[i])
            crop_jpeg = None
            if self.emit_crops:
                import cv2  # type: ignore[import-not-found]
                xi1, yi1, xi2, yi2 = max(0, int(x1)), max(0, int(y1)), min(w, int(x2)), min(h, int(y2))
                if xi2 > xi1 and yi2 > yi1:
                    crop = img_bgr[yi1:yi2, xi1:xi2]
                    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ok:
                        crop_jpeg = bytes(buf)
            out.append(
                Detection(
                    source_id=source_id,
                    ts_ns=ts_ns,
                    frame_seq=frame_seq,
                    cls=c,
                    cls_name=str(names.get(c, str(c))),
                    conf=float(conf[i]),
                    bbox_xyxy=(x1 / w, y1 / h, x2 / w, y2 / h),
                    crop_jpeg=crop_jpeg,
                )
            )
        return out
