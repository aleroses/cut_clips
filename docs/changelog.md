# Changelog — Anki Video Tool

Registro incremental de cambios por fase del plan de evolución GUI.

## Fase 0 — Análisis del proyecto

**Fecha:** 2026-09-20

### Qué se hizo

- Análisis completo del código existente (CLI, core, GUI prototipo).
- Identificación de flujos, dependencias, problemas y riesgos.
- Propuesta de arquitectura incremental por 17 fases.
- Creación de documentación inicial en `docs/`.

### Archivos creados

- `docs/01-project-analysis.md`
- `docs/02-current-architecture.md`
- `docs/changelog.md`

### Decisiones técnicas

- Mantener formato TSV Anki de 9 campos sin cambios.
- CSV como import/export, no como fuente de verdad (desde Fase 2).
- No eliminar scripts CLI; reutilizar lógica de `core/`.
- Primera implementación post-análisis: Fase 1 (estabilización).

### Cómo probar

Revisar que los documentos reflejan el estado actual del repositorio.

---

## Fase 1 — Estabilización (sin cambio de comportamiento CLI)

**Fecha:** 2026-09-20

### Qué se hizo

- Añadido `requirements.txt` con dependencias Python documentadas.
- Extraída lógica ffprobe a `media/probe.py`; `inspect_media.py` importa desde ahí.
- Centralizado naming en `core/naming.py` (etiquetas de episodio, nombres de clip y TSV).
- `clip_engine.py` y `cut_clips.py` usan `core/naming` (mismos nombres que antes).
- Corrección GUI: `cut_selected_segment()` aplica valores del spinbox antes de cortar.
- Corrección GUI: `export_tsv()` exporta solo segmentos `exported`.
- README actualizado: `inspect_media`, GUI, estructura del proyecto.

### Archivos creados

- `requirements.txt`
- `media/__init__.py`, `media/probe.py`
- `core/naming.py`

### Archivos modificados

- `inspect_media.py`
- `core/clip_engine.py`
- `cut_clips.py`
- `gui_app.py`
- `README.md`

### Decisiones técnicas

- `media/probe.probe()` acepta `exit_on_error` para uso futuro desde GUI.
- Formato `S01-Ep01` conservado como default (`style='legacy'`) por compatibilidad CLI.
- Formato TSV Anki no modificado.

### Cómo probar

```bash
python3 -c "from core.naming import clip_video_filename; assert clip_video_filename('S','S01-Ep01',1).endswith('.webm')"
python3 inspect_media.py --help
python3 gui_app.py  # cortar con spinbox sin Aplicar; exportar solo tras Cortar
```

---

## Fase 2 — Modelo de proyecto/episodio

**Fecha:** 2026-09-20

### Qué se hizo

- Módulo `persistence/` con modelo de datos interno (JSON).
- Clases `Project`, `Episode`, `Clip`, `SubtitleCue`, `TranslationConfig`.
- Enum `ClipStatus`: pending, modified, preview, generated, outdated, error.
- Fingerprint de generación en `Clip` para detectar clips desactualizados (base Fase 11).
- `save_project()` / `load_project()` con escritura atómica.
- Helpers en `persistence/builders.py` para crear proyecto y clips desde parser.
- Documentación del modelo en `docs/03-data-model.md`.

### Archivos creados

- `persistence/__init__.py`
- `persistence/models.py`
- `persistence/store.py`
- `persistence/builders.py`
- `docs/03-data-model.md`

### Decisiones técnicas

- `schema_version: 1` en JSON para migraciones futuras.
- API keys de traducción excluidas del archivo de proyecto.
- `episode_label` default `S01-Ep01` via `core/naming.format_episode_label`.
- La GUI y CLI aún no usan el modelo; integración en Fases 3–9.

### Cómo probar

```bash
python3 -c "
from persistence.builders import new_project
from persistence import save_project, load_project
p = new_project(series_name='Test', season=1, episode=1)
save_project(p, '/tmp/test.anki-project.json')
assert load_project('/tmp/test.anki-project.json').series_name == 'Test'
print('OK')
"
```

---

## Fase 3 — FFprobe en GUI

**Fecha:** 2026-09-20

### Qué se hizo

