from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple
import cv2
import numpy as np
from src.table_monitor.domain.models import DetectionBox, TableConfig


def point_in_polygon(point: Tuple[float, float], polygon: Sequence[Tuple[float, float]]) -> bool:
    """Algoritmo de Ray Casting (Jordan curve theorem) en Python puro.
    
    Determina si un punto (x, y) está dentro de un polígono 2D.
    """
    x, y = point
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        x_inters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= x_inters:
                            inside = not inside
        p1x, p1y = p2x, p2y

    return inside


def polygon_area(polygon: Sequence[Tuple[float, float]]) -> float:
    """Calcula el área de un polígono 2D mediante la fórmula Shoelace (Gauss)."""
    n = len(polygon)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    return abs(area) / 2.0


def get_table_dimensions(polygon: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    """Obtiene el ancho y alto del bounding box de un polígono de mesa."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (max(xs) - min(xs), max(ys) - min(ys))


def distance_point_to_polygon(point: Tuple[float, float], polygon: Sequence[Tuple[float, float]]) -> float:
    """Calcula la distancia con signo desde un punto al contorno del polígono mediante cv2.pointPolygonTest.
    
    Retorna:
    >= 0: El punto está dentro del polígono.
    < 0: El punto está fuera; el valor absoluto es la distancia euclidiana exacta en píxeles.
    """
    pts = np.array(polygon, np.float32).reshape((-1, 1, 2))
    return float(cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), True))


def is_standing_person(box: DetectionBox) -> bool:
    """Determina si la persona detectada está de pie (ej. transeúnte o personal caminando).
    
    Una persona de pie tiene relación alto/ancho > 1.90. Un comensal sentado tiene oclusión
    inferior por la mesa y la silla (relación 0.9 - 1.6).
    """
    w = max(1.0, box.x2 - box.x1)
    h = max(1.0, box.y2 - box.y1)
    return (h / w) >= 1.90


def match_box_to_tables(
    box: DetectionBox,
    tables: List[TableConfig],
    seating_halo_factor: float = 0.22,
) -> Optional[Tuple[str, float]]:
    """Asocia competitivamente una persona a su mesa más cercana evitando falsos positivos.
    
    Aplica:
    1. Distancia euclidiana exacta punto-polígono para centroide y base del comensal.
    2. Margen de tolerancia de silla ajustado proporcionalmente al tamaño real de cada mesa (22%).
    3. Restricción para personas de pie caminando por pasillos contiguos.
    4. Exclusión mutua: cada persona solo puede pertenecer a la mesa más cercana.
    """
    best_table_id: Optional[str] = None
    best_dist = -float("inf")
    standing = is_standing_person(box)

    for table in tables:
        tw, th = get_table_dimensions(table.polygon)
        # Margen ajustado: 22% del tamaño menor de la mesa, con cota mínima de 15px
        base_margin = max(15.0, min(tw, th) * seating_halo_factor)
        # Si la persona está de pie caminando, reducir el margen para no capturar transeúntes
        allowed_margin = base_margin * 0.55 if standing else base_margin

        pts = np.array(table.polygon, np.float32).reshape((-1, 1, 2))
        d_center = float(cv2.pointPolygonTest(pts, (float(box.center[0]), float(box.center[1])), True))
        d_base = float(cv2.pointPolygonTest(pts, (float(box.base[0]), float(box.base[1])), True))

        # El comensal sentado tiene al menos su base o centro dentro o muy cerca de la mesa
        d_effective = max(d_center, d_base)

        if d_effective >= -allowed_margin:
            if d_effective > best_dist:
                best_dist = d_effective
                best_table_id = table.table_id

    if best_table_id is not None:
        return (best_table_id, best_dist)
    return None


def is_box_in_table(
    box: DetectionBox,
    table: TableConfig,
    criterion: str = "chair_aware",
) -> bool:
    """Verifica si una detección pertenece al espacio de la mesa según el criterio seleccionado."""
    if criterion == "center":
        return point_in_polygon(box.center, table.polygon)
    elif criterion == "base":
        return point_in_polygon(box.base, table.polygon)
    match = match_box_to_tables(box, [table])
    return match is not None


def evaluate_table_presence(
    boxes: List[DetectionBox],
    tables: List[TableConfig],
    criterion: str = "chair_aware",
) -> Dict[str, bool]:
    """Evalúa la presencia de detecciones en cada mesa, asignando cada persona a su mesa más cercana."""
    presence: Dict[str, bool] = {table.table_id: False for table in tables}

    if criterion == "center":
        for table in tables:
            for box in boxes:
                if point_in_polygon(box.center, table.polygon):
                    presence[table.table_id] = True
                    break
        return presence

    # Modo chair_aware de alta precisión
    for box in boxes:
        match = match_box_to_tables(box, tables)
        if match:
            table_id, _ = match
            presence[table_id] = True

    return presence
