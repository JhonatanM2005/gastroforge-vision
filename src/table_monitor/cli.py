from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

# Asegurar codificación utf-8 en terminales Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
from src.table_monitor.analytics.gastroforge_exporter import (
    build_gastroforge_telemetry_dict,
    export_alerts_json,
    export_gastroforge_telemetry_json,
    export_sessions_csv,
    sync_telemetry_to_api,
)
from src.table_monitor.analytics.kpi_calculator import compute_salon_kpis
from src.table_monitor.domain.models import POSTableState, TableConfig
from src.table_monitor.domain.state_machine import RestaurantSalonStateMachine
from src.table_monitor.geometry.spatial import evaluate_table_presence
from src.table_monitor.vision.annotator import annotate_salon_frame
from src.table_monitor.vision.yolo_detector import YOLOTableDetector


def load_tables_config(config_path: str | Path) -> List[TableConfig]:
    """Carga la definición de polígonos de mesas desde un archivo JSON."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de mesas: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    tables = []
    # Compatible con el formato estándar de plazas/mesas
    items = data.get("mesas") or data.get("plazas") or []
    for item in items:
        t_id = item.get("id") or item.get("mesa_id") or f"Mesa {len(tables) + 1}"
        pts = [tuple(p) for p in item.get("puntos", [])]
        tables.append(TableConfig(table_id=t_id, polygon=pts))
    return tables


def interactive_calibrate(image_path: str, output_json: str):
    """Herramienta interactiva para dibujar polígonos de mesas sobre una foto o video."""
    video_exts = (".mp4", ".avi", ".mov", ".webm", ".mkv")
    if image_path.lower().endswith(video_exts):
        cap = cv2.VideoCapture(image_path)
        ok, img = cap.read()
        cap.release()
        if not ok or img is None:
            sys.exit(f"Error: No se pudo extraer el fotograma del video {image_path}")
    else:
        img = cv2.imread(image_path)
        if img is None:
            sys.exit(f"Error: No se pudo cargar la imagen {image_path}")

    base = img.copy()
    clone = base.copy()
    current_pts: List[List[int]] = []
    mesas: List[dict] = []
    mesa_num = 1
    circle_mode = False  # Modo mesa redonda

    window_name = "Calibrador Manual de Mesas (GastroForge Vision)"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, min(1280, img.shape[1]), min(720, img.shape[0]))

    def redraw_all():
        nonlocal base, clone
        base = img.copy()
        for idx, m in enumerate(mesas, 1):
            pts = np.array(m["puntos"], np.int32)
            cv2.polylines(base, [pts], True, (0, 255, 0), 2, cv2.LINE_AA)
            cx, cy = int(np.mean(pts[:, 0])), int(np.mean(pts[:, 1]))
            cv2.putText(base, m["id"], (cx - 25, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2, cv2.LINE_AA)
        clone = base.copy()

    def generate_circle_polygon(center: List[int], perimeter: List[int], num_points: int = 16) -> List[List[int]]:
        cx, cy = center
        px, py = perimeter
        radius = math.hypot(px - cx, py - cy)
        polygon = []
        for i in range(num_points):
            angle = 2.0 * math.pi * i / num_points
            x = int(round(cx + radius * math.cos(angle)))
            y = int(round(cy + radius * math.sin(angle)))
            polygon.append([x, y])
        return polygon

    def on_mouse(event, x, y, flags, param):
        nonlocal current_pts, clone, mesa_num
        if event == cv2.EVENT_LBUTTONDOWN:
            if circle_mode:
                if len(current_pts) == 0:
                    current_pts.append([x, y])
                    cv2.circle(clone, (x, y), 5, (0, 0, 255), -1)
                    cv2.putText(clone, "Centro marcado. Clic en el borde/silla...", (x + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                elif len(current_pts) == 1:
                    poly = generate_circle_polygon(current_pts[0], [x, y], num_points=16)
                    m_id = f"Mesa {mesa_num}"
                    mesas.append({"id": m_id, "puntos": poly})
                    print(f"✔ Registrada mesa redonda {m_id} (16 vértices automáticos).")
                    mesa_num += 1
                    current_pts = []
                    redraw_all()
            else:
                current_pts.append([x, y])
                cv2.circle(clone, (x, y), 5, (0, 0, 255), -1)
                if len(current_pts) > 1:
                    cv2.line(clone, tuple(current_pts[-2]), tuple(current_pts[-1]), (0, 255, 255), 2, cv2.LINE_AA)
            cv2.imshow(window_name, clone)

    cv2.setMouseCallback(window_name, on_mouse)

    print("\n=======================================================")
    print("🛠️ MODO DE CALIBRACIÓN MANUAL DE MESAS (RECTAS Y REDONDAS)")
    print("=======================================================")
    print("• MODO POLÍGONO LIBRE (Por defecto):")
    print("  - Clic izquierdo en cada esquina del polígono.")
    print("  - Presiona ESPACIO para cerrar y guardar la mesa.")
    print("• MODO MESA REDONDA (Presiona tecla 'c'):")
    print("  - 1er clic: Centro de la mesa.")
    print("  - 2do clic: Borde exterior (incluyendo las sillas).")
    print("  - Se autogenera un polígono circular suave de 16 vértices.")
    print("• TECLA 'u':     Deshacer (elimina la última mesa registrada).")
    print("• TECLA 'r':     Reinicia los puntos de la mesa actual.")
    print("• TECLA 'q':     Guarda las mesas en el archivo JSON y sale.")
    print("=======================================================\n")

    while True:
        status_txt = "MODO: MESA REDONDA (Clic Centro + Borde)" if circle_mode else "MODO: POLIGONO (Clic esquinas + ESPACIO)"
        display_frame = clone.copy()
        cv2.putText(display_frame, status_txt, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if circle_mode else (255, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow(window_name, display_frame)

        key = cv2.waitKey(20) & 0xFF

        if key == ord("c"):
            circle_mode = not circle_mode
            current_pts = []
            clone = base.copy()
            print(f"-> Cambiado a {'MODO MESA REDONDA (círculo 2 clics)' if circle_mode else 'MODO POLÍGONO LIBRE'}")
        elif key == ord(" "):
            if not circle_mode and len(current_pts) >= 3:
                m_id = f"Mesa {mesa_num}"
                mesas.append({"id": m_id, "puntos": current_pts.copy()})
                print(f"✔ Registrada {m_id} con {len(current_pts)} vértices.")
                mesa_num += 1
                current_pts = []
                redraw_all()
            elif not circle_mode:
                print("⚠ Se requieren al menos 3 puntos para cerrar el polígono.")
        elif key == ord("u"):
            if mesas:
                eliminada = mesas.pop()
                mesa_num = len(mesas) + 1
                current_pts = []
                print(f"↩ Deshecha {eliminada['id']}.")
                redraw_all()
            else:
                print("No hay mesas para deshacer.")
        elif key == ord("r"):
            current_pts = []
            clone = base.copy()
            print("Puntos en curso reiniciados.")
        elif key == ord("q"):
            break

    cv2.destroyAllWindows()
    if mesas:
        out_p = Path(output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps({"mesas": mesas}, indent=2), encoding="utf-8")
        print(f"\n✅ ¡Configuración de {len(mesas)} mesas guardada en {output_json}!\n")


def run_pipeline(
    source: str,
    tables_config: str,
    model_path: str = "docs/Archive/yolo26n.pt",
    output_dir: str = "output/analisis",
    conf: float = 0.3,
    t_ocupar: float = 15.0,
    t_liberar: float = 30.0,
    every_n_frames: int = 2,
    privacy_blur: bool = True,
    save_video: bool = True,
    show_window: bool = False,
    mock_pos_bathroom_table: Optional[str] = None,
    waiting_queue_count: int = 0,
    api_url: Optional[str] = None,
):
    """Ejecuta el pipeline de monitoreo continuo sobre video o cámara."""
    tables = load_tables_config(tables_config)
    table_ids = [t.table_id for t in tables]
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap_source = int(source) if source.isdigit() else source
    cap = cv2.VideoCapture(cap_source)
    if not cap.isOpened():
        sys.exit(f"Error: No se pudo abrir la fuente de video {source}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_dur_s = total_frames / fps if fps > 0 else 0.0

    # Detección inteligente de clips cortos (ej. videos de 10s a 50s)
    if 0 < video_dur_s <= 50.0 and t_ocupar >= 10.0:
        t_ocupar = max(2.5, round(video_dur_s * 0.10, 1))
        t_liberar = max(3.5, round(video_dur_s * 0.18, 1))
        print(
            f"[!] [GastroForge Vision] Clip corto detectado ({video_dur_s:.1f}s): "
            f"Ajustando umbrales temporales adaptativos (t_ocupar={t_ocupar}s, t_liberar={t_liberar}s) "
            "para filtrar personas caminando y confirmar comensales sentados."
        )

    print(f"\n[GastroForge Vision] Cargando modelo YOLO ({model_path})...")
    detector = YOLOTableDetector(model_path=model_path)
    state_machine = RestaurantSalonStateMachine(
        table_ids=table_ids,
        t_ocupar=t_ocupar,
        t_liberar=t_liberar,
    )

    video_writer = None
    if save_video:
        video_out_path = out_dir / "salon_telemetria.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(str(video_out_path), fourcc, fps / every_n_frames, (w, h))

    print(f"[GastroForge Vision] Procesando video ({w}x{h} @ {fps:.1f} fps) | Mesas configuradas: {len(tables)}")
    frame_idx = 0
    start_real_clock = time.time()

    # Simulación de POS conectable: si se pasa mesa de baño, simular pedido activo
    pos_states: Dict[str, POSTableState] = {}
    if mock_pos_bathroom_table:
        pos_states[mock_pos_bathroom_table] = POSTableState(
            table_id=mock_pos_bathroom_table,
            has_active_order=True,
            order_id="GF-ORD-901",
            order_status="delivered",
            diner_count=1,
        )

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_idx += 1
            if frame_idx % every_n_frames != 0:
                continue

            current_time_s = frame_idx / fps

            # 1. Inferencia YOLO
            people_boxes, dish_boxes = detector.detect(frame, conf=conf, detect_dishes=True)

            # 2. Análisis Espacial inteligente (con soporte para mesas calibradas por superficie)
            people_presence = evaluate_table_presence(people_boxes, tables, criterion="chair_aware")
            dishes_presence = evaluate_table_presence(dish_boxes, tables, criterion="chair_aware")

            # 3. Transición de Estado y Fusión Transaccional
            state_machine.update(
                t=current_time_s,
                people_by_table=people_presence,
                dishes_by_table=dishes_presence,
                pos_states=pos_states,
            )

            # 4. Cálculo de KPIs
            current_states = {t_id: state_machine.get_state(t_id) for t_id in table_ids}
            completed_sessions = state_machine.get_all_completed_sessions()
            kpis = compute_salon_kpis(
                table_states=current_states,
                completed_sessions=completed_sessions,
                alerts=state_machine.all_alerts,
                waiting_queue_count=waiting_queue_count,
            )

            # 5. Anotación y HUD
            annotated_frame = annotate_salon_frame(
                frame=frame,
                tables=tables,
                trackers=state_machine.trackers,
                current_time_s=current_time_s,
                people_boxes=people_boxes,
                kpis=kpis,
                blur_privacy=privacy_blur,
            )

            if video_writer:
                video_writer.write(annotated_frame)

            if show_window:
                cv2.imshow("GastroForge Vision - Control de Mesas", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if frame_idx % (every_n_frames * 20) == 0:
                print(
                    f"Frame {frame_idx}/{total_frames} (t={current_time_s:.1f}s) | "
                    f"Libres: {kpis.free_tables} | Ocupadas: {kpis.occupied_tables} | "
                    f"Por recoger: {kpis.pending_clean_tables} | Ocupación: {kpis.occupancy_rate_percent}%"
                )

    finally:
        cap.release()
        if video_writer:
            video_writer.release()
        if show_window:
            cv2.destroyAllWindows()

    final_time_s = frame_idx / fps
    state_machine.force_close_all(final_time_s)

    # 6. Exportación final de artefactos analíticos para GastroForge
    completed_sessions = state_machine.get_all_completed_sessions()
    current_states = {t_id: state_machine.get_state(t_id) for t_id in table_ids}
    final_kpis = compute_salon_kpis(
        table_states=current_states,
        completed_sessions=completed_sessions,
        alerts=state_machine.all_alerts,
        waiting_queue_count=waiting_queue_count,
    )

    telemetry_data = build_gastroforge_telemetry_dict(
        final_kpis,
        state_machine.trackers,
        final_time_s,
    )
    json_path = out_dir / "gastroforge_telemetry.json"
    json_path.write_text(json.dumps(telemetry_data, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = export_sessions_csv(out_dir / "gastroforge_sessions.csv", completed_sessions)
    alerts_path = export_alerts_json(out_dir / "gastroforge_alerts.json", state_machine.all_alerts)

    api_sync_result = None
    if api_url:
        print(f"\n[GastroForge Vision] Sincronizando telemetría con API REST ({api_url})...")
        api_sync_result = sync_telemetry_to_api(telemetry_data, api_url)

    print("\n=======================================================")
    print("✅ PROCESAMIENTO COMPLETADO CON ÉXITO")
    print(f"📊 Reporte Telemetría GastroForge: {json_path}")
    print(f"📋 Registro de Sesiones CSV:       {csv_path}")
    print(f"🚨 Registro de Alertas Operativas: {alerts_path}")
    if save_video:
        print(f"🎥 Video Anotado con Privacidad:   {out_dir / 'salon_telemetria.mp4'}")
    if api_sync_result:
        if api_sync_result["success"]:
            print(f"🌐 Sincronización API GastroForge:  EXITOSA (HTTP {api_sync_result['status_code']})")
        else:
            print(f"⚠️ Sincronización API GastroForge:  FALLIDA ({api_sync_result['error']})")
    print(f"Diagnóstico Operativo: {final_kpis.operational_diagnosis}")
    print("=======================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="GastroForge Vision: Sistema de Control de Mesas con Ultralytics YOLO"
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Comandos disponibles")

    # Comando autocalibrar
    p_autocalib = subparsers.add_parser("autocalibrar", help="Detecta y calibra automáticamente las mesas de los videos")
    p_autocalib.add_argument("--carpeta", default="input", help="Carpeta con los videos de entrada")
    p_autocalib.add_argument("--modelo", default="docs/Archive/yolo26n.pt", help="Ruta al modelo YOLO")
    p_autocalib.add_argument("--salida", default="config", help="Carpeta donde guardar los archivos JSON de mesas")

    # Comando calibrar
    p_calib = subparsers.add_parser("calibrar", help="Marcar polígonos de mesas sobre una foto")
    p_calib.add_argument("--imagen", required=True, help="Ruta de la imagen de referencia")
    p_calib.add_argument("--salida", default="config/mesas.json", help="Ruta para guardar el JSON de mesas")

    # Comando analizar
    p_run = subparsers.add_parser("analizar", help="Ejecutar análisis sobre video o cámara")
    p_run.add_argument("--fuente", required=True, help="Archivo de video o 0 para webcam")
    p_run.add_argument("--mesas", required=True, help="Ruta al JSON de mesas")
    p_run.add_argument("--modelo", default="docs/Archive/yolo26n.pt", help="Ruta al modelo YOLO")
    p_run.add_argument("--salida", default="output/analisis", help="Carpeta de salida")
    p_run.add_argument("--conf", type=float, default=0.40, help="Umbral de confianza")
    p_run.add_argument("--t-ocupar", type=float, default=15.0, help="Segundos para confirmar ocupada")
    p_run.add_argument("--t-liberar", type=float, default=30.0, help="Segundos sin gente para liberar")
    p_run.add_argument("--cada", type=int, default=2, help="Analizar 1 de cada N cuadros")
    p_run.add_argument("--sin-difuminar", action="store_true", help="Desactiva difuminado de personas")
    p_run.add_argument("--mostrar", action="store_true", help="Mostrar ventana visual durante ejecución")
    p_run.add_argument("--cola", type=int, default=0, help="Cantidad de personas esperando en cola")
    p_run.add_argument("--simular-bano", help="ID de mesa para simular ausencia al baño con pedido activo")
    p_run.add_argument("--api-url", default=None, help="URL de la API GastroForge para enviar telemetría (ej: http://localhost:3000/api/v1/telemetry/ingest)")

    args = parser.parse_args()

    if args.subcommand == "autocalibrar":
        from src.table_monitor.auto_calibrate import auto_calibrate_all_inputs
        auto_calibrate_all_inputs(
            input_dir=args.carpeta,
            config_dir=args.salida,
            model_path=args.modelo,
        )
    elif args.subcommand == "calibrar":
        interactive_calibrate(args.imagen, args.salida)
    elif args.subcommand == "analizar":
        run_pipeline(
            source=args.fuente,
            tables_config=args.mesas,
            model_path=args.modelo,
            output_dir=args.salida,
            conf=args.conf,
            t_ocupar=args.t_ocupar,
            t_liberar=args.t_liberar,
            every_n_frames=args.cada,
            privacy_blur=not args.sin_difuminar,
            show_window=args.mostrar,
            waiting_queue_count=args.cola,
            mock_pos_bathroom_table=args.simular_bano,
            api_url=args.api_url,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
