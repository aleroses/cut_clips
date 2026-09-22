# Interfaz gráfica (GUI)

Documentación de la aplicación PySide6 (`gui_app.py`).

## Arranque

```bash
python3 gui_app.py
```

Requisitos: PySide6, python-mpv, libmpv, ffmpeg/ffprobe.

## Flujo principal

1. **Archivo → Abrir vídeo** — analiza el archivo con ffprobe y muestra el diálogo de pistas.
2. **Archivo → Abrir subtítulo (.srt)** o **Extraer subtítulos del vídeo** — con opciones de parseo.
3. Seleccionar línea → ajustar Start/End → previsualizar con mpv (A–B loop).
4. **Cortar** — genera WebM + MP3 en `output_files/` junto al vídeo.
5. **Exportar TSV** — solo clips ya cortados (`exported`).

## Fase 3 — Análisis multimedia al abrir vídeo

Al elegir un vídeo, la aplicación:

1. Ejecuta `media.probe.probe()` (ffprobe JSON).
2. Muestra `ui.media_info_dialog.MediaInfoDialog` con:
   - **Vídeo:** códec, resolución, FPS, bitrate por pista.
   - **Audio:** índice relativo (`audio_track`) e absoluto, idioma, canales, frecuencia.
   - **Subtítulos:** índice absoluto, idioma, tipo texto vs imagen.
3. Permite filtrar por idioma (código ISO 639-1/2) para sugerir pistas.
4. Guarda la selección en la ventana principal:
   - `audio_track`, `video_track` — usados al cortar clips.
   - `subtitle_track_index` — usado para extracción embebida (Fase 4).
   - `media_summary` — resumen para persistencia futura.

### Mensajes al usuario

- **ffprobe no instalado:** diálogo claro con instrucción `apt install ffmpeg`.
- **Subtítulos gráficos (PGS):** aviso en el diálogo; confirmación si se elige esa pista.
- **Sin subtítulos embebidos:** indicación de usar archivo `.srt` externo.

### Cancelar el diálogo

Si se pulsa Cancelar, el vídeo no se carga (no se modifica el estado anterior).

## Estado en memoria (MainWindow)

| Campo | Uso |
|-------|-----|
| `probe_data` | JSON crudo de ffprobe |
| `media_summary` | Resumen via `summarize_media()` |
| `audio_track` | Índice relativo FFmpeg `0:a:N` |
| `video_track` | Índice relativo FFmpeg `0:v:N` |
| `subtitle_track_index` | Índice absoluto para extracción |
| `subtitle_language` | Código idioma preferido |
| `subtitle_path` | Ruta del SRT cargado o extraído |
| `parser_options` | Últimas opciones de parseo usadas |
| `segments` | Lista de dicts `{id, start, end, text, status}` |

## Fase 4 — Carga y extracción de subtítulos

### Abrir subtítulo (.srt)

1. Elige un archivo `.srt`.
2. Aparece el diálogo **Cargar subtítulos** con opciones equivalentes a `parse_srt_preview.py`:
   - idioma, offset, scale, shift, trim inicio/final, duración/palabras mínimas.
3. Las oraciones agrupadas reemplazan la lista (con confirmación si ya había líneas).

### Extraer subtítulos del vídeo

Requiere vídeo abierto con pista de subtítulos embebida seleccionada (Fase 3).

1. **Archivo → Extraer subtítulos del vídeo…**
2. Valida que la pista sea textual (no PGS/VobSub).
3. Muestra opciones de parseo.
4. Extrae con FFmpeg a `{video}.track{N}.srt` (async, no bloquea la UI).
5. Parsea y carga las oraciones.

### Mensajes de error

- Pista gráfica: explicación clara, sin intentar extraer.
- FFmpeg no instalado / extracción fallida.
- Parseo fallido (archivo corrupto o formato no SRT).

## Fase 5 — Controles de reproducción mpv

Panel **Reproducción** junto al vídeo:

| Control | Acción |
|---------|--------|
| ▶ Reproducir segmento / ⏸ Pausar | Bucle A–B entre Start y End |
| ■ Detener | Pausa y desactiva el bucle |
| ⏮ Inicio clip | Salta al Start |
| ⏭ Final clip | Salta cerca del End y pausa |
| ◀ −1 s / +1 s ▶ | Seek relativo (limitado al segmento si el bucle está activo) |

