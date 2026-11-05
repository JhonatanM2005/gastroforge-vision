# Esquema de Diapositivas: Control de Mesas con Ultralytics YOLO & GastroForge

> **Guía para la elaboración de la presentación (PowerPoint / Canva / Google Slides)**  
> Cada diapositiva incluye el contenido visual sugerido y las notas del orador para una exposición fluida de 25 a 35 minutos.

---

### Diapositiva 1: Portada
- **Título:** Control Automatizado de Mesas y Telemetría de Salón en Restaurantes con Ultralytics YOLO
- **Subtítulo:** Fusión de Visión por Computador y Sistemas Transaccionales en el Ecosistema GastroForge
- **Asignatura:** Programación Avanzada
- **Expositores:** [Nombres de los integrantes]
- **Notas del orador:**
  > "Buenas tardes profesor y compañeros. Hoy les presentaremos nuestro Producto Mínimo Viable de visión artificial aplicada a la industria restaurantera, integrando redes neuronales convolucionales de última generación con la lógica de negocio de nuestro proyecto GastroForge."

---

### Diapositiva 2: El Problema en Sala
- **Puntos clave:**
  - El cuello de botella invisible: mesas sucias o vacías mientras hay clientes esperando en la entrada.
  - Carga operativa en meseros y anfitriones al registrar manualmente el estado en el POS.
  - Falta de métricas cuantitativas sobre tiempos de atención y rotación.
- **Gráfico sugerido:** Comparativa visual: *Salón con gestión manual a ciegas* vs *Salón con telemetría visual inteligente*.
- **Notas del orador:**
  > "En el sector gastronómico, los restaurantes pierden ingresos por rotación ineficiente. Si un cliente se va y la mesa pasa 15 minutos con platos sucios, esa mesa no produce. El problema es que los gerentes no tienen ojos en todas partes ni métricas objetivas de cuánto tarda el personal en limpiar o servir."

---

### Diapositiva 3: Propósito y Enfoque del MVP
- **Puntos clave:**
  - Monitoreo continuo mediante cámaras de seguridad fijas convencionales.
  - Clasificación en tiempo real del estado de cada mesa (`Libre`, `Ocupada`, `Por Recoger`, `Pausa`).
  - Automatización del registro en el sistema POS del restaurante.
  - Generación de reportes estructurados compatibles con la API de GastroForge.
- **Notas del orador:**
  > "Nuestro objetivo no fue hacer un script de detección aislado, sino un sistema integral que traduzca píxeles en decisiones de negocio: optimizar la rotación de mesas y alertar sobre incidencias de servicio en tiempo real."

---

### Diapositiva 4: Fundamentos de Ultralytics YOLO
- **Puntos clave:**
  - ¿Qué significa YOLO? *You Only Look Once* (Detección en una sola etapa).
  - Regresión directa: Bounding Box $(x_1, y_1, x_2, y_2) + \text{Confianza} + \text{Clases}$.
  - Ventajas frente a modelos en dos etapas (Faster R-CNN): Mayor velocidad, inferencia en tiempo real en CPU estándar (>25 FPS).
  - Clases COCO utilizadas: `person` para comensales y conjunto de vajilla (`cup`, `bowl`, `bottle`, `fork`).
- **Diagrama:** Diagrama de bloques del flujo de inferencia YOLO.

---

### Diapositiva 5: Geometría Espacial, Halo Chair-Aware y Calibración
- **Puntos clave:**
  - Las mesas se definen como polígonos convexos arbitrarios (`mesas_*.json`).
  - **Prueba Ray-Casting y PointPolygonTest:** Evaluación geométrica euclidiana en tiempo $\mathcal{O}(N \times M \times V)$.
  - **Margen Elíptico Chair-Aware (22%):** Detección robusta de comensales sentados junto a mesas calibradas solo en el tablero.
  - **Filtro de Relación de Aspecto de Transeúntes:** Filtra personas de pie o meseros caminando ($h/w > 1.90$) para evitar falsos positivos en pasillos.
- **Gráfico sugerido:** Captura de un fotograma mostrando los polígonos verdes, amarillos y rojos sobre las mesas con el difuminado facial.

---

### Diapositiva 6: Fusión Sensorial-Transaccional y Estado de Limpieza
- **El desafío del comensal solitario:**
  - Si un comensal solo va al baño tras 90 min, la cámara deja de verlo.
  - **Fusión Sensorial:** Visión por computador + Estado transaccional POS (`active_order: true`).
  - La mesa transiciona a `AUSENCIA_TEMPORAL` (preservando sesión y cronómetro acumulado).
- **El dilema de la mesa sucia:**
  - Al levantarse los comensales dejando platos, pasa a `POR_RECOGER`.
  - Cuando un mesero se acerca a desbarasar la vajilla, el sistema entra en estado `LIMPIANDO` y luego a `LIBRE`, evitando disparar falsas alertas de incidentes de higiene.
