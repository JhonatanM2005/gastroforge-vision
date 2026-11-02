from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.table_monitor.analytics.kpi_calculator import SalonKPISummary
from src.table_monitor.domain.models import OperationalAlert, TableSession
from src.table_monitor.domain.state_machine import TableTracker


def _format_time(seconds: float, base_datetime: Optional[datetime]) -> str:
    if base_datetime:
        dt = base_datetime + timedelta(seconds=seconds)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    m = int(seconds // 60)
    s = int(seconds % 60)
    h = int(m // 60)
    m = int(m % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def build_gastroforge_telemetry_dict(
    kpis: SalonKPISummary,
    trackers: Dict[str, TableTracker],
    current_time_s: float,
    base_datetime: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Construye el diccionario de telemetría con el esquema oficial de GastroForge-Academic."""
    timestamp_iso = (
        (base_datetime + timedelta(seconds=current_time_s)).isoformat()
        if base_datetime
        else datetime.utcnow().isoformat() + "Z"
    )

    tables_payload = []
    for t_id, tr in trackers.items():
        occ_sec = tr.get_current_occupied_duration(current_time_s)
        session = tr.get_active_or_last_session()
        tables_payload.append(
            {
                "table_id": t_id,
                "state": tr.state.value,
                "current_session_id": session.session_id if session else None,
                "is_occupied": tr.state.value in ("ocupada", "ausencia_temporal"),
                "occupied_duration_seconds": round(occ_sec, 1),
                "occupied_duration_formatted": _format_time(occ_sec, None),
                "first_dish_served": bool(session and session.first_dish_time is not None),
                "has_hygiene_incident": bool(session and session.hygiene_incident),
            }
        )

    return {
        "system": "GastroForge-Vision-Ultralytics",
        "timestamp": timestamp_iso,
        "current_time_seconds": round(current_time_s, 2),
        "salon_summary": {
            "total_tables": kpis.total_tables,
            "free_tables": kpis.free_tables,
            "occupied_tables": kpis.occupied_tables,
            "pending_clean_tables": kpis.pending_clean_tables,
            "cleaning_tables": kpis.cleaning_tables,
            "temporary_absence_tables": kpis.temporary_absence_tables,
            "occupancy_rate_percent": kpis.occupancy_rate_percent,
        },
        "kpis": {
            "avg_first_service_latency_seconds": kpis.avg_first_service_latency_seconds,
            "avg_turnover_latency_seconds": kpis.avg_turnover_latency_seconds,
            "avg_stay_duration_seconds": kpis.avg_stay_duration_seconds,
            "hygiene_incidents_count": kpis.hygiene_incidents_count,
            "waiting_queue_count": kpis.waiting_queue_count,
            "service_bottleneck_detected": kpis.service_bottleneck_detected,
            "low_demand_detected": kpis.low_demand_detected,
            "operational_diagnosis": kpis.operational_diagnosis,
        },
        "tables": tables_payload,
    }


def export_gastroforge_telemetry_json(
    output_path: str | Path,
    kpis: SalonKPISummary,
    trackers: Dict[str, TableTracker],
    current_time_s: float,
    base_datetime: Optional[datetime] = None,
) -> Path:
    """Exporta el estado completo de telemetría del salón en un JSON consumible por la API GastroForge."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    data = build_gastroforge_telemetry_dict(
        kpis=kpis,
        trackers=trackers,
        current_time_s=current_time_s,
        base_datetime=base_datetime,
    )

    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_file


def sync_telemetry_to_api(
    telemetry_data: Dict[str, Any],
    api_url: str,
    timeout_seconds: float = 5.0,
) -> Dict[str, Any]:
    """Envía el payload de telemetría por HTTP POST al endpoint REST de GastroForge-Academic."""
    json_bytes = json.dumps(telemetry_data).encode("utf-8")
    req = urllib.request.Request(
        url=api_url,
        data=json_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "GastroForge-Vision-Client/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
            try:
                parsed_body = json.loads(response_body)
            except Exception:
                parsed_body = response_body
            return {
                "success": 200 <= status_code < 300,
                "status_code": status_code,
                "data": parsed_body,
                "error": None,
            }
    except urllib.error.HTTPError as err:
        err_msg = err.read().decode("utf-8") if err.fp else str(err)
        return {
            "success": False,
            "status_code": err.code,
            "data": None,
            "error": f"HTTP {err.code}: {err_msg}",
        }
    except urllib.error.URLError as err:
        return {
            "success": False,
            "status_code": None,
            "data": None,
            "error": f"Error de conexión ({api_url}): {err.reason}",
        }
    except Exception as err:
        return {
            "success": False,
            "status_code": None,
            "data": None,
            "error": f"Error inesperado al sincronizar con la API: {str(err)}",
        }


def export_sessions_csv(
    output_path: str | Path,
    sessions: List[TableSession],
    base_datetime: Optional[datetime] = None,
) -> Path:
    """Exporta el registro tabular de servicios y rotaciones de mesas."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    with open(out_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "session_id",
                "table_id",
                "start_time_s",
                "end_time_s",
                "duration_seconds",
                "duration_formatted",
                "tpa_first_service_s",
                "trm_turnover_s",
                "hygiene_incident",
                "is_open",
                "start_timestamp",
                "end_timestamp",
            ]
        )
        for s in sorted(sessions, key=lambda x: x.start_time):
            dur = s.duration_seconds
            writer.writerow(
                [
                    s.session_id,
                    s.table_id,
                    round(s.start_time, 1),
                    round(s.end_time, 1) if s.end_time is not None else "",
                    round(dur, 1),
                    _format_time(dur, None),
                    round(s.first_service_latency, 1) if s.first_service_latency is not None else "",
                    round(s.turnover_latency, 1) if s.turnover_latency is not None else "",
                    int(s.hygiene_incident),
                    int(s.is_open),
                    _format_time(s.start_time, base_datetime) if base_datetime else "",
                    _format_time(s.end_time, base_datetime) if (base_datetime and s.end_time is not None) else "",
                ]
            )

    return out_file


def export_alerts_json(output_path: str | Path, alerts: List[OperationalAlert]) -> Path:
    """Exporta el log cronológico de alertas operativas del restaurante."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    payload = [
        {
            "timestamp_seconds": round(a.timestamp, 1),
            "table_id": a.table_id,
            "alert_type": a.alert_type,
            "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
            "message": a.message,
        }
        for a in alerts
    ]

    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_file
