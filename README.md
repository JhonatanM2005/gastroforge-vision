# GastroForge Vision - Sistema de Control y Telemetría de Mesas 🎥🍳📊

Sistema de visión por computadora para monitoreo inteligente de mesas en tiempo real con **Ultralytics YOLO**, tracking espacial adaptativo (*chair-aware*), máquina de estados operativa y telemetría analítica integrada con **GastroForge-Academic**.

---

## 🚀 Requisitos Previos

- **Python 3.10 o superior** (probado en Python 3.11.x)
- **pip** actualizado

---

## 📦 Instalación

1. Clonar el repositorio y entrar al directorio:
   ```bash
   git clone https://github.com/JhonatanM2005/gastroforge-vision.git
   cd gastroforge-vision
   ```

2. (Opcional pero recomendado) Crear y activar entorno virtual:
   ```bash
   python -m venv .venv
   # En Windows:
   .venv\Scripts\activate
   # En Linux / macOS:
   source .venv/bin/activate
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

4. Ejecutar pruebas unitarias para verificar la instalación:
   ```bash
   python -m pytest tests/ -v
   ```

---

## 🎬 1. Ejecución en Modo Local (Sin Conexión a la API)

En este modo, el sistema procesa el video, genera la ventana gráfica en vivo con difuminado por privacidad, y exporta todos los archivos analíticos localmente en la carpeta `output/analisis/` (`gastroforge_telemetry.json`, `gastroforge_sessions.csv`, `gastroforge_alerts.json`, `salon_telemetria.mp4`).

### Restaurante Clásico (Salón Principal):
```bash
python -m src.table_monitor.cli analizar --fuente input/restaurant.mp4 --mesas config/mesas_restaurant.json --mostrar --cada 2
```

### Cafetería / Bistro de Alta Densidad:
```bash
python -m src.table_monitor.cli analizar --fuente input/cafe_restaurant.mp4 --mesas config/mesas_cafe_restaurant.json --mostrar --cada 2
```

### Comida Rápida (Rotación y Vajilla por Recoger):
```bash
python -m src.table_monitor.cli analizar --fuente input/fast_food.mp4 --mesas config/mesas_fast_food.json --mostrar --cada 2
```

### Heladería (Mesas Redondas y Estancia Corta):
```bash
python -m src.table_monitor.cli analizar --fuente input/ice_cream_shop.mp4 --mesas config/mesas_ice_cream.json --mostrar --cada 2
```

### Resort / Terraza Amplia:
```bash
python -m src.table_monitor.cli analizar --fuente input/resort_restaurant.mp4 --mesas config/mesas_resort.json --mostrar --cada 2
```

---

## 🌐 2. Ejecución Integrada con la API de GastroForge-Academic

Para enviar la telemetría en tiempo real al backend y visualizarla en el dashboard frontend:

```bash
python -m src.table_monitor.cli analizar \
  --fuente input/restaurant.mp4 \
  --mesas config/mesas_restaurant.json \
  --api-url http://localhost:3000/api/v1/telemetry/ingest \
  --mostrar \
  --cada 2
```

### Banderas Especiales de Demostración:
- `--simular-bano "Mesa 1"`: Simula la integración POS para cliente solitario que va al baño (`AUSENCIA_TEMPORAL`).
- `--cola 5`: Simula fila de personas en espera en recepción para forzar alerta de `CUELLO_DE_BOTELLA`.
- `--sin-difuminar`: Desactiva el desenfoque gaussiano de rostros.

---

## 📐 3. Calibración de Nuevas Mesas

- **Modo interactivo manual**:
  ```bash
  python -m src.table_monitor.cli calibrar --imagen config/frames/restaurant_ref.jpg --salida config/mesas_mi_local.json
  ```
  *Controles:* Clic izquierdo marca vértices; tecla `c` cambia entre modo polígono y círculo; tecla `u` deshace; tecla `s` guarda.

- **Autocalibración por detección**:
  ```bash
  python -m src.table_monitor.cli autocalibrar --carpeta input --salida config
  ```