- Al abrir un vídeo, la GUI ejecuta ffprobe y muestra diálogo de pistas.
- Nuevo `ui/media_info_dialog.py`: vídeo, audio, subtítulos, filtro por idioma.
- Selección de `audio_track` y `video_track` aplicada al cortar clips.
- `subtitle_track_index` guardado para extracción embebida (Fase 4).
- Helpers en `media/probe.py`: `get_format_info`, `suggest_tracks`, `summarize_media`.
- `classify_streams` ahora incluye `relative_index` en pistas de vídeo.
- Mensajes amigables si ffprobe no está instalado o falla el análisis.
- Aviso explícito para subtítulos gráficos (PGS/VobSub).

### Archivos creados

- `ui/__init__.py`
- `ui/media_info_dialog.py`
- `docs/04-gui.md`

### Archivos modificados

- `gui_app.py`
- `media/probe.py`

### Decisiones técnicas

- Cancelar el diálogo no carga el vídeo.
- Índices de audio/vídeo para corte: relativos (como CLI `cut_clips.py`).
- Índice de subtítulo: absoluto (como CLI `inspect_media.py --extract-subtitle`).
- `media_summary` preparado para integración con `persistence.Episode` en fases posteriores.

### Cómo probar

```bash
python3 gui_app.py
# Archivo → Abrir vídeo → verificar diálogo de pistas
# Elegir audio_track distinto de 0 si hay varias pistas
# Cortar un clip y comprobar que usa la pista seleccionada
python3 -m py_compile gui_app.py ui/media_info_dialog.py media/probe.py
```

---

## Fase 4 — Subtítulos en GUI

**Fecha:** 2026-09-20

### Qué se hizo

- **Archivo → Abrir subtítulo (.srt)** ahora muestra diálogo con opciones de parseo
  (offset, scale, shift, trim, filtros, idioma) — equivalente a `parse_srt_preview.py`.
- **Archivo → Extraer subtítulos del vídeo…** extrae la pista embebida seleccionada
  en Fase 3, guarda `{video}.track{N}.srt` y carga oraciones.
- Extracción FFmpeg en hilo aparte (`ExtractSubtitleTask`).
- Validación explícita de subtítulos gráficos antes de extraer.
- Confirmación al reemplazar líneas ya cargadas.
- Persistencia en memoria de `parser_options` y `subtitle_path`.

### Archivos creados

- `ui/parser_options_widget.py`
- `ui/subtitle_load_dialog.py`

### Archivos modificados

- `gui_app.py`
- `media/probe.py` — `find_subtitle_stream`, `subtitle_extract_path`
- `docs/04-gui.md`

### Decisiones técnicas

- Opciones de parseo compartidas entre archivo externo y extracción embebida.
- Idioma del parser se inicializa desde `subtitle_language` del diálogo de pistas.
- SRT extraído se guarda junto al vídeo (reutilizable fuera de la GUI).

### Cómo probar

```bash
python3 gui_app.py
# 1. Abrir vídeo → elegir pista de subtítulos texto
# 2. Extraer subtítulos del vídeo → ajustar shift si hace falta → cargar
# 3. O Abrir subtítulo (.srt) con opciones de parseo
python3 -m py_compile ui/parser_options_widget.py ui/subtitle_load_dialog.py gui_app.py
```

---

## Fase 5 — Controles de reproducción mpv

**Fecha:** 2026-09-20

### Qué se hizo

- Panel **Reproducción** con play/pausa, detener, ir a inicio/fin del clip, seek ±1 s.
- Bucle A–B del segmento (Start–End) con toggle play/pausa.
- Etiqueta de posición actual vs rango del segmento.
- Seek relativo acotado al segmento cuando el bucle está activo.
- Atajos de teclado: Espacio (play/pausa), ←/→ (±1 s).
- Actualización de `ab-loop-a/b` al modificar Start/End durante reproducción.
- Limpieza de mpv en `closeEvent`.

### Archivos modificados

- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Abrir vídeo + subtítulos → seleccionar línea
# Reproducir segmento → probar pausa, seek, inicio/final, atajos
```

---

## Fase 6 — Deshacer / Rehacer

**Fecha:** 2026-09-20

### Qué se hizo

- Módulo `ui/undo_stack.py` con historial de instantáneas (undo/redo).
- Menú **Edición → Deshacer / Rehacer** (Ctrl+Z, Ctrl+Shift+Z).
- Historial para: aplicar tiempos, fusionar, eliminar.
- Restauración de segmentos, numeración y selección al deshacer/rehacer.
- Historial se limpia al cargar subtítulos nuevos.
- Spinboxes Start/End bloquean señales al cambiar de línea (evita parpadeos).

### Archivos creados

- `ui/undo_stack.py`

### Archivos modificados

- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Cargar subtítulos → aplicar tiempos → Ctrl+Z deshace
# Fusionar dos líneas → Ctrl+Z restaura la segunda
python3 -m py_compile ui/undo_stack.py gui_app.py
```

---

## Fase 7 — Previsualizar vs generar clip

**Fecha:** 2026-09-20

### Qué se hizo

- UI separada: **Previsualización (mpv)** vs **Generación (FFmpeg)**.
- Botón **🔁 Probar clip** — bucle mpv sin archivos en disco.
- Botón **💾 Generar clip** — sustituye «Cortar»; crea WebM + MP3.
- Estado `preview` en segmentos previsualizados (`[PREVIEW]` en la lista).
- Al cambiar tiempos en spinboxes, `preview` → `pending` automáticamente.
- Confirmación antes de sobrescribir archivos existentes.
- Botón **Reanudar** cuando la previsualización está en pausa.

### Archivos modificados

- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Probar clip varias veces → no debe aparecer nada nuevo en output_files/
# Generar clip → deben crearse .webm y .mp3
# Cambiar spinbox tras preview → etiqueta [PREVIEW] desaparece
```

---

## Fase 8 — Unir subtítulos con trazabilidad

**Fecha:** 2026-09-20

### Qué se hizo

- `group_into_sentences()` añade `cue_indices` a cada oración (índices de bloques SRT).
- GUI guarda `cue_map` y `cue_indices` por segmento/clip.
- Panel **Subtítulos incluidos en el clip** con detalle de cada bloque.
- Lista muestra rango SRT `(SRT #N–#M)`.
- Fusionar une `cue_indices` de ambas líneas y muestra resumen en barra de estado.
- Documentación «Cómo abrir un vídeo» en `docs/04-gui.md`.

### Archivos modificados

- `core/subtitle_parser.py`
- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Cargar SRT → ver cues en lista y panel inferior
# Fusionar dos líneas → verificar que cue_indices se combinan
python3 -c "
from core.subtitle_parser import parse_srt_blocks, group_into_sentences
blocks = [{'start':0,'end':1,'raw_text':'Hello.'}]
s,_ = group_into_sentences(blocks)
assert 'cue_indices' in s[0]
"
```

---

## Fase 9 — Guardar y cargar proyecto JSON

**Fecha:** 2026-09-21

### Qué se hizo

- Integración de `persistence/` en la GUI vía `persistence/gui_bridge.py`.
- Menú **Archivo → Guardar proyecto** (`Ctrl+S`), **Guardar proyecto como…** y **Abrir proyecto…**.
- Formato `{serie}_{S01-Ep01}.anki-project.json` junto al vídeo (sugerido al guardar).
- Indicador `*` en el título de ventana cuando hay cambios sin guardar.
- Aviso al cerrar con opciones Guardar / No guardar / Cancelar.
- Confirmación al abrir otro vídeo o proyecto con cambios pendientes.
- Persiste: vídeo, pistas, subtítulos (`cue_map`), clips (pending/preview/exported), opciones de parseo, traducción opcional.

### Archivos creados / modificados

- `persistence/gui_bridge.py` (nuevo)
- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Abrir vídeo + SRT → editar → Ctrl+S (primera vez: elegir ruta)
# Cerrar y Archivo → Abrir proyecto… → verificar clips y tiempos
python3 -c "from persistence.gui_bridge import build_project_from_gui; print('ok')"
```

---

## Fase 10 — Naming CLI y padding al generar

**Fecha:** 2026-09-21

### Qué se hizo

- Clips generados con naming `{serie}_{S01-Ep01}_Line_{id:04d}` (igual que `cut_clips.py`).
- Panel **Generación**: campo **Serie** y spinboxes **Padding inicio/final**.
- `compute_padded_window()` en `clip_engine.py` (reutilizado por CLI y GUI).
- Padding al cortar respeta límites de líneas vecinas; mpv sigue sin padding.
- TSV exportado con nombres CLI y `episode_label`.
- Padding y serie persisten en el proyecto JSON.

### Archivos modificados

- `core/clip_engine.py`
- `persistence/gui_bridge.py`
- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Abrir vídeo → cargar SRT → poner padding 0.3 → Generar clip
# Verificar output_files/{serie}_S01-Ep01_Line_0001.webm
python3 -c "from core.clip_engine import compute_padded_window; print(compute_padded_window(10,12,padding_start=0.5))"
```

---

## Fase 11 — Detección OUTDATED vía fingerprint

**Fecha:** 2026-09-21

### Qué se hizo

- Al generar un clip se guarda `generation_fingerprint` en el segmento y en el JSON.
- `build_segment_fingerprint()` y `apply_outdated_status()` en `gui_bridge.py`.
- Cambios de padding, pistas o vídeo marcan clips generados como `[OUTDATED]`.
- Clips desactualizados vuelven a la lista (amarillo); regenerar con **Generar clip**.
- Exportar TSV avisa si hay outdated y excluye esos clips del export.

### Archivos modificados

- `persistence/gui_bridge.py`
- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Generar un clip → cambiar padding → ver [OUTDATED] en la lista
python3 -c "from persistence.gui_bridge import apply_outdated_status, build_segment_fingerprint; print('ok')"
```

---

## Fase 12 — Generación por lotes y cancelación

**Fecha:** 2026-09-21

### Qué se hizo

- Botón **Generar todos pendientes** — usa `run_batch()` del CLI (una pasada ffmpeg).
- Incluye clips `pending`, `preview` y `outdated`.
- **Cancelar lote** con `BatchCancelToken` (termina el subprocess).
- Diálogo: omitir archivos existentes o sobrescribir.
- Barra de progreso indeterminada; bloqueo de generación individual durante el lote.

### Archivos modificados

- `core/clip_engine.py` — `BatchCancelToken`, `run_batch(..., cancel_token=)`
- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Cargar SRT → Generar todos pendientes → Cancelar lote (opcional)
python3 -c "from core.clip_engine import BatchCancelToken; print('ok')"
```

---

## Fase 12.1 — Crash al abrir vídeo (SIGSEGV)

**Fecha:** 2026-09-21

### Qué se hizo

- Corregido segmentation fault al pulsar OK en «Análisis del archivo multimedia».
- Causa: Qt cambia `LC_NUMERIC` tras `QApplication`; libmpv rechaza `mpv_create()`.
- `_ensure_mpv_numeric_locale()` en `gui_app.py` (tras QApplication y antes de `mpv.MPV`).
- Documentación en `docs/12.1-crash-opening-media.md`.

### Archivos modificados

- `gui_app.py`
- `docs/12.1-crash-opening-media.md`

### Cómo probar

```bash
python3 gui_app.py
# Archivo → Abrir vídeo → OK — la app no debe cerrarse
python3 -X faulthandler -c "import gui_app; gui_app._ensure_mpv_numeric_locale(); print('ok')"
```

---

## Fase 12.2 — Reproducción mpv embebida

**Fecha:** 2026-09-21

### Qué se hizo

- Restaurado embed de mpv en el panel de previsualización (ventana externa en Wayland).
- **Capa 1:** `QT_QPA_PLATFORM=xcb` bajo Wayland+XWayland, atributos nativos del `QFrame`, init diferida, `vo=x11`.
- **Capa 2:** `ui/mpv_gl_widget.py` con `QOpenGLWidget` + Render API para Wayland nativo.
- `_shutdown_mpv_player()` y cierre ordenado en `closeEvent`.
- Documentación en `docs/12.2-embedded-mpv.md`.

### Archivos modificados

- `gui_app.py`
- `ui/mpv_gl_widget.py` (nuevo)
- `docs/12.2-embedded-mpv.md`

### Cómo probar

```bash
python3 gui_app.py
# Abrir vídeo → OK — vídeo dentro del panel negro
python3 -X faulthandler -c "import gui_app; gui_app._configure_qt_platform_for_mpv(); print('ok')"
```

---

## Fase 12.2b — Flujo de carga vídeo + subtítulos

**Fecha:** 2026-09-21

### Qué se hizo

- Tras OK en «Abrir vídeo», carga automática de subtítulos: sidecar `.srt` o extracción de pista embebida textual.
- `_finish_video_open()` unifica vídeo + subtítulos + sincronización GUI.
- mpv: rutas absolutas, `log_handler`, try/except, verificación post-`play()`.
- GUI: primera oración seleccionada, Start/End actualizados, mensaje «sin oraciones cargadas» si no hay SRT.

### Archivos modificados

- `gui_app.py`
- `media/probe.py` — `find_sidecar_subtitle()`
- `ui/mpv_embed.py`, `ui/mpv_gl_widget.py`

### Cómo probar

```bash
python3 gui_app.py
# Archivo → Abrir vídeo → OK — lista poblada y vídeo en panel negro
```

---

## Fase 12.2c — Salida de audio mpv

**Fecha:** 2026-09-21

### Qué se hizo

- Corregido `ao=auto` que fallaba con `Audio output auto not found` en Debian/PipeWire.
- Default `ao=pulse,pipewire,alsa` en `ui/mpv_embed.py`.
- Variable `ANKI_MPV_AO` para forzar driver (ej. `ANKI_MPV_AO=alsa`).

### Archivos modificados

- `ui/mpv_embed.py`
- `docs/12.2-embedded-mpv.md`

### Cómo probar

```bash
python3 gui_app.py
# Abrir vídeo → Probar clip — debe oírse audio en el segmento
```

---

## Fase 13 — Edición, lista y layout GUI

**Fecha:** 2026-09-21

### Qué se hizo

- Campo **Texto** editable en panel izquierdo (actualización inmediata en lista).
- Lista sin metadatos `(SRT #…)`; clips generados visibles con `[✓]`.
- Botón **Dividir clip** (posición de reproducción o punto medio).
- Selección preservada tras «Aplicar tiempos» y refrescos de lista.
- Panel izquierdo en `QScrollArea` (Traducción accesible con scroll).

### Archivos modificados

- `gui_app.py`
- `docs/04-gui.md`

### Cómo probar

```bash
python3 gui_app.py
# Editar texto, dividir clip, generar clip → [✓] en lista
```

---

## Fase 13.1 — Capitalización, división SRT y tag [PREVIEW]

**Fecha:** 2026-09-21

### Qué se hizo

- **Fusionar / dividir:** texto y tiempos reconstruidos desde `cue_map` (raw SRT) con `_restore_segment_text_and_bounds`, sin mezclar capitalización normalizada.
- **Dividir clip:** diálogo para cortar en límites entre bloques SRT (`ui/srt_split_dialog.py`); preselección según playhead; fallback por tiempo si hay menos de 2 bloques.
- **Tag [PREVIEW]:** estado visual `_preview_display_id`; no pisa `[✓]` en clips exportados; se limpia al cambiar de fila o detener preview.

### Archivos creados

- `ui/srt_split_dialog.py`

### Archivos modificados

- `gui_app.py`
- `docs/changelog.md`

### Cómo probar

```bash
python3 gui_app.py
# 1. Fusionar dos clips → texto con capitalización/HTML del SRT fuente
# 2. Dividir clip con ≥2 bloques SRT → diálogo con bloque preseleccionado
# 3. Probar clip → cambiar fila → [PREVIEW] desaparece; [✓] se mantiene en exportados
```

---

## Fase 12.3 — Estabilidad mpv (instancia persistente)

**Fecha:** 2026-09-21

### Qué se hizo

- **Una sola instancia mpv** durante el ciclo de vida de la app; recarga con `loadfile replace` (sin `terminate()` al cambiar vídeo).
- **`_stop_mpv_playback()`** separado de **`_shutdown_mpv_player()`** (solo en `closeEvent`).
- Carga de proyecto JSON: parar mpv → limpiar GUI → parsear → aplicar state → `loadfile` al final.
- Cierre seguro Capa 1: `wid=0` + `processEvents()` antes de `terminate()`.

### Archivos modificados

- `gui_app.py`
- `ui/mpv_gl_widget.py`
- `docs/12.2-embedded-mpv.md`
- `docs/changelog.md`

### Cómo probar

```bash
python3 -X faulthandler gui_app.py
# Abrir vídeo A → Abrir vídeo B → Abrir proyecto .json → Cerrar app (sin munmap_chunk)
```
