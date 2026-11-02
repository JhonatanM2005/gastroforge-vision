from __future__ import annotations

from typing import Dict, List, Optional
from src.table_monitor.domain.models import (
    AlertSeverity,
    OperationalAlert,
    POSTableState,
    TableSession,
    TableState,
)


class TableTracker:
    """Rastreador de estado y telemetría para una mesa individual."""

    def __init__(
        self,
        table_id: str,
        t_ocupar: float = 15.0,
        t_liberar: float = 30.0,
        t_gracia: float = 3.0,
        t_limpieza: float = 10.0,
        t_alerta_primera_atencion: float = 300.0,
        t_alerta_rotacion_sucia: float = 180.0,
    ):
        self.table_id = table_id
        self.t_ocupar = t_ocupar
        self.t_liberar = t_liberar
        self.t_gracia = t_gracia
        self.t_limpieza = t_limpieza
        self.t_alerta_primera_atencion = t_alerta_primera_atencion
        self.t_alerta_rotacion_sucia = t_alerta_rotacion_sucia

        self.state: TableState = TableState.LIBRE
        self.candidate_since: Optional[float] = None
        self.last_seen_person: Optional[float] = None
        self.dishes_absent_since: Optional[float] = None
        self.vacated_at: Optional[float] = None
        self.cleaning_started_at: Optional[float] = None

        self.current_session: Optional[TableSession] = None
        self.last_session: Optional[TableSession] = None
        self.completed_sessions: List[TableSession] = []
        self.alerts: List[OperationalAlert] = []
        self._session_counter = 0

    def update(
        self,
        t: float,
        has_person: bool,
        has_dishes: bool = False,
        pos_state: Optional[POSTableState] = None,
    ) -> List[OperationalAlert]:
        """Actualiza el estado de la mesa en el tiempo t con la visión y el estado POS."""
        new_alerts: List[OperationalAlert] = []
        has_active_order = pos_state.has_active_order if pos_state else False

        # ==========================================
        # 1. ESTADO: LIBRE
        # ==========================================
        if self.state == TableState.LIBRE:
            if has_person:
                self.candidate_since = t
                self.last_seen_person = t
                self.state = TableState.EN_CONFIRMACION

        # ==========================================
        # 2. ESTADO: EN_CONFIRMACION (Debounce)
        # ==========================================
        elif self.state == TableState.EN_CONFIRMACION:
            if has_person:
                self.last_seen_person = t
                # Verificamos si superó el tiempo requerido para confirmar ocupación
                if self.candidate_since is not None and (t - self.candidate_since >= self.t_ocupar):
                    self.state = TableState.OCUPADA
                    self._session_counter += 1
                    sess_id = f"sess-{self.table_id}-{self._session_counter:03d}"
                    self.current_session = TableSession(
                        session_id=sess_id,
                        table_id=self.table_id,
                        start_time=self.candidate_since,
                        first_dish_time=t if has_dishes else None,
                        hygiene_incident=bool(has_dishes),
                    )
                    self.last_session = self.current_session
                    new_alerts.append(
                        OperationalAlert(
                            timestamp=t,
                            table_id=self.table_id,
                            alert_type="TABLE_OCCUPIED",
                            message=f"{self.table_id} confirmada OCUPADA. Sesión iniciada ({sess_id}).",
                            severity=AlertSeverity.INFO,
                        )
                    )
            else:
                # Pérdida de detección durante la confirmación (ej. mesero pasando)
                if self.last_seen_person is not None and (t - self.last_seen_person > self.t_gracia):
                    self.candidate_since = None
                    self.last_seen_person = None
                    self.state = TableState.POR_RECOGER if has_dishes else TableState.LIBRE

        # ==========================================
        # 3. ESTADO: OCUPADA
        # ==========================================
        elif self.state == TableState.OCUPADA:
            if self.current_session and self.current_session.first_dish_time is None and has_dishes:
                self.current_session.first_dish_time = t
                tpa = t - self.current_session.start_time
                new_alerts.append(
                    OperationalAlert(
                        timestamp=t,
                        table_id=self.table_id,
                        alert_type="FIRST_SERVICE_SERVED",
                        message=f"{self.table_id}: Primer servicio entregado en {tpa:.1f} s.",
                        severity=AlertSeverity.INFO,
                    )
                )

            if (
                self.current_session
                and self.current_session.first_dish_time is None
                and (t - self.current_session.start_time > self.t_alerta_primera_atencion)
            ):
                alert_key = f"slow_service_{self.current_session.session_id}"
                if not any(a.alert_type == alert_key for a in self.alerts):
                    alert = OperationalAlert(
                        timestamp=t,
                        table_id=self.table_id,
                        alert_type=alert_key,
                        message=f"Alerta en {self.table_id}: Mesa lleva {t - self.current_session.start_time:.0f}s ocupada sin platos servidos.",
                        severity=AlertSeverity.WARNING,
                    )
                    self.alerts.append(alert)
                    new_alerts.append(alert)

            if has_person:
                self.last_seen_person = t
            else:
                if self.last_seen_person is not None and (t - self.last_seen_person >= self.t_liberar):
                    if has_active_order:
                        self.state = TableState.AUSENCIA_TEMPORAL
                        new_alerts.append(
                            OperationalAlert(
                                timestamp=t,
                                table_id=self.table_id,
                                alert_type="TEMPORARY_ABSENCE",
                                message=f"{self.table_id}: Comensal ausente temporalmente (baño/salida corta), pedido activo en POS.",
                                severity=AlertSeverity.INFO,
                            )
                        )
                    else:
                        self._cerrar_sesion_ocupada(t, has_dishes, new_alerts)

        # ==========================================
        # 4. ESTADO: AUSENCIA_TEMPORAL (Baño/Pausa)
        # ==========================================
        elif self.state == TableState.AUSENCIA_TEMPORAL:
            if has_person:
                self.state = TableState.OCUPADA
                self.last_seen_person = t
                new_alerts.append(
                    OperationalAlert(
                        timestamp=t,
                        table_id=self.table_id,
                        alert_type="CLIENT_RETURNED",
                        message=f"{self.table_id}: Comensal ha regresado a la mesa. Sesión reanudada con éxito.",
                        severity=AlertSeverity.INFO,
                    )
                )
            else:
                if not has_active_order:
                    self._cerrar_sesion_ocupada(t, has_dishes, new_alerts)

        # ==========================================
        # 5. ESTADO: POR_RECOGER (Mesa Sucia / Pendiente Limpieza)
        # ==========================================
        elif self.state == TableState.POR_RECOGER:
            if has_person:
                # El personal se aproxima a higienizar la mesa
                self.state = TableState.LIMPIANDO
                self.cleaning_started_at = t
                self.last_seen_person = t
                new_alerts.append(
                    OperationalAlert(
                        timestamp=t,
                        table_id=self.table_id,
                        alert_type="TABLE_CLEANING",
                        message=f"{self.table_id}: Personal higienizando / desbarasando la mesa.",
                        severity=AlertSeverity.INFO,
                    )
                )
            else:
                if not has_dishes:
                    if self.dishes_absent_since is None:
                        self.dishes_absent_since = t
                    elif (t - self.dishes_absent_since) >= self.t_limpieza:
                        self._registrar_limpieza_completada(t, new_alerts)
                else:
                    self.dishes_absent_since = None
                    if self.vacated_at and (t - self.vacated_at > self.t_alerta_rotacion_sucia):
                        alert_key = f"slow_busser_{self.table_id}_{int(self.vacated_at)}"
                        if not any(a.alert_type == alert_key for a in self.alerts):
                            alert = OperationalAlert(
                                timestamp=t,
                                table_id=self.table_id,
                                alert_type=alert_key,
                                message=f"Atención en {self.table_id}: Mesa lleva {t - self.vacated_at:.0f}s sucia sin ser recogida.",
                                severity=AlertSeverity.WARNING,
                            )
                            self.alerts.append(alert)
                            new_alerts.append(alert)

        # ==========================================
        # 6. ESTADO: LIMPIANDO (Mesero Higienizando la Mesa)
        # ==========================================
        elif self.state == TableState.LIMPIANDO:
            if has_person:
                self.last_seen_person = t
                # Detección de falso positivo: sólo si una persona permanece sentada un tiempo excesivo
                # con vajilla aún presente sin limpiar, se considera comensal sentado en mesa sucia
                if has_dishes and self.cleaning_started_at and (t - self.cleaning_started_at >= self.t_ocupar * 2.5):
                    alert_key = f"hygiene_real_{self.table_id}_{int(self.cleaning_started_at)}"
                    if not any(a.alert_type == alert_key for a in self.alerts):
                        alert = OperationalAlert(
                            timestamp=t,
                            table_id=self.table_id,
                            alert_type=alert_key,
                            message=f"CRÍTICO en {self.table_id}: Cliente esperando en mesa con vajilla previa sin recoger.",
                            severity=AlertSeverity.CRITICAL,
                        )
                        self.alerts.append(alert)
                        new_alerts.append(alert)
                        self.state = TableState.OCUPADA
            else:
                # El personal terminó de limpiar y se retiró de la mesa
                self._registrar_limpieza_completada(t, new_alerts)

        return new_alerts

    def _registrar_limpieza_completada(self, t: float, new_alerts: List[OperationalAlert]):
        """Marca la mesa como libre y limpia tras haber sido higienizada o desbarasada."""
        self.state = TableState.LIBRE
        self.vacated_at = None
        self.cleaning_started_at = None
        self.dishes_absent_since = None
        self.candidate_since = None
        self.last_seen_person = None

        trm = None
        if self.completed_sessions and self.completed_sessions[-1].cleared_time is None:
            self.completed_sessions[-1].cleared_time = t
            trm = self.completed_sessions[-1].turnover_latency

        new_alerts.append(
            OperationalAlert(
                timestamp=t,
                table_id=self.table_id,
                alert_type="TABLE_CLEARED",
                message=f"{self.table_id} higienizada y lista para nuevo servicio (TRM: {trm:.1f}s)." if trm else f"{self.table_id} higienizada y lista.",
                severity=AlertSeverity.INFO,
            )
        )

    def _cerrar_sesion_ocupada(self, t: float, has_dishes: bool, new_alerts: List[OperationalAlert]):
        """Finaliza la sesión actual y transiciona a POR_RECOGER o LIBRE."""
        fin = self.last_seen_person if self.last_seen_person is not None else t
        if self.current_session:
            self.current_session.end_time = fin
            self.current_session.is_open = False
            if not has_dishes:
                self.current_session.cleared_time = t
            self.completed_sessions.append(self.current_session)
            self.last_session = self.current_session

        self.vacated_at = t
        if has_dishes:
            self.state = TableState.POR_RECOGER
            self.dishes_absent_since = None
            new_alerts.append(
                OperationalAlert(
                    timestamp=t,
                    table_id=self.table_id,
                    alert_type="TABLE_DIRTY",
                    message=f"{self.table_id}: Clientes se retiraron. Mesa marcada POR RECOGER.",
                    severity=AlertSeverity.INFO,
                )
            )
        else:
            self.state = TableState.LIBRE
            new_alerts.append(
                OperationalAlert(
                    timestamp=t,
                    table_id=self.table_id,
                    alert_type="TABLE_FREED",
                    message=f"{self.table_id}: Mesa liberada y despejada.",
                    severity=AlertSeverity.INFO,
                )
            )
        self.current_session = None
        self.candidate_since = None
        self.last_seen_person = None

    def get_current_occupied_duration(self, t: float) -> float:
        """Retorna la duración de ocupación activa o de la última sesión registrada."""
        if self.current_session and self.current_session.is_open:
            return max(0.0, t - self.current_session.start_time)
        elif self.last_session:
            return self.last_session.duration_seconds
        elif self.completed_sessions:
            return self.completed_sessions[-1].duration_seconds
        return 0.0

    def get_active_or_last_session(self) -> Optional[TableSession]:
        """Retorna la sesión en curso o la más reciente registrada."""
        return self.current_session or self.last_session or (self.completed_sessions[-1] if self.completed_sessions else None)


