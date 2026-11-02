from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class TableState(str, Enum):
    """Estados del ciclo de vida de una mesa en el salón."""
    LIBRE = "libre"
    EN_CONFIRMACION = "en_confirmacion"
    OCUPADA = "ocupada"
    AUSENCIA_TEMPORAL = "ausencia_temporal"  # Comensal en el baño con pedido activo en POS
    POR_RECOGER = "por_recoger"  # Cliente salió, vajilla pendiente de limpieza
    LIMPIANDO = "limpiando"  # Personal higienizando o desbarasando la mesa


class AlertSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class POSTableState:
    """Estado transaccional de la mesa reportado por GastroForge POS."""
    table_id: str
    has_active_order: bool = False
    order_id: Optional[str] = None
    order_status: Optional[str] = None  # 'pending' | 'preparing' | 'delivered'
    diner_count: int = 0


@dataclass
class DetectionBox:
    """Caja delimitadora detectada por el modelo de visión."""
    x1: float
    y1: float
    x2: float
    y2: float
    class_name: str
    confidence: float

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    @property
    def base(self) -> Tuple[float, float]:
        # Punto inferior central, óptimo para cámaras con perspectiva inclinada
        return ((self.x1 + self.x2) / 2.0, self.y2)


@dataclass
class TableConfig:
    """Configuración espacial de una mesa (zona poligonal)."""
    table_id: str
    polygon: List[Tuple[float, float]]


@dataclass
class OperationalAlert:
    """Alerta de negocio o calidad en el servicio."""
    timestamp: float
    table_id: str
    alert_type: str
    message: str
    severity: AlertSeverity = AlertSeverity.INFO


@dataclass
class TableSession:
    """Registro histórico de atención de una mesa."""
    session_id: str
    table_id: str
    start_time: float
    end_time: Optional[float] = None
    first_dish_time: Optional[float] = None
    cleared_time: Optional[float] = None
    hygiene_incident: bool = False
    is_open: bool = True

    @property
    def duration_seconds(self) -> float:
        if self.end_time is not None:
            return max(0.0, self.end_time - self.start_time)
        return 0.0

    @property
    def first_service_latency(self) -> Optional[float]:
        """TPA: Tiempo desde que el cliente se sienta hasta el primer plato."""
        if self.first_dish_time is not None and self.first_dish_time >= self.start_time:
            return self.first_dish_time - self.start_time
        return None

    @property
    def turnover_latency(self) -> Optional[float]:
        """TRM: Tiempo desde que el cliente sale hasta que la mesa queda limpia."""
        if self.end_time is not None and self.cleared_time is not None:
            if self.cleared_time >= self.end_time:
                return self.cleared_time - self.end_time
        return None
