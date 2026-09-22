# Modelo de datos (Fase 2)

El proyecto usa un modelo interno JSON como fuente de verdad. CSV y TSV
permanecen como formatos de importación/exportación.

## Jerarquía

```text
Project
 └── Episode (1..N)
      ├── SubtitleCue[]
      └── Clip[]
```

## Project

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `series_name` | string | Nombre de la serie para archivos |
| `root_dir` | string | Directorio raíz del proyecto |
| `last_clip_id` | int | Último ID de clip usado (numeración global) |
| `episodes` | Episode[] | Episodios del proyecto |

Archivo sugerido: `{series}_{episode_label}.anki-project.json`

## Episode

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `video_path` | string | Ruta al MKV/MP4 |
| `season`, `episode` | int | Valores estructurados |
| `episode_label` | string | Ej. `S01-Ep01` (via `core/naming`) |
| `episode_title` | string | Título para columna TSV |
| `subtitle_path` | string | SRT externo, si aplica |
| `subtitle_track_index` | int? | Índice absoluto ffprobe |
| `subtitle_language` | string | Código idioma |
| `audio_track`, `video_track` | int | Índices relativos FFmpeg |
| `padding_start`, `padding_end` | float | Segundos |
| `media_info` | object | Salida resumida de ffprobe |
| `subtitles` | SubtitleCue[] | Bloques de subtítulo |
| `clips` | Clip[] | Clips de estudio |
| `translation` | TranslationConfig | Proveedor e idioma (sin API key) |
| `output_dir` | string | Carpeta de salida |

## SubtitleCue

| Campo | Tipo |
|-------|------|
| `index` | int |
| `start`, `end` | float (segundos) |
| `text` | string |

## Clip

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | int | ID global del clip |
| `internal_index` | int | Orden dentro del episodio |
| `subtitle_indices` | int[] | Subtítulos que componen el clip |
| `text`, `translation` | string | Diálogo original y traducido |
| `start`, `end` | float | Ventana de corte |
| `padding_start`, `padding_end` | float | Margen antes/después |
| `status` | ClipStatus | Ver abajo |
| `video_path`, `audio_path` | string | Rutas de salida |
| `generation_fingerprint` | object | Config usada al generar |
| `error_message` | string | Si status=error |

## Estados (ClipStatus)

| Estado | Significado |
|--------|-------------|
| `pending` | Sin generar |
| `modified` | Editado, no generado o pendiente de regenerar |
| `preview` | Previsualizado (fase posterior) |
| `generated` | Archivos generados con fingerprint actual |
| `outdated` | Generado pero la config cambió |
| `error` | Falló el procesamiento |

### Detección OUTDATED

`Clip.compute_fingerprint()` captura tiempos, padding, texto y parámetros de
encoding. `Clip.is_outdated(current)` compara con la fingerprint guardada en
`generation_fingerprint` cuando `status == generated`.

## TranslationConfig

| Campo | Tipo | Notas |
|-------|------|-------|
| `provider` | string | `none`, `deepl`, `openai`, ... |
| `target_lang` | string | Ej. `ES` |
| `cache_path` | string | Ruta al JSON de caché |

**La API key nunca se guarda en el proyecto.**

## API de persistencia

```python
from persistence import Project, save_project, load_project
from persistence.builders import new_project, clips_from_subtitles

project = new_project(series_name="MySeries", season=1, episode=1)
save_project(project, "MySeries_S01-Ep01.anki-project.json")
project = load_project("MySeries_S01-Ep01.anki-project.json")
```

Escritura atómica: `save_project()` escribe a un archivo temporal y renombra.

## Esquema JSON

`schema_version: 1` en la raíz del documento. Versiones futuras pueden migrar
con funciones en `persistence/store.py`.
