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
| skip the series manifest for movies | Una película no lee ni escribe `series_manifest.json`. Una serie sigue usando la carpeta padre del episodio. | `persistence/series_manifest.py`, `gui_app.py`, `tests/test_series_manifest.py` |

## Pendiente, todavía no implementado

- Manifiesto de serie dentro de una carpeta llamada `data/`. En `debian` el manifiesto sigue en la carpeta padre del episodio.
- Escape de campos del TSV con `csv.writer`.
- Lectura de SRT en Windows-1252 y UTF-16, además de UTF-8.
- «Cargar externo» con un segundo archivo SRT.
- Rediseño oscuro de la ventana, con iconos.

Cada commit nuevo de funcionalidad en `debian` debe añadir aquí su hash y sus archivos.
