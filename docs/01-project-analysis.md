# Análisis del proyecto Anki Video Tool (Fase 0)

Documento generado como parte de la Fase 0 del plan de evolución hacia una
aplicación gráfica de edición de clips para Anki.

## 1. Estructura actual

```text
anki_video_tool/
├── core/
│   ├── clip_engine.py       # Corte, traducción DeepL, TSV Anki
│   └── subtitle_parser.py   # Parseo SRT, agrupación, CSV preview
├── cut_clips.py             # CLI paso 2: CSV + vídeo → clips + TSV
├── parse_srt_preview.py     # CLI paso 1: SRT → CSV preview
├── inspect_media.py         # CLI utilidad: ffprobe + extracción SRT
├── gui_app.py               # GUI PySide6 (prototipo funcional)
├── README.md
├── LICENSE
└── .gitignore
```

No existían (antes de Fase 0/1): `docs/`, `ui/`, `tests/`, `requirements.txt`,
`pyproject.toml`, empaquetado ni CI.

## 2. Propósito de cada archivo

| Archivo | Rol |
|---------|-----|
| `core/subtitle_parser.py` | Parsea SRT, limpia SDH, agrupa oraciones, aplica correcciones de tiempo, escribe CSV preview |
| `core/clip_engine.py` | Padding, jobs FFmpeg (lote/individual), DeepL + caché, TSV Anki |
| `parse_srt_preview.py` | CLI wrapper del parser |
| `cut_clips.py` | CLI wrapper del motor de corte |
| `inspect_media.py` | Análisis ffprobe, clasificación de pistas, extracción SRT |
| `gui_app.py` | Prototipo GUI: mpv, edición tiempos, merge/delete, corte individual, export TSV |

## 3. Flujo actual

### CLI

```text
MKV → inspect_media.py → SRT
SRT → parse_srt_preview.py → CSV (edición manual)
CSV + MKV → cut_clips.py → WebM/MP3 + TSV Anki
```

### GUI (alternativo)

```text
MKV + SRT → gui_app.py → preview mpv → cut_single_clip → TSV
```

El CSV es la fuente de verdad en el flujo CLI. La GUI carga SRT directamente
con `generate_sentences()` y mantiene segmentos en memoria.

## 4. Dependencias

**Sistema:** Python 3, FFmpeg, ffprobe, libmpv (GUI).

**Python:** `deepl` (opcional), `PySide6` (GUI), `python-mpv` (preview GUI).

## 5. Funcionalidades existentes (CLI)

- Análisis multimedia (ffprobe)
- Extracción de subtítulos textuales
- Parseo SRT → CSV editable
- Corte vídeo/audio con padding
- Traducción DeepL con caché JSON
- Numeración continua entre episodios (`--start-index`)
- TSV Anki de 9 campos (formato congelado)
- Procesamiento limitado (`--limit`)
- Skip de archivos existentes (parcial: solo comprueba existencia)

## 6. Funcionalidades parcialmente implementadas

### GUI

Implementado: split-pane, mpv A-B loop, edición start/end, merge/delete,
corte async, export TSV, DeepL opcional.

Ausente: ffprobe integrado, selector de pistas, padding, persistencia,
estados OUTDATED, batch, cancelación, undo, naming consistente con CLI.

## 7. Problemas detectados

### Críticos

1. Skip por existencia de archivo, no por equivalencia de configuración.
2. TSV puede referenciar archivos inexistentes (GUI exporta `pending`).
3. GUI corta valores del segmento, no del spinbox (sin "Aplicar tiempos").
4. Caché DeepL sin clave de idioma destino.

### Importantes

5. Segmentos exportados desaparecen de la lista.
6. Nombres de clip inconsistentes CLI vs GUI.
7. GUI ignora opciones del parser (offset, shift, etc.).
8. Sin selector de pistas en GUI.
9. Traducción bloquea UI en export.
10. TSV sin escaping de tabs/newlines.
11. Solo SRT con coma en milisegundos.
12. Numeración global manual / no persistida.

## 8. Riesgos de modificación

| Riesgo | Mitigación |
|--------|------------|
| Romper formato TSV | Congelar schema; tests snapshot |
| Cambiar nombres de archivo | Centralizar en `core/naming.py` |
| Refactor agresivo | Fases incrementales, sin cambio de comportamiento CLI |
| Duplicar lógica FFmpeg | Capa `media/` compartida |

## 9. Componentes reutilizables

- `core/subtitle_parser.py` — parser y agrupación
- `core/clip_engine.py` — corte, traducción, TSV
- `inspect_media.py` / `media/probe.py` — análisis multimedia
- `gui_app.py` — layout, mpv, CutTask

## 10. Componentes a refactorizar

| Componente | Fase |
|------------|------|
| `translate_texts()` | 13 — TranslationProvider |
| ffprobe en inspect | 1 — `media/probe.py` |
| Estado en gui_app | 2 — modelo persistido |
| Naming disperso | 1 — `core/naming.py` |
| Skip logic | 11 — fingerprint OUTDATED |
| gui_app monolítico | 4–9 — `ui/` |

## 11–13. Arquitectura y fases

Ver [02-current-architecture.md](02-current-architecture.md) y [changelog.md](changelog.md).

La estrategia es incremental: estabilizar (Fase 1), modelo interno JSON (Fase 2),
completar GUI por fases 3–16, tests finales (Fase 17).
