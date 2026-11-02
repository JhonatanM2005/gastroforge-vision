from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import urllib.error
from src.table_monitor.analytics.gastroforge_exporter import (
    build_gastroforge_telemetry_dict,
    sync_telemetry_to_api,
)
from src.table_monitor.analytics.kpi_calculator import SalonKPISummary
from src.table_monitor.domain.models import TableState
from src.table_monitor.domain.state_machine import TableTracker


def test_build_gastroforge_telemetry_dict_schema():
    kpis = SalonKPISummary(
        total_tables=2,
        free_tables=1,
        occupied_tables=1,
        pending_clean_tables=0,
        cleaning_tables=0,
        temporary_absence_tables=0,
        occupancy_rate_percent=50.0,
        avg_first_service_latency_seconds=12.0,
        avg_turnover_latency_seconds=30.0,
        avg_stay_duration_seconds=60.0,
        hygiene_incidents_count=0,
        waiting_queue_count=0,
        service_bottleneck_detected=False,
        low_demand_detected=False,
        operational_diagnosis="OPERACION_BALANCEADA",
    )
    tr1 = TableTracker("Mesa 1")
    tr1.state = TableState.OCUPADA
    tr2 = TableTracker("Mesa 2")
    tr2.state = TableState.LIBRE

    trackers = {"Mesa 1": tr1, "Mesa 2": tr2}
    payload = build_gastroforge_telemetry_dict(kpis, trackers, 15.0)

    assert payload["system"] == "GastroForge-Vision-Ultralytics"
    assert "timestamp" in payload
    assert payload["current_time_seconds"] == 15.0
    assert payload["salon_summary"]["total_tables"] == 2
    assert payload["salon_summary"]["occupied_tables"] == 1
    assert len(payload["tables"]) == 2
    assert payload["tables"][0]["table_id"] == "Mesa 1"
    assert payload["tables"][0]["is_occupied"] is True


def test_sync_telemetry_to_api_success():
    mock_response = MagicMock()
    mock_response.getcode.return_value = 201
    mock_response.read.return_value = json.dumps({"success": True, "ingestedTables": 2}).encode("utf-8")
    mock_response.__enter__.return_value = mock_response

    payload = {"system": "GastroForge-Vision-Ultralytics", "tables": []}

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = sync_telemetry_to_api(payload, "http://localhost:3000/api/v1/telemetry/ingest")
        assert result["success"] is True
        assert result["status_code"] == 201
        assert result["data"]["success"] is True


def test_sync_telemetry_to_api_connection_error():
    payload = {"system": "GastroForge-Vision-Ultralytics", "tables": []}

    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        result = sync_telemetry_to_api(payload, "http://127.0.0.1:9999/api/v1/telemetry/ingest")
        assert result["success"] is False
        assert result["status_code"] is None
        assert "Error de conexión" in result["error"]