- **Diagrama:** Máquina de estados completa: `LIBRE` $\leftrightarrow$ `EN_CONFIRMACION` $\rightarrow$ `OCUPADA` $\leftrightarrow$ `AUSENCIA_TEMPORAL` $\rightarrow$ `POR_RECOGER` $\rightarrow$ `LIMPIANDO` $\rightarrow$ `LIBRE`.

---

### Diapositiva 7: Lógica Temporal, Debouncing y Algoritmos
- **Lógica Temporal Antirrebote:**
  - `t_ocupar` (adaptativo 2.5s - 15s): Confirmación por presencia sostenida.
  - `t_gracia` (3s): Tolerancia a parpadeos u oclusiones momentáneas.
  - `t_liberar` (adaptativo 4.2s - 30s): Confirmación de abandono de mesa.
  - `t_limpieza` (10s): Confirmación de mesa despejada de vajilla.
- **Gráfico:** Diagrama de transiciones y cronómetro de permanencia en tiempo real.

---

### Diapositiva 8: KPIs Operativos y Diagnóstico de Negocio
- **Indicadores Clave generados:**
  - **TPA (Tiempo de Primera Atención):** Lapso desde que el cliente se sienta hasta que llega el primer plato.
  - **TRM (Tiempo de Rotación de Mesa):** Lapso desde que el comensal sale hasta que la mesa queda limpia.
  - **Alerta Crítica de Incidencia de Higiene:** Cliente sentándose en mesa con vajilla previa sin recoger.
  - **Diagnóstico Automático:** Detección de cuellos de botella en sala (`mesas libres + cola en espera`) vs. baja demanda.

---

### Diapositiva 9: Demostración Práctica en Vivo y Visualización
- **Estructura de la Demostración:**
  1. Ejecución del comando CLI sobre video con ventana gráfica OpenCV (`--mostrar`).
  2. Demostración del difuminado de privacidad en tiempo real (Ley 1581 de 2012).
  3. Transmisión continua a la API REST de GastroForge mediante `--api-url`.
  4. Visualización de los 5 escenarios grabados (`restaurant.mp4`, `cafe_restaurant.mp4`, `fast_food.mp4`, `ice_cream_shop.mp4`, `resort_restaurant.mp4`).
- **Notas del orador:**
  > "Procederemos a ejecutar la solución en vivo. Observen cómo el sistema detecta a las personas difuminando sus rostros para proteger su privacidad, calcula el tiempo de estancia y envía la telemetría en tiempo real por HTTP POST a la API."

---

### Diapositiva 10: Integración Full-Stack con GastroForge-Academic
- **Puntos clave:**
  - **Endpoint REST Ingest (`POST /api/v1/telemetry/ingest`):** Recepción y validación estricta con DTOs en NestJS.
  - **Dashboard en Tiempo Real (React + Vite + Tailwind):** Panel web con auto-sondeo cada 3s, tarjetas de mesas y alertas.
  - **Ruta de Despacho Dijkstra ($\mathcal{O}((V+E)\log V)$):** Cálculo del camino mínimo en segundos desde cocina hasta la mesa (`kitchen -> passage -> table-1`).
  - **Cola de Prioridad MinHeap ($\mathcal{O}(\log n)$):** Jerarquización de atención urgente (Incidentes de higiene > Mesas por recoger > Demora de primer plato TPA).
  - **Verificación Rigurosa:** 14 pruebas en Python (`pytest`), 106 pruebas en NestJS (`npm test`) y 18 pruebas en Frontend (`vitest`).
- **Notas del orador:**
  > "Este MVP conecta el mundo físico con los algoritmos del curso: la visión alimenta el estado del salón, Dijkstra calcula el trayecto óptimo del mesero desde cocina y el MinHeap jerarquiza las mesas más urgentes sin intervención manual."

---

### Diapositiva 11: Limitaciones y Aspectos Éticos (Ley 1581 de 2012)
- **Puntos clave:**
  - **Protección de Datos:** Cumplimiento estricto de la Ley 1581 de 2012. Sin almacenamiento de rostros ni reconocimiento biométrico; difuminado gaussiano activo en el video.
  - **Limitaciones Técnicas:** Oclusiones por columnas o ángulos bajos; resolución necesaria para vajilla pequeña.
  - **Trabajo Futuro:** Fine-tuning con dataset específico de vajilla y despliegue en microcomputadores en el borde (Edge Computing con Raspberry Pi / Jetson Nano).

---

### Diapositiva 12: Conclusiones y Preguntas
- **Síntesis del Aprendizaje:**
  - La visión por computador es una herramienta de telemetría de alto impacto cuando se integra con arquitecturas limpias y dominios de negocio.
  - No basta con correr un modelo: la lógica de estados temporal y la fusión con el POS son lo que transforman detecciones crudas en un producto útil.
- **Espacio para preguntas del docente y compañeros.**
