from __future__ import annotations

from typing import Dict, List, Sequence, Tuple
import cv2
import numpy as np
from src.table_monitor.analytics.kpi_calculator import SalonKPISummary
from src.table_monitor.domain.models import DetectionBox, TableConfig, TableState
from src.table_monitor.domain.state_machine import TableTracker

STATE_COLORS = {
    TableState.LIBRE: (0, 190, 0),  # Verde
    TableState.EN_CONFIRMACION: (0, 215, 255),  # Amarillo
    TableState.OCUPADA: (0, 0, 220),  # Rojo
    TableState.AUSENCIA_TEMPORAL: (220, 160, 0),  # Azul cian
    TableState.POR_RECOGER: (0, 140, 255),  # Naranja
    TableState.LIMPIANDO: (255, 180, 0),  # Celeste brillante (higienizando)
}

STATE_LABELS = {
    TableState.LIBRE: "LIBRE",
    TableState.EN_CONFIRMACION: "VERIFICANDO...",
    TableState.OCUPADA: "OCUPADA",
    TableState.AUSENCIA_TEMPORAL: "PAUSA (BAÑO)",
    TableState.POR_RECOGER: "POR RECOGER",
    TableState.LIMPIANDO: "HIGIENIZANDO",
}


def apply_privacy_blur(img: np.ndarray, boxes: Sequence[DetectionBox]) -> np.ndarray:
    """Aplica difuminado gaussiano sobre las personas detectadas para proteger su identidad (Ley 1581)."""
    h_img, w_img = img.shape[:2]
    for box in boxes:
        x1, y1 = max(0, int(box.x1)), max(0, int(box.y1))
        x2, y2 = min(w_img, int(box.x2)), min(h_img, int(box.y2))
        w_box, h_box = x2 - x1, y2 - y1
        if w_box > 4 and h_box > 4:
            k = max(15, (w_box // 3) | 1)
            img[y1:y2, x1:x2] = cv2.GaussianBlur(img[y1:y2, x1:x2], (k, k), 0)
    return img


def format_duration(seconds: float) -> str:
    s = int(max(0, seconds))
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def annotate_salon_frame(
    frame: np.ndarray,
    tables: List[TableConfig],
    trackers: Dict[str, TableTracker],
    current_time_s: float,
    people_boxes: List[DetectionBox],
    kpis: SalonKPISummary,
    blur_privacy: bool = True,
) -> np.ndarray:
    """Dibuja polígonos, cronómetros, difuminado de privacidad y panel HUD de control."""
    canvas = frame.copy()

    # 1. Privacidad si está habilitada
    if blur_privacy and people_boxes:
        canvas = apply_privacy_blur(canvas, people_boxes)

    # 2. Dibujar polígonos de mesas y estados
    for table in tables:
        tracker = trackers.get(table.table_id)
        if not tracker:
            continue

        state = tracker.state
        color = STATE_COLORS.get(state, (200, 200, 200))
        pts = np.array(table.polygon, np.int32)

        # Relleno semi-transparente
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.28, canvas, 0.72, 0, canvas)
        cv2.polylines(canvas, [pts], True, color, 2, cv2.LINE_AA)

        # Centroide para etiquetas
        cx, cy = int(np.mean(pts[:, 0])), int(np.mean(pts[:, 1]))
        state_txt = STATE_LABELS.get(state, state.value)
        timer_txt = ""

        if state in (TableState.OCUPADA, TableState.AUSENCIA_TEMPORAL):
            dur = tracker.get_current_occupied_duration(current_time_s)
            timer_txt = format_duration(dur)

        label_primary = f"{table.table_id}: {state_txt}"

        # Dibujar cajita de texto
        font = cv2.FONT_HERSHEY_SIMPLEX
        (w1, h1), _ = cv2.getTextSize(label_primary, font, 0.55, 2)
        cv2.rectangle(canvas, (cx - w1 // 2 - 4, cy - h1 - 4), (cx + w1 // 2 + 4, cy + 4), (0, 0, 0), -1)
        cv2.putText(canvas, label_primary, (cx - w1 // 2, cy), font, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

        if timer_txt:
            (w2, h2), _ = cv2.getTextSize(timer_txt, font, 0.65, 2)
            cv2.rectangle(canvas, (cx - w2 // 2 - 4, cy + 8), (cx + w2 // 2 + 4, cy + h2 + 12), (0, 0, 0), -1)
            cv2.putText(canvas, timer_txt, (cx - w2 // 2, cy + h2 + 8), font, 0.65, (0, 255, 255), 2, cv2.LINE_AA)

    # 3. HUD Superior (Dashboard Operativo en Vivo)
    hud_h = 50
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], hud_h), (25, 25, 25), -1)

    hud_txt1 = (
        f"GastroForge Vision | Tot: {kpis.total_tables} | "
        f"Libres: {kpis.free_tables} | Ocup: {kpis.occupied_tables} | "
        f"Sucia: {kpis.pending_clean_tables} | Limp: {kpis.cleaning_tables} | "
        f"Baño: {kpis.temporary_absence_tables} | Ocupación: {kpis.occupancy_rate_percent}%"
    )
    cv2.putText(canvas, hud_txt1, (15, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2, cv2.LINE_AA)

    hud_txt2 = (
        f"TPA (1er Plato): {kpis.avg_first_service_latency_seconds or 0:.0f}s | "
        f"TRM (Limpieza): {kpis.avg_turnover_latency_seconds or 0:.0f}s | "
        f"Incidencias Higiene: {kpis.hygiene_incidents_count}"
    )
    color_hud2 = (0, 0, 255) if kpis.hygiene_incidents_count > 0 else (180, 255, 180)
    cv2.putText(canvas, hud_txt2, (15, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.50, color_hud2, 1, cv2.LINE_AA)

    return canvas
