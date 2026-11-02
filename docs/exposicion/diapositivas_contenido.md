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

### Diapositiva 5: Geometría Espacial y Calibración de Mesas
- **Puntos clave:**
  - Las mesas se definen como polígonos convexos arbitrarios (`mesas.json`).
  - Perspectiva oblicua: el criterio de centroide y punto base inferior.
  - Algoritmo de Ray-Casting (Teorema de la curva de Jordan): evaluación geométrica pura en tiempo $O(N \times M \times V)$.
- **Gráfico sugerido:** Captura de un fotograma mostrando los polígonos verdes, amarillos y rojos sobre las mesas.

---

### Diapositiva 6: El Desafío del Comensal Solitario (Fusión Sensorial-Transaccional)
- **El problema de un sensor aislado:**
  - Si un comensal solo va al baño a los 90 minutos de comida, la cámara deja de verlo. Un sistema ingenuo liberaría la mesa o crearía una sesión nueva al volver.
- **Nuestra solución:**
  - **Fusión Sensorial:** Visión por computador + Estado de pedidos en GastroForge POS.
  - Si no hay persona visual pero la mesa tiene pedido abierto (`active_order: true`), entra en `AUSENCIA_TEMPORAL`.
  - Al regresar, se reanuda la misma sesión sin perder el historial.
- **Diagrama:** Máquina de estados mostrando la transición a `AUSENCIA_TEMPORAL` y retorno.

---

### Diapositiva 7: Lógica Temporal y Debouncing
- **Puntos clave:**
  - ¿Cómo evitar falsos positivos con meseros o transeúntes?
  - `t_ocupar` (15s): Confirmación por presencia sostenida.
  - `t_gracia` (3s): Tolerancia a parpadeos u oclusiones momentáneas de la cámara.
  - `t_liberar` (30s): Confirmación de abandono de mesa.
  - `t_limpieza` (10s): Confirmación de mesa despejada de vajilla.
- **Gráfico:** Línea de tiempo ilustrando el debouncing.

---

### Diapositiva 8: KPIs Operativos y Diagnóstico de Negocio
- **Indicadores Clave generados:**
  - **TPA (Tiempo de Primera Atención):** Lapso desde que el cliente se sienta hasta que llega el primer plato.
  - **TRM (Tiempo de Rotación de Mesa Sucia):** Lapso desde que el comensal sale hasta que la mesa queda limpia.
  - **Alerta Crítica de Incidencia de Higiene:** Cliente sentándose en mesa con vajilla previa sin recoger.
  - **Diagnóstico Automático:** Detección de cuellos de botella en sala (mesas sucias con cola de espera) vs. baja demanda.

---

### Diapositiva 9: Demostración Práctica en Vivo
- **Estructura de la Demo:**
  1. Ejecución del comando CLI sobre video en tiempo real.
  2. Visualización del HUD interactivo y difuminado de privacidad.
  3. Comprobación del cronómetro de ocupación por mesa.
  4. Generación y apertura de los archivos de salida: `gastroforge_telemetry.json` y `gastroforge_sessions.csv`.
- **Notas del orador:**
  > "Procederemos a ejecutar la solución en vivo sobre el salón de pruebas. Observen cómo el sistema detecta a las personas difuminando sus rostros para proteger su privacidad, calcula el tiempo de estancia y genera las alertas operativas."

---

### Diapositiva 10: Integración con GastroForge-Academic
- **Puntos clave:**
  - Exportación en formato compatible con los nodos del plano de sala (`table-1`, `table-2`, `terrace`).
  - Alimentación del motor de asignación de turnos y simulación de complejidad computacional.
  - Verificación del software mediante 10 pruebas unitarias automatizadas (`pytest`).
- **Notas del orador:**
  > "Este MVP cierra el círculo entre el mundo físico y el digital: la cámara informa el estado del salón y GastroForge actualiza sus algoritmos de optimización de rutas y pedidos sin intervención manual."

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
