from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
from src.table_monitor.domain.models import OperationalAlert, TableSession, TableState


@dataclass
class SalonKPISummary:
    total_tables: int
    free_tables: int
    occupied_tables: int
    pending_clean_tables: int
    cleaning_tables: int
    temporary_absence_tables: int
    occupancy_rate_percent: float

    avg_first_service_latency_seconds: Optional[float]
    avg_turnover_latency_seconds: Optional[float]
    avg_stay_duration_seconds: Optional[float]

    hygiene_incidents_count: int
    waiting_queue_count: int
    service_bottleneck_detected: bool
    low_demand_detected: bool
    operational_diagnosis: str


def compute_salon_kpis(
    table_states: Dict[str, TableState],
    completed_sessions: List[TableSession],
    alerts: List[OperationalAlert],
    waiting_queue_count: int = 0,
) -> SalonKPISummary:
    """Calcula las métricas de rendimiento y diagnóstico operativo del restaurante."""
    total = len(table_states)
    free = sum(1 for s in table_states.values() if s == TableState.LIBRE)
    occupied = sum(1 for s in table_states.values() if s == TableState.OCUPADA)
    pending_clean = sum(1 for s in table_states.values() if s == TableState.POR_RECOGER)
    cleaning = sum(1 for s in table_states.values() if s == TableState.LIMPIANDO)
    temp_absent = sum(1 for s in table_states.values() if s == TableState.AUSENCIA_TEMPORAL)

    # Ocupación efectiva: activas + comensales en ausencia temporal (baño)
    effective_occupied = occupied + temp_absent
    occ_rate = (effective_occupied / total * 100.0) if total > 0 else 0.0

    # TPA (Tiempo de Primera Atención / First Service Latency)
    tpa_samples = [s.first_service_latency for s in completed_sessions if s.first_service_latency is not None]
    avg_tpa = (sum(tpa_samples) / len(tpa_samples)) if tpa_samples else None

    # TRM (Tiempo de Rotación de Mesa Sucia / Busser Latency)
    trm_samples = [s.turnover_latency for s in completed_sessions if s.turnover_latency is not None]
    avg_trm = (sum(trm_samples) / len(trm_samples)) if trm_samples else None

    # Duración promedio de estancia
    stay_samples = [s.duration_seconds for s in completed_sessions if not s.is_open and s.duration_seconds > 0]
    avg_stay = (sum(stay_samples) / len(stay_samples)) if stay_samples else None

    # Conteo de incidentes de higiene
    hygiene_incidents = sum(
        1 for a in alerts if a.alert_type == "HYGIENE_INCIDENT" or getattr(a, "severity", "") == "CRITICAL"
    )

    # Diagnóstico de cuello de botella vs demanda
    bottleneck = False
    low_demand = False
    diagnosis = "Operación normal y balanceada."

    if waiting_queue_count > 0 and (free > 0 or pending_clean > 0 or cleaning > 0):
        bottleneck = True
        diagnosis = (
            f"CUELLO DE BOTELLA OPERATIVO: Hay {waiting_queue_count} comensales esperando pero existen "
            f"{free} mesas libres y {pending_clean + cleaning} mesas en proceso de desbarase/limpieza. "
            "El personal de sala no está rotando las mesas a la velocidad requerida."
        )
    elif waiting_queue_count == 0 and (free / total >= 0.5 if total > 0 else False):
        low_demand = True
        diagnosis = (
            f"BAJA DEMANDA: Más del 50% de las mesas ({free}/{total}) están desocupadas sin cola de espera. "
            "Revisar dimensionamiento del local, campañas comerciales o estacionalidad."
        )

    return SalonKPISummary(
        total_tables=total,
        free_tables=free,
        occupied_tables=occupied,
        pending_clean_tables=pending_clean,
        cleaning_tables=cleaning,
        temporary_absence_tables=temp_absent,
        occupancy_rate_percent=round(occ_rate, 1),
        avg_first_service_latency_seconds=round(avg_tpa, 1) if avg_tpa is not None else None,
        avg_turnover_latency_seconds=round(avg_trm, 1) if avg_trm is not None else None,
        avg_stay_duration_seconds=round(avg_stay, 1) if avg_stay is not None else None,
        hygiene_incidents_count=hygiene_incidents,
        waiting_queue_count=waiting_queue_count,
        service_bottleneck_detected=bottleneck,
        low_demand_detected=low_demand,
        operational_diagnosis=diagnosis,
    )
