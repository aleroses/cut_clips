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
| `40fa329` | Limpia etiquetas, anotaciones SDH, anuncios y mayúsculas del texto de un subtítulo. | `core/subtitle_text.py`, `tests/test_subtitle_text.py` |
| `4742cfb` | Lee un SRT externo a bloques con inicio, fin y texto limpio, en UTF-8 o Windows-1252. | `core/subtitle_text.py`, `tests/test_reference_cues.py` |
| `e92bad7` | El texto de referencia de un clip es el de los bloques que solapan su intervalo, con 0.5 s de tolerancia. | `core/subtitle_text.py`, `tests/test_reference_cues.py` |
| `a7605e6` | El mismo botón acepta un .srt. La caja muestra el texto del intervalo del clip y un proyecto viejo abre sin ese campo. | `gui_app.py`, `persistence/gui_bridge.py`, `tests/test_reference_cues.py` |
| `a8f6005` | Las diferencias se calculan sobre el texto limpio, así que anotaciones como reporter o screams no cuentan. | `core/subtitle_text.py`, `gui_app.py`, `tests/test_reference_cues.py` |
| `aabf500` | Recorta el texto de referencia al diálogo del clip, por palabras. | `core/subtitle_parser.py`, `core/subtitle_text.py`, `tests/test_reference_cues.py` |
| `04efaba` | La caja de referencia usa ese recorte y se actualiza al editar el texto. | `gui_app.py` |
| `3e40dba` | Las diferencias se calculan contra el texto recortado. Mayúsculas, puntuación y anotaciones SDH no cuentan. | `core/subtitle_text.py`, `gui_app.py`, `tests/test_reference_cues.py` |
| `63eb0b0` | Guarda la ruta del SRT externo y, al abrir, lo relee si sigue en disco. | `core/subtitle_text.py`, `gui_app.py`, `persistence/gui_bridge.py`, `tests/test_reference_cues.py` |
| `936e18a` | Documenta el desplegable Película/Serie, los nombres de clip y TSV, el manifiesto y que Cargar externo acepta .txt, .md y .srt. | `docs/04-gui.md`, `docs/changelog.md` |
| `TBD-theme-1` | Tema oscuro: paleta, estilo Fusion y hoja global. El vídeo embebido queda fuera del QSS, solo con fondo negro. | `ui/theme.py`, `gui_app.py`, `tests/test_theme.py` |
| `TBD-theme-2` | Iconos Lucide y un helper que arma el QIcon en normal, hover y deshabilitado. Sin QtSvg la app arranca y el botón se queda en texto. | `assets/icons/`, `ui/icons.py`, `tests/test_icons.py` |

## Pendiente, todavía no implementado

- Manifiesto de serie dentro de una carpeta llamada `data/` (regla de portability, aún no portada). En `debian` el manifiesto sigue en la carpeta padre del episodio.
- Opcional: ofrecer ocultar o filtrar líneas sin audio, del tipo «Captions made possible by...», al abrir un vídeo.
- Escape de campos del TSV con `csv.writer`.
- Rediseño oscuro de la ventana, con iconos.

Cada commit nuevo de funcionalidad en `debian` debe añadir aquí su hash y sus archivos.
