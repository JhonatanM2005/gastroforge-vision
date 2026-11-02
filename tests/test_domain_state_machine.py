from __future__ import annotations

import pytest
from src.table_monitor.domain.models import (
    AlertSeverity,
    POSTableState,
    TableState,
)
from src.table_monitor.domain.state_machine import TableTracker


def test_person_sitting_confirms_occupied_after_t_ocupar():
    """Verifica que una persona sentada durante t_ocupar confirma el estado OCUPADA e inicia sesión."""
    tracker = TableTracker("Mesa 1", t_ocupar=15.0, t_liberar=30.0, t_gracia=3.0)

    # t = 0: Comensal llega a la mesa
    alerts = tracker.update(t=0.0, has_person=True, has_dishes=False)
    assert tracker.state == TableState.EN_CONFIRMACION
    assert tracker.current_session is None

    # t = 10: Sigue sentado (menos de t_ocupar)
    alerts = tracker.update(t=10.0, has_person=True, has_dishes=False)
    assert tracker.state == TableState.EN_CONFIRMACION
    assert tracker.current_session is None

    # t = 15: Cumple t_ocupar -> Se confirma OCUPADA
    alerts = tracker.update(t=15.0, has_person=True, has_dishes=False)
    assert tracker.state == TableState.OCUPADA
    assert tracker.current_session is not None
    assert tracker.current_session.session_id == "sess-Mesa 1-001"
    assert tracker.current_session.start_time == 0.0
    assert any(a.alert_type == "TABLE_OCCUPIED" for a in alerts)


def test_waiter_passing_by_does_not_trigger_occupancy():
    """Verifica que un mesero o transeúnte que pasa menos de t_ocupar no dispara falsa ocupación (debouncing)."""
    tracker = TableTracker("Mesa 1", t_ocupar=15.0, t_liberar=30.0, t_gracia=3.0)

    # t = 0: Persona detectada
    tracker.update(t=0.0, has_person=True)
    assert tracker.state == TableState.EN_CONFIRMACION

    # t = 4: Persona detectada brevemente
    tracker.update(t=4.0, has_person=True)

    # t = 8: Persona desaparece y se supera tiempo de gracia (t=4 + gracia=3 = 7s)
    tracker.update(t=8.0, has_person=False)
    assert tracker.state == TableState.LIBRE
    assert tracker.current_session is None
    assert len(tracker.completed_sessions) == 0


def test_solitary_diner_goes_to_bathroom_with_active_pos_order():
    """Caso Clave: Comensal solitario va al baño; el POS evita liberar la mesa y preserva la sesión."""
    tracker = TableTracker("Mesa 1", t_ocupar=10.0, t_liberar=20.0, t_gracia=3.0)

    # 1. Comensal se sienta e inicia sesión
    tracker.update(t=0.0, has_person=True)
    tracker.update(t=10.0, has_person=True)
    assert tracker.state == TableState.OCUPADA
    session_id = tracker.current_session.session_id

    # 2. Comensal tiene un pedido activo en GastroForge POS
    pos_state = POSTableState(
        table_id="Mesa 1",
        has_active_order=True,
        order_id="GF-ORD-101",
        order_status="delivered",
    )

    # 3. Comensal se levanta al baño (last_seen_person era 10.0)
    # A t=35 (35 - 10 = 25 >= t_liberar), se detecta ausencia prolongada
    alerts = tracker.update(t=35.0, has_person=False, pos_state=pos_state)

    # Con la fusión sensorial-POS, la mesa NO se libera ni se borra la sesión
    assert tracker.state == TableState.AUSENCIA_TEMPORAL
    assert tracker.current_session is not None
    assert tracker.current_session.session_id == session_id
    assert any(a.alert_type == "TEMPORARY_ABSENCE" for a in alerts)

    # 4. Comensal regresa del baño en t=120
    return_alerts = tracker.update(t=120.0, has_person=True, pos_state=pos_state)
    assert tracker.state == TableState.OCUPADA
    assert tracker.current_session.session_id == session_id
    assert any(a.alert_type == "CLIENT_RETURNED" for a in return_alerts)

    # El tiempo total ocupado debe ser continuo desde t=0
    assert tracker.get_current_occupied_duration(120.0) == 120.0


