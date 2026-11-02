from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import List, Tuple
import cv2
import numpy as np


def _nms(boxes: List[List[float]], scores: List[float], iou_thresh: float = 0.3) -> List[int]:
    """Non-Maximum Suppression para eliminar cajas duplicadas de una misma mesa."""
    if len(boxes) == 0:
        return []
    np_boxes = np.array(boxes)
    np_scores = np.array(scores)
    x1, y1, x2, y2 = np_boxes[:, 0], np_boxes[:, 1], np_boxes[:, 2], np_boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = np_scores.argsort()[::-1]
    keep = []

    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        inds = np.where(ovr <= iou_thresh)[0]
        order = order[inds + 1]

    return keep


def calibrate_video_tables(
    video_path: str,
    output_json: str,
    output_preview_img: str,
    model_path: str = "docs/Archive/yolo26n.pt",
    conf: float = 0.20,
    expand_margin: float = 0.12,
) -> List[dict]:
    """Detecta automáticamente las mesas de un video y genera su configuración poligonal."""
    from ultralytics import YOLO

    cap = cv2.VideoCapture(video_path)
    ok, frame = cap.read()
    cap.release()

    if not ok or frame is None:
        raise ValueError(f"No se pudo leer el fotograma inicial del video: {video_path}")

    h_img, w_img = frame.shape[:2]
    model = YOLO(model_path)

    # Detectar dining tables (clase 60 de COCO)
    res = model.predict(frame, classes=[60], conf=conf, verbose=False)[0]

    raw_boxes = [b.xyxy[0].tolist() for b in res.boxes] if res.boxes is not None else []
    scores = [b.conf.item() for b in res.boxes] if res.boxes is not None else []

    # Filtrar cajas duplicadas con NMS
    keep_indices = _nms(raw_boxes, scores, iou_thresh=0.25)
    filtered_boxes = [raw_boxes[i] for i in keep_indices]

    # Ordenar mesas de arriba hacia abajo, izquierda a derecha
    filtered_boxes.sort(key=lambda b: (b[1], b[0]))

    mesas = []
    preview = frame.copy()

    for idx, box in enumerate(filtered_boxes, 1):
        x1, y1, x2, y2 = box
        bw, bh = x2 - x1, y2 - y1

        # Expandir la caja para abarcar las sillas y las personas sentadas
        mx = bw * expand_margin
        my = bh * expand_margin

        ex1 = max(0, int(x1 - mx))
        ey1 = max(0, int(y1 - my))
        ex2 = min(w_img, int(x2 + mx))
        ey2 = min(h_img, int(y2 + my))

        polygon = [
            [ex1, ey1],
            [ex2, ey1],
            [ex2, ey2],
            [ex1, ey2],
        ]

        table_id = f"Mesa {idx}"
        mesas.append({"id": table_id, "puntos": polygon})

        # Dibujar en la imagen de preview
        pts = np.array(polygon, np.int32)
        cv2.polylines(preview, [pts], True, (0, 255, 0), 2)
        cv2.putText(
            preview,
            table_id,
            (ex1 + 8, ey1 + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )

    # Guardar JSON
    p_json = Path(output_json)
    p_json.parent.mkdir(parents=True, exist_ok=True)
    p_json.write_text(json.dumps({"mesas": mesas}, indent=2), encoding="utf-8")

    # Guardar imagen anotada de verificación
    p_img = Path(output_preview_img)
    p_img.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p_img), preview)

    return mesas


def auto_calibrate_all_inputs(
    input_dir: str = "input",
    config_dir: str = "config",
    model_path: str = "docs/Archive/yolo26n.pt",
) -> dict:
    """Calibra automáticamente todos los videos compatibles encontrados en el directorio input."""
    video_extensions = ("*.mp4", "*.avi", "*.mov", "*.webm", "*.mkv")
    videos = []
    for ext in video_extensions:
        videos.extend(glob.glob(os.path.join(input_dir, ext)))

    results = {}
    for vid in sorted(videos):
        basename = os.path.splitext(os.path.basename(vid))[0]
        # Limpieza de caracteres especiales en nombres de archivo
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in basename)
        out_json = os.path.join(config_dir, f"mesas_{safe_name}.json")
        out_preview = os.path.join(config_dir, "frames", f"{safe_name}_calibradas.jpg")

        try:
            mesas = calibrate_video_tables(vid, out_json, out_preview, model_path=model_path)
            results[vid] = {
                "tables_count": len(mesas),
                "config_json": out_json,
                "preview_image": out_preview,
            }
            print(f"✔ Calibrado: {os.path.basename(vid)} -> {len(mesas)} mesas registradas en {out_json}")
        except Exception as e:
            print(f"✖ Error calibrando {vid}: {e}")

    return results


if __name__ == "__main__":
    auto_calibrate_all_inputs()
