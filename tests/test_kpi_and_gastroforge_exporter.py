from __future__ import annotations

import json
from pathlib import Path
import pytest
from src.table_monitor.analytics.gastroforge_exporter import (
    export_alerts_json,
    export_gastroforge_telemetry_json,
    export_sessions_csv,
)
from src.table_monitor.analytics.kpi_calculator import compute_salon_kpis
from src.table_monitor.domain.models import (
    AlertSeverity,
    OperationalAlert,
    TableSession,
    TableState,
)
from src.table_monitor.domain.state_machine import TableTracker


def test_compute_salon_kpis_diagnostics():
    states = {
        "Mesa 1": TableState.OCUPADA,
        "Mesa 2": TableState.LIBRE,
        "Mesa 3": TableState.POR_RECOGER,
        "Mesa 4": TableState.AUSENCIA_TEMPORAL,
    }

    sess1 = TableSession(
        session_id="s1",
        table_id="Mesa 1",
        start_time=0.0,
        end_time=120.0,
        first_dish_time=30.0,
        cleared_time=150.0,
        is_open=False,
    )
    # TPA = 30.0, TRM = 150 - 120 = 30.0, stay = 120.0

    alerts = [
        OperationalAlert(
            timestamp=10.0,
            table_id="Mesa 3",
            alert_type="HYGIENE_INCIDENT",
            message="Test",
            severity=AlertSeverity.CRITICAL,
        )
    ]

    # Caso 1: Con cola de espera -> debe alertar cuello de botella
    kpi_bottleneck = compute_salon_kpis(
        table_states=states,
        completed_sessions=[sess1],
        alerts=alerts,
        waiting_queue_count=3,
    )
    assert kpi_bottleneck.service_bottleneck_detected is True
    assert kpi_bottleneck.hygiene_incidents_count == 1
    assert kpi_bottleneck.avg_first_service_latency_seconds == 30.0
    assert kpi_bottleneck.avg_turnover_latency_seconds == 30.0

    # Caso 2: Sin cola de espera y 3 mesas libres de 4 -> debe alertar baja demanda
    empty_states = {f"Mesa {i}": TableState.LIBRE for i in range(1, 4)}
    empty_states["Mesa 4"] = TableState.OCUPADA
    kpi_low_demand = compute_salon_kpis(
        table_states=empty_states,
        completed_sessions=[],
        alerts=[],
        waiting_queue_count=0,
    )
    assert kpi_low_demand.low_demand_detected is True
    assert kpi_low_demand.service_bottleneck_detected is False


def test_export_gastroforge_artifacts(tmp_path: Path):
    trackers = {
        "Mesa 1": TableTracker("Mesa 1"),
        "Mesa 2": TableTracker("Mesa 2"),
    }
    trackers["Mesa 1"].state = TableState.OCUPADA

    kpis = compute_salon_kpis(
        table_states={"Mesa 1": TableState.OCUPADA, "Mesa 2": TableState.LIBRE},
        completed_sessions=[],
        alerts=[],
        waiting_queue_count=0,
    )

    json_file = tmp_path / "telemetry.json"
    csv_file = tmp_path / "sessions.csv"
    alerts_file = tmp_path / "alerts.json"

    export_gastroforge_telemetry_json(json_file, kpis, trackers, current_time_s=100.0)
    export_sessions_csv(csv_file, [])
    export_alerts_json(alerts_file, [])

    assert json_file.exists()
    assert csv_file.exists()
    assert alerts_file.exists()

    data = json.loads(json_file.read_text(encoding="utf-8"))
    assert data["system"] == "GastroForge-Vision-Ultralytics"
    assert "salon_summary" in data
    assert "kpis" in data
    assert len(data["tables"]) == 2