- Etiqueta de **posición actual** y rango del segmento (actualizada cada 200 ms durante reproducción).
- Al cambiar Start/End con el bucle activo, mpv actualiza `ab-loop-a/b` al instante.
- **Atajos** (solo cuando el foco no está en un campo de texto/número):
  - `Espacio` — play/pausa del segmento
  - `←` / `→` — retroceder / avanzar 1 s
- `closeEvent` libera la instancia mpv al cerrar la ventana.

## Fase 6 — Deshacer / Rehacer

Menú **Edición** con operaciones sobre segmentos:

| Acción | Atajo |
|--------|-------|
| Deshacer | Ctrl+Z |
| Rehacer | Ctrl+Shift+Z |

Operaciones registradas en el historial:

- Aplicar tiempos a la línea seleccionada
- Fusionar con siguiente
- Eliminar línea

Cada entrada guarda una instantánea de todos los segmentos, `next_id` y la línea
seleccionada. Al cargar subtítulos nuevos, el historial se reinicia.

Los atajos no se activan cuando el foco está en un campo de texto o número
(API key, opciones de parseo, spinboxes Start/End).

## Fase 7 — Previsualizar vs generar

Dos acciones claramente separadas:

| Acción | Botón | Efecto |
|--------|-------|--------|
| **Previsualizar** | 🔁 Probar clip | mpv A–B loop; **no escribe archivos** |
| **Generar** | 💾 Generar clip | FFmpeg → `.webm` + `.mp3` en `output_files/` |

### Estado PREVIEW

Tras «Probar clip», la línea muestra la etiqueta `[PREVIEW]` en verde.
Si cambias Start/End en los spinboxes sin aplicar, vuelve a `pending`.
«Generar clip» pide confirmación si los archivos ya existen.

La previsualización se puede repetir las veces que haga falta antes de generar.

## Fase 8 — Unir subtítulos con trazabilidad

Cada clip guarda `cue_indices`: qué bloques del SRT original lo componen.

- Al cargar subtítulos, el parser registra los índices en cada oración.
- La lista muestra `(SRT #12–#14 (3 cues))` junto a cada línea.
- El panel **Subtítulos incluidos en el clip** detalla cada bloque con tiempos y texto.
- **Fusionar con siguiente** concatena textos, extiende `end` y **une** las listas de índices.

## Fase 9 — Guardar y cargar proyecto JSON

La GUI usa el modelo de `persistence/` como fuente de verdad interna.

| Acción | Atajo | Efecto |
|--------|-------|--------|
| **Guardar proyecto** | Ctrl+S | Escribe `.anki-project.json` (pide ruta la primera vez) |
| **Guardar proyecto como…** | — | Elige ruta explícita |
| **Abrir proyecto…** | — | Restaura vídeo, pistas, subtítulos y clips |

### Indicador de cambios

- Título de ventana con `*` si hay cambios sin guardar.
- Al cerrar: **Guardar** / **No guardar** / **Cancelar**.
- Al abrir otro vídeo o proyecto con cambios: confirmación de descarte.

### Contenido del JSON

Episodio actual: rutas de vídeo/SRT, pistas ffprobe, `cue_map`, clips con
`cue_indices`, estados (`pending`, `preview`, `exported`), opciones de parseo
y preferencia de traducción (sin API key).

Ruta sugerida junto al vídeo: `{serie}_{S01-Ep01}.anki-project.json`

## Fase 10 — Naming CLI y padding al generar

Panel **Generación (FFmpeg)**:

| Campo | Uso |
|-------|-----|
| **Serie** | Nombre base para archivos (mismo rol que `--series-name` en cut_clips.py) |
| **Padding inicio / final** | Segundos extra al cortar (equivalente a `--padding`, por separado) |

### Naming de archivos

Los clips generados usan el formato CLI:

```text
{serie}_{S01-Ep01}_Line_{id:04d}.webm
{serie}_{S01-Ep01}_Line_{id:04d}.mp3
```

