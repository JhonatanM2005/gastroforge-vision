# Guion de Sustentación Académica: Ultralytics YOLO para Control de Mesas en Restaurante

> **Asignatura:** Programación Avanzada  
> **Tiempo Estimado:** 25 a 35 minutos (Rango permitido: 20 a 40 min)  
> **Tema:** Visión por Computador con Ultralytics YOLO & Fusión Transaccional POS para Telemetría de Salón  
> **Proyecto Relacionado:** Ecosistema GastroForge ([GastroForge-Academic](file:///c:/Users/Usuario/Documents/Programación%20Avanzada/GastroForge-Academic))  
> **Cumplimiento de Rúbrica:** [Instrucciones.md](file:///c:/Users/Usuario/Documents/Programación%20Avanzada/Expo%20Programación%20Avanzada/docs/Instrucciones.md)

---

## ⏱️ Estructura y Cronograma Minuto a Minuto

| Bloque | Minutos | Sección | Responsable / Enfoque |
| :--- | :--- | :--- | :--- |
| **I** | 00:00 - 05:00 | **Problema y Propósito:** Ineficiencias en sala y motivación GastroForge | Presentación de negocio y contexto real |
| **II** | 05:00 - 12:00 | **Fundamentos Técnicos:** Ultralytics YOLO, Redes Neuronales y Geometría | Conceptos esenciales sin teoría innecesaria |
| **III** | 12:00 - 20:00 | **Arquitectura de la Solución:** Fusión Sensorial-Transaccional y KPIs | Decisiones de diseño y Clean Architecture |
| **IV** | 20:00 - 30:00 | **Demostración en Vivo del MVP:** Inferencia, Telemetría y Alertas | Ejecución práctica y validación de casos |
| **V** | 30:00 - 35:00 | **Limitaciones, Aspectos Éticos/Legales y Cierre:** Ley 1581 y Trabajo Futuro | Preguntas y conclusiones |

---

## Bloque I: El Problema y Propósito del Proyecto (00:00 - 05:00)

### 1. El Problema Real en la Gestión Gastronómica
- En los restaurantes tradicionales, el personal de salón (anfitriones y camareros) depende de la inspección visual manual para saber:
  - Qué mesas están libres u ocupadas.
  - Cuánto tiempo lleva un cliente esperando antes de recibir su primer plato.
  - Qué mesas quedaron sucias tras la salida del cliente y cuánto tiempo llevan sin ser desbarasadas (recogidas).
- **Impacto negativo:**
  - Si hay mesas vacías pero con platos sucios mientras hay fila en la entrada, se genera un **cuello de botella de servicio** que arruina la rotación y la satisfacción del cliente.
  - El personal pierde tiempo valioso registrando manualmente el estado de las mesas en el sistema POS en lugar de atender a los comensales.

### 2. Propósito y Conexión con GastroForge
- En entregas anteriores desarrollamos **GastroForge-Academic**, una plataforma que analiza la complejidad algorítmica ($O(1)$, $O(n)$, $O(n^2)$, $O(\log n)$) de los pedidos y el tráfico en salón.
- **La innovación de este MVP:** Conectar los sensores físicos del restaurante (cámaras de visión artificial con YOLO) con la capa transaccional del software de restaurante, automatizando el registro de mesas y generando telemetría operativa en tiempo real (JSON/CSV).

---

## Bloque II: Fundamentos de Ultralytics YOLO y Visión Artificial (05:00 - 12:00)

### 1. ¿Qué es YOLO (You Only Look Once)?
- **Definición Clara:** A diferencia de los modelos tradicionales en dos etapas (como Faster R-CNN) que primero proponen regiones y luego clasifican, YOLO formula la detección de objetos como un **único problema de regresión**.
- **Cómo procesa la imagen:**
  1. Toma el fotograma completo una sola vez.
  2. Lo pasa por una red neuronal convolucional (Backbone CSPDarknet + C2f/C3k2 en versiones recientes).
  3. Divide la imagen en una cuadrícula y predice simultáneamente las coordenadas de las cajas delimitadoras (*Bounding Boxes*), la probabilidad de objeto (*Objectness Score*) y las probabilidades de clase.
- **Rendimiento:** Permite procesar video en tiempo real (25 a 60 FPS) incluso en CPU estándar, utilizando variantes ultraligeras (`yolo11n` o `yolo26n`).

### 2. Conceptos Clave para la Exposición
- **Bounding Box ($x_1, y_1, x_2, y_2$):** Coordenadas que delimitan la presencia de personas (`person`) y vajilla (`cup`, `bowl`, `bottle`, etc.).
- **IoU (Intersection over Union):** Métrica que evalúa la superposición entre dos cajas o entre una caja y un polígono.
- **Confianza (Confidence Threshold):** Filtro matemático (usamos $\ge 0.30$) para descartar detecciones dudosas sin perder personas parcialmente ocluidas.

### 3. Geometría Espacial: Algoritmo Ray-Casting
- Las mesas de un restaurante no son simples rectángulos; tienen perspectiva oblicua y formas trapezoidales.
- Implementamos el algoritmo **Ray Casting (Teorema de la curva de Jordan)** en $O(v)$ (donde $v$ es el número de vértices de la mesa) para evaluar si el centro o base de la persona está dentro del área poligonal de la mesa.

---

## Bloque III: Arquitectura y Fusión Sensorial-Transaccional (12:00 - 20:00)

### 1. Por qué la cámara no es suficiente por sí sola (El dilema del comensal solitario)
- **Caso Crítico:** *"Si voy solo a un restaurante, llevo 1.5 horas en la mesa, me levanto al baño y regreso a los 3 minutos... ¿el sistema cree que la mesa se liberó y que llegó un cliente nuevo?"*
- **Respuesta Arquitectónica: Fusión Sensorial-Transaccional.**
  - Si el sistema solo mirara la cámara, la ausencia de persona a los 30 segundos marcaría la mesa como `LIBRE` o `POR_RECOGER`, reiniciando el cronómetro a cero al volver.
  - **Nuestra Solución:** La máquina de estados `TableTracker` se comunica con el estado de pedidos de GastroForge POS (`has_active_order: true`). Si no se detecta persona físicamente pero el comensal tiene un pedido abierto o cuenta activa, la mesa entra en estado **`AUSENCIA_TEMPORAL`**. La sesión (`session_id`) y el cronómetro de permanencia se mantienen intactos.

### 2. Máquina de Estados con Debouncing Temporal
- Para evitar falsas alarmas cuando un mesero o transeúnte camina junto a la mesa:
  - **`t_ocupar` (15 segundos):** La presencia debe sostenerse para confirmar la mesa como `OCUPADA`.
  - **`t_gracia` (3 segundos):** Parpadeos o pérdidas cortas de detección no cancelan el cronómetro.
  - **`t_liberar` (30 segundos):** Se requiere ausencia sostenida antes de iniciar el cierre de servicio.
  - **`t_limpieza` (10 segundos):** Tiempo sin vajilla para confirmar que la mesa fue limpiada.

### 3. Matriz de KPIs Operativos
1. **TPA (Tiempo de Primera Atención / First Service Latency):** Lapso entre que el cliente se sienta y se le sirve el primer plato/bebida ($t_{primer\_plato} - t_{llegada}$).
2. **TRM (Tiempo de Rotación de Mesa Sucia / Busser Latency):** Tiempo que transcurre desde que el cliente sale hasta que el personal retira los platos ($t_{limpia} - t_{salida}$).
3. **Alerta Crítica de Incidencia de Higiene:** Disparada automáticamente si un nuevo cliente se sienta en una mesa con vajilla previa sin recoger (`HYGIENE_INCIDENT`).
4. **Diagnóstico Automático de Cuello de Botella vs Demanda:**
   - *Mesas vacías + Cola en espera* $\rightarrow$ Cuello de botella del personal de sala.
   - *Mesas vacías + Cero cola* $\rightarrow$ Problema comercial / sobredimensionamiento.

---

## Bloque IV: Demostración en Vivo del MVP (20:00 - 30:00)

### Paso 1: Ejecución del Pipeline con Video y Salida Anotada
Ejecutar en la terminal ante el jurado:
```bash
python -m src.table_monitor.cli analizar --fuente "docs/Archive/input/restaurant.mp4" --mesas "config/mesas_restaurant.json" --salida "output/demo_en_vivo" --cada 3 --t-ocupar 3 --t-liberar 5 --simular-bano "Mesa 1" --mostrar
```

### Paso 2: Puntos a Señalar en la Pantalla
1. **HUD Superior:** Mostrar cómo el panel contabiliza en tiempo real: Libres, Ocupadas, Por Recoger, Pausa (Baño) y el porcentaje de ocupación.
2. **Difuminado de Privacidad:** Señalar cómo los rostros/cuerpos de los comensales se difuminan automáticamente mediante desenfoque gaussiano, demostrando cumplimiento de la Ley 1581 de 2012.
3. **Cronómetro sobre las Mesas:** Mostrar el tiempo de ocupación en formato `HH:MM:SS` sobre cada polígono activo.
4. **Alerta de Primer Servicio:** Mostrar en la consola la alerta `FIRST_SERVICE_SERVED` cuando la vajilla es detectada sobre la mesa.

### Paso 3: Inspección de los Resultados Generados
Abrir los archivos generados en `output/demo_en_vivo/`:
- **`gastroforge_telemetry.json`:** Explicar cómo este JSON alimenta los dashboards de GastroForge con KPIs consolidados.
- **`gastroforge_sessions.csv`:** Mostrar la trazabilidad de cada sesión: hora de inicio, hora de fin, duración, TPA y TRM.
- **`gastroforge_alerts.json`:** Mostrar el registro histórico de eventos operativos y alertas de higiene.

### Paso 4: Ejecución de las Pruebas Unitarias
Demostrar la solidez y verificación del software ejecutando la suite de pruebas:
```bash
python -m pytest tests/ -v
```
*(Señalar al jurado que los 10 tests unitarios verifican matemáticamente la máquina de estados, el debounce, el caso del baño y los algoritmos geométricos).*

---

## Bloque V: Limitaciones, Aspectos Éticos y Conclusiones (30:00 - 35:00)

### 1. Limitaciones Técnicas Identificadas
- **Oclusiones Severas:** Si una persona se sienta detrás de una columna o de espaldas a una cámara ubicada en un ángulo muy bajo, el modelo COCO genérico puede presentar falsos negativos. *Solución recomendada: Cámaras cenitales (cenithal/top-down).*
- **Detección de Vajilla Fina:** El modelo COCO detecta objetos como tazas o platos grandes, pero puede ignorar servilletas o cubiertos pequeños. Para un entorno industrial se requeriría un *fine-tuning* con un dataset propio de vajilla sucia.

### 2. Aspectos Éticos y Protección de Datos (Ley 1581 de 2012)
- Monitorear espacios comerciales donde hay clientes exige responsabilidad.
- Nuestro sistema **NO realiza reconocimiento facial** ni almacena identidades biométricas.
- Aplica **difuminado irreversible en el pipeline de video** y conserva únicamente datos numéricos y cronómetros anónimos.

### 3. Conclusiones Principales
- Se construyó un MVP que trasciende un ejercicio de laboratorio: resuelve un problema operativo real mediante la unión de **visión artificial + arquitectura de software empresarial**.
- La integración de la telemetría de visión con el POS elimina tareas mecánicas y aporta visibilidad cuantitativa a la gerencia del restaurante.

---

## ❓ Preguntas Frecuentes del Jurado y Cómo Responderlas

### P1: ¿Por qué eligieron Ultralytics YOLO en lugar de modelos como Faster R-CNN o SSD?
> **Respuesta:**  
> "Faster R-CNN tiene una arquitectura de dos etapas (*Two-Stage Detector*) que primero genera propuestas de región y luego clasifica. Aunque es ligeramente más preciso en objetos diminutos, su latencia por fotograma supera los 100-200 ms en hardware no especializado, haciéndolo inviable para cámaras en vivo sin una GPU costosa.  
> Ultralytics YOLO es un detector de una sola etapa (*Single-Stage Detector*) que predice cajas y clases en un único pase hacia adelante (*feedforward*). Esto nos permite procesar a más de 30 FPS en CPU con un consumo de memoria inferior a 150 MB, ideal para el despliegue distribuido en múltiples sucursales de restaurantes."

### P2: ¿Cuál es la complejidad algorítmica de la coincidencia espacial entre personas y mesas?
> **Respuesta:**  
> "Para cada fotograma procesado, si tenemos $N$ detecciones de personas y $M$ polígonos de mesas con $V$ vértices cada uno, la complejidad del algoritmo Ray-Casting es de $O(N \times M \times V)$. Dado que en un salón típico $N \le 50$, $M \le 30$ y $V \approx 4$, el número total de operaciones por fotograma es del orden de $6.000$ comparaciones elementales, lo que en Python toma menos de 0.5 milisegundos, siendo despreciable frente a los 25 milisegundos de la red neuronal."

### P3: ¿Cómo manejan el problema de que un camarero se acerque a tomar el pedido sin considerarlo un cliente?
> **Respuesta:**  
> "Lo resolvemos mediante el concepto de debouncing temporal en la máquina de estados. La presencia debe sostenerse de manera ininterrumpida durante el parámetro `t_ocupar` (por ejemplo, 15 segundos). Un mesero que camina o se detiene brevemente a dejar la carta no cumple este umbral temporal y el sistema descarta la transición a OCUPADA gracias al tiempo de gracia (`t_gracia`)."

### P4: ¿Cómo se comunica este MVP con GastroForge-Academic?
> **Respuesta:**  
> "El módulo genera reportes desacoplados en formato JSON y CSV siguiendo la convención de nodos de sala (`table-1`, `table-2`, `terrace`) definida en los modelos de grafos de GastroForge. Este esquema permite que la API de GastroForge actualice automáticamente el grafo de ruteo de pedidos y los dashboards de métricas operativas sin acoplamiento directo entre el código de visión y la base de datos."