def test_waiter_cleaning_dirty_table_does_not_trigger_hygiene_incident():
    """Verifica que un mesero limpiando una mesa sucia (POR_RECOGER) pasa a LIMPIANDO y luego a LIBRE sin falsa alarma."""
    tracker = TableTracker("Mesa 1", t_ocupar=10.0, t_liberar=20.0)
    tracker.state = TableState.POR_RECOGER
    tracker.last_seen_dish = 50.0

    # Mesero llega a limpiar en t=55.0
    alerts = tracker.update(t=55.0, has_person=True, has_dishes=True)
    assert tracker.state == TableState.LIMPIANDO
    # No debe acusar al mesero de comensal en mesa sucia
    assert not any(a.alert_type == "HYGIENE_INCIDENT" for a in alerts)

    # Mesero retira la vajilla y se va en t=62.0 (t - 55 = 7s < 25s)
    alerts_cleaned = tracker.update(t=62.0, has_person=False, has_dishes=False)
    assert tracker.state == TableState.LIBRE
    assert any(a.alert_type == "TABLE_CLEARED" for a in alerts_cleaned)


def test_hygiene_incident_diner_seats_at_dirty_table():
    """Verifica que si un comensal permanece sentado un tiempo prolongado en mesa sucia sin limpiar, sí dispara alerta."""
    tracker = TableTracker("Mesa 1", t_ocupar=10.0, t_liberar=20.0)

    # Mesa que quedó con vajilla previa (POR_RECOGER)
    tracker.state = TableState.POR_RECOGER
    tracker.last_seen_dish = 50.0

    # Persona llega a la mesa en t=55.0
    tracker.update(t=55.0, has_person=True, has_dishes=True)
    assert tracker.state == TableState.LIMPIANDO

    # Persona permanece sentada por tiempo excesivo (t=85.0, diferencia 30s > 2.5 * t_ocupar) con vajilla aún ahí
    alerts = tracker.update(t=85.0, has_person=True, has_dishes=True)
    assert tracker.state == TableState.OCUPADA
    assert any(a.severity == AlertSeverity.CRITICAL for a in alerts)


def test_first_service_latency_and_turnover_latency():
    """Verifica el cálculo de TPA (primer plato servido) y TRM (limpieza de mesa tras salida)."""
    tracker = TableTracker("Mesa 1", t_ocupar=10.0, t_liberar=20.0, t_limpieza=5.0)

    # t = 0 a 10: Ocupación confirmada
    tracker.update(t=0.0, has_person=True, has_dishes=False)
    tracker.update(t=10.0, has_person=True, has_dishes=False)

    # t = 45: Se sirve el primer plato (TPA = 45 - 0 = 45s)
    alerts = tracker.update(t=45.0, has_person=True, has_dishes=True)
    assert tracker.current_session.first_dish_time == 45.0
    assert tracker.current_session.first_service_latency == 45.0
    assert any(a.alert_type == "FIRST_SERVICE_SERVED" for a in alerts)

    # t = 100: Cliente se va dejando platos
    tracker.update(t=100.0, has_person=True, has_dishes=True)
    # t = 125: Se confirma salida (ausencia >= 20s) -> pasa a POR_RECOGER
    tracker.update(t=125.0, has_person=False, has_dishes=True)
    assert tracker.state == TableState.POR_RECOGER
    assert len(tracker.completed_sessions) == 1
    session = tracker.completed_sessions[0]
    assert session.end_time == 100.0

    # t = 160: Personal recoge la vajilla
    tracker.update(t=160.0, has_person=False, has_dishes=False)
    # t = 165: Cumple t_limpieza (5s) -> Mesa queda LIBRE y se registra TRM
    tracker.update(t=165.0, has_person=False, has_dishes=False)
    assert tracker.state == TableState.LIBRE
    assert session.cleared_time == 165.0
    # TRM = cleared_time (165) - end_time (100) = 65s
    assert session.turnover_latency == 65.0
