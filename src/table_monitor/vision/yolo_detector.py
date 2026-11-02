from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np
from src.table_monitor.domain.models import DetectionBox

COCO_DISH_CLASSES = {"cup", "bowl", "wine glass", "fork", "knife", "spoon", "bottle"}


class YOLOTableDetector:
    """Detector de visión por computador basado en Ultralytics YOLO."""

    def __init__(self, model_path: str = "docs/Archive/yolo26n.pt"):
        from ultralytics import YOLO

        resolved_path = Path(model_path)
        if not resolved_path.exists():
            # Si no está en la ruta local, intentar en la carpeta docs/Archive o descargar por defecto
            alt_path = Path("docs/Archive/yolo26n.pt")
            if alt_path.exists():
                resolved_path = alt_path
            else:
                resolved_path = Path("yolo11n.pt")

        self.model = YOLO(str(resolved_path))
        self.names = self.model.names

        self.person_class_ids = [k for k, v in self.names.items() if v == "person"]
        self.dish_class_ids = [k for k, v in self.names.items() if v in COCO_DISH_CLASSES]

    def detect(
        self,
        frame: np.ndarray,
        conf: float = 0.3,
        imgsz: int = 640,
        detect_dishes: bool = True,
    ) -> Tuple[List[DetectionBox], List[DetectionBox]]:
        """Ejecuta inferencia sobre el fotograma y extrae cajas de personas y vajilla."""
        target_classes = list(self.person_class_ids)
        if detect_dishes:
            target_classes.extend(self.dish_class_ids)

        if not target_classes:
            return [], []

        results = self.model.predict(
            frame,
            conf=conf,
            imgsz=imgsz,
            classes=target_classes,
            verbose=False,
        )

        people_boxes: List[DetectionBox] = []
        dish_boxes: List[DetectionBox] = []

        if not results or len(results) == 0:
            return people_boxes, dish_boxes

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return people_boxes, dish_boxes

        xyxy = boxes.xyxy.cpu().numpy()
        confs = boxes.conf.cpu().numpy()
        cls_ids = boxes.cls.cpu().numpy().astype(int)

        for i in range(len(xyxy)):
            box = xyxy[i]
            c = float(confs[i])
            cls_id = int(cls_ids[i])
            cls_name = self.names.get(cls_id, str(cls_id))

            det_box = DetectionBox(
                x1=float(box[0]),
                y1=float(box[1]),
                x2=float(box[2]),
                y2=float(box[3]),
                class_name=cls_name,
                confidence=c,
            )

            if cls_id in self.person_class_ids:
                people_boxes.append(det_box)
            elif cls_id in self.dish_class_ids:
                dish_boxes.append(det_box)

        return people_boxes, dish_boxes