Ejemplo: `Spawn_Anki_Video_S01-Ep01_Line_0003.webm`

### Padding

- La **previsualización mpv** usa los tiempos Start/End del diálogo (sin padding).
- **Generar clip** aplica padding respetando límites de la línea anterior/siguiente
  (misma lógica que `compute_padded_windows()` en el CLI).
- El TSV exportado referencia los nombres CLI y la etiqueta de episodio.

## Fase 11 — Detección OUTDATED (fingerprint)

Tras **Generar clip**, se guarda un `generation_fingerprint` con tiempos,
padding, texto, vídeo y pistas usadas al cortar.

Si cambia la configuración (padding global, pista de audio/vídeo, vídeo, etc.),
los clips ya generados pasan a **`[OUTDATED]`** (amarillo en la lista).

| Estado | Lista | Significado |
|--------|-------|-------------|
| `pending` / `preview` | Visible | Sin generar o solo previsualizado |
| `exported` | Oculto (contador en cabecera) | Archivos coinciden con la config |
| `outdated` | Visible `[OUTDATED]` | Archivos en disco ya no coinciden |

- Regenera con **Generar clip** para actualizar el fingerprint.
- **Exportar TSV** avisa si hay clips desactualizados y solo incluye los `exported`.

## Fase 12 — Generación por lotes y cancelación

| Control | Efecto |
|---------|--------|
| **⚡ Generar todos pendientes** | Una pasada FFmpeg (`run_batch`) para pending, preview y outdated |
| **Cancelar lote** | Termina ffmpeg en curso; conserva clips ya escritos |

- Diálogo previo: omitir archivos existentes o **sobrescribir**.
- Barra de progreso indeterminada durante la decodificación.
- Durante el lote, «Generar clip» individual queda deshabilitado.

## Fase 13 — Edición, lista y layout

| Control | Efecto |
|---------|--------|
| **Texto** (panel izquierdo) | Edita la oración seleccionada; se refleja al instante en la lista |
| **Dividir clip** | Parte el clip en la posición de reproducción (o punto medio) |
| **Fusionar / Eliminar** | Sin cambio de comportamiento |
| Lista `[✓]` | Clips ya generados permanecen visibles con marca de verificación |
| Scroll panel izquierdo | Acceso a «Traducción (opcional)» en ventanas pequeñas |

- La trazabilidad SRT (`#1`, `#2`…) sigue en **Subtítulos incluidos en el clip** (panel derecho).
- «Aplicar tiempos» mantiene la fila seleccionada.

## Cómo abrir un vídeo para editar

Desde la raíz del proyecto:

```bash
cd /home/ale/Documents/projects/anki_video_tool
pip install -r requirements.txt   # PySide6, python-mpv, deepl (opcional)
sudo apt install ffmpeg libmpv2    # sistema: ffprobe, ffmpeg, mpv

python3 gui_app.py
```

### Pasos en la interfaz

1. **Archivo → Abrir vídeo…** — elige tu `.mkv` / `.mp4` / `.webm`.
2. En el diálogo **Análisis del archivo multimedia**:
   - Revisa pistas de vídeo, audio y subtítulos.
   - Elige **pista de audio** (para los clips).
   - Elige **pista de subtítulos embebida** (si la hay) o deja «Ninguno».
   - Pulsa **OK** (Cancelar no carga el vídeo).
3. Carga subtítulos de una de estas formas:
   - **Archivo → Extraer subtítulos del vídeo…** (si elegiste pista embebida en el paso 2).
   - **Archivo → Abrir subtítulo (.srt)…** (archivo `.srt` externo).
4. Ajusta opciones de parseo (shift, idioma, etc.) y confirma.
5. Selecciona una línea en la lista → **Probar clip** → edita tiempos → **Generar clip**.
6. **Ctrl+S** o **Archivo → Guardar proyecto** para retomar más tarde.

El vídeo se reproduce en el panel negro izquierdo (requiere `python-mpv` + `libmpv`).

## Próximas fases GUI

| Fase | Funcionalidad |
|------|----------------|
| 13 | Edición de texto, dividir clip, lista con [✓], scroll panel izquierdo |
| 14+ | TranslationProvider, etc. |