class RestaurantSalonStateMachine:
    """Orquestador de la máquina de estados de todas las mesas del restaurante."""

    def __init__(self, table_ids: List[str], **tracker_kwargs):
        self.trackers: Dict[str, TableTracker] = {
            t_id: TableTracker(t_id, **tracker_kwargs) for t_id in table_ids
        }
        self.all_alerts: List[OperationalAlert] = []

    def update(
        self,
        t: float,
        people_by_table: Dict[str, bool],
        dishes_by_table: Optional[Dict[str, bool]] = None,
        pos_states: Optional[Dict[str, POSTableState]] = None,
    ) -> List[OperationalAlert]:
        """Procesa un ciclo de tiempo para todo el salón."""
        dishes = dishes_by_table or {}
        pos = pos_states or {}
        tick_alerts: List[OperationalAlert] = []

        for t_id, tracker in self.trackers.items():
            has_p = people_by_table.get(t_id, False)
            has_d = dishes.get(t_id, False)
            p_state = pos.get(t_id)
            alerts = tracker.update(t, has_p, has_d, p_state)
            tick_alerts.extend(alerts)

        self.all_alerts.extend(tick_alerts)
        return tick_alerts

    def get_state(self, table_id: str) -> TableState:
        return self.trackers[table_id].state

    def get_all_completed_sessions(self) -> List[TableSession]:
        sessions = []
        for tr in self.trackers.values():
            sessions.extend(tr.completed_sessions)
        return sorted(sessions, key=lambda s: s.start_time)

    def force_close_all(self, t: float):
        """Cierra todas las sesiones abiertas al finalizar la jornada o video."""
        for tr in self.trackers.values():
            if tr.current_session and tr.current_session.is_open:
                tr.current_session.end_time = t
                tr.current_session.is_open = False
                tr.completed_sessions.append(tr.current_session)
                tr.last_session = tr.current_session
                tr.current_session = None
