# Pendiente para Windows

Funcionalidad añadida en `debian` que falta por llevar a la rama de Windows. `origin/portability` ya tiene parte del modo película/serie y de otros arreglos. Hay que comparar antes de copiar, para no duplicar lo que esa rama ya hace y para no traer su código de Windows (DLL de mpv, `wasapi`, PowerShell).

La fila de generación en `debian` queda así:

`Serie: [nombre] [Serie|Película] Temporada Episodio`

Temporada y episodio solo se ven en Serie.

## Ya en debian

| Commit | Qué añade | Archivos |
| --- | --- | --- |
| `1c63d33` | Una etiqueta de episodio vacía omite `S01E01` en el clip y en el TSV. | `core/naming.py`, `tests/test_naming.py` |
| `7ac5539` | `media_kind` en el episodio (`movie` o `series`). Un JSON viejo sigue siendo serie. | `persistence/models.py`, `persistence/store.py`, `tests/test_media_kind.py` |
| `9ae8c89` | Detecta serie por `SxxExx` o `Episode N` en el nombre o en el título. Sin patrón, es película. | `persistence/gui_bridge.py`, `tests/test_naming.py` |
| `8eaf29d` | Desplegable Película/Serie y spinboxes de temporada y episodio. Guardar y abrir conservan el modo. | `gui_app.py`, `persistence/gui_bridge.py`, `tests/test_media_kind.py` |
| `4777a41` | Cambiar el modo con clips ya generados pide confirmación. Esos clips conservan su ruta y el TSV existente no cambia de nombre. | `core/naming.py`, `gui_app.py`, `persistence/gui_bridge.py`, `tests/test_media_kind.py` |
| `67f3012` | Una película no lee ni escribe `series_manifest.json`. Una serie sigue usando la carpeta padre del episodio. | `persistence/series_manifest.py`, `gui_app.py`, `tests/test_series_manifest.py` |
| `c40e0d8` | Reconstruye `series_manifest.json` con los mismos dos campos, en dry-run salvo `--apply`. | `tools/rebuild_series_manifest.py`, `tests/test_rebuild_series_manifest.py`, `docs/20-rebuild-series-manifest.md` |
| `02d6cb3` | Tras eliminar, fusionar o dividir, el editor y el bucle de mpv pasan al clip que queda. Si no queda ninguno, los campos se vacían y Probar/Generar se deshabilitan. | `gui_app.py`, `core/segment_selection.py`, `tests/test_segment_selection.py` |
| `1116710` | Lee un SRT en UTF-8 (con o sin BOM), UTF-16 con BOM, Windows-1252 o Latin-1. El parseo de un archivo UTF-8 no cambia. | `core/subtitle_parser.py`, `tests/test_subtitle_encoding.py` |

## Pendiente, todavía no implementado

- Manifiesto de serie dentro de una carpeta llamada `data/` (regla de portability, aún no portada). En `debian` el manifiesto sigue en la carpeta padre del episodio.
- «Cargar externo»: hoy un `.srt` se guarda como texto plano con índices y tiempos mezclados (`gui_reference_map.cue_reference_text`), lo que genera diferencias falsas. Reutilizar `core/subtitle_parser.py` y aceptar un segundo SRT para comparar. Primero el análisis, sin implementarlo todavía.
- Opcional: ofrecer ocultar o filtrar líneas sin audio, del tipo «Captions made possible by...», al abrir un vídeo.
- Escape de campos del TSV con `csv.writer`.
- Paso 7: apartado de nombres película/serie en `docs/04-gui.md` y `docs/changelog.md`.
- Rediseño oscuro de la ventana, con iconos.

Cada commit nuevo de funcionalidad en `debian` debe añadir aquí su hash y sus archivos.
