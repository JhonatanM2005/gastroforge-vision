from __future__ import annotations

import pytest
from src.table_monitor.domain.models import DetectionBox, TableConfig
from src.table_monitor.geometry.spatial import (
    evaluate_table_presence,
    is_box_in_table,
    point_in_polygon,
    polygon_area,
)


def test_point_in_polygon():
    # Cuadrilátero 100x100
    poly = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)]

    # Puntos dentro
    assert point_in_polygon((50.0, 50.0), poly) is True
    assert point_in_polygon((10.0, 10.0), poly) is True

    # Puntos fuera
    assert point_in_polygon((150.0, 50.0), poly) is False
    assert point_in_polygon((-10.0, 50.0), poly) is False
    assert point_in_polygon((50.0, 150.0), poly) is False


def test_polygon_area():
    # Rectángulo 40 x 50 = 2000
    rect = [(0.0, 0.0), (40.0, 0.0), (40.0, 50.0), (0.0, 50.0)]
    assert polygon_area(rect) == 2000.0

    # Triángulo base 10, altura 10 = 50
    tri = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)]
    assert polygon_area(tri) == 50.0


def test_evaluate_table_presence():
    table1 = TableConfig(
        table_id="table-1",
        polygon=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    )
    table2 = TableConfig(
        table_id="table-2",
        polygon=[(200.0, 0.0), (300.0, 0.0), (300.0, 100.0), (200.0, 100.0)],
    )

    box_in_t1 = DetectionBox(
        x1=40.0, y1=40.0, x2=60.0, y2=60.0, class_name="person", confidence=0.85
    )
    box_outside = DetectionBox(
        x1=500.0, y1=500.0, x2=550.0, y2=550.0, class_name="person", confidence=0.9
    )

    presence = evaluate_table_presence([box_in_t1, box_outside], [table1, table2])
    assert presence["table-1"] is True
    assert presence["table-2"] is False
