# Reconstruir series_manifest.json

El manifiesto solo guarda dos campos: `last_sequence_number` y `series_name`. Vive en la carpeta de la serie, que es el directorio padre de cada episodio. Un valor 546 hace que el episodio siguiente, sin clips propios, empiece en `Line_0547`.

La herramienta elige esa carpeta con la misma regla que la ventana. En `data/Serie/SxxExx` el archivo queda en `Serie`. Si la carpeta del episodio se llama `data`, o si su padre es la raíz del proyecto, el archivo se queda dentro del episodio. Nunca se escribe en la raíz del proyecto. Una película no usa este archivo.

La herramienta usa la misma escritura que la ventana, así que el archivo queda con el mismo formato. No añade temporada ni episodio. Por defecto no escribe: muestra el JSON. Solo crea el archivo con `--apply`. Si ya existe, no lo toca salvo `--force`, y en ese caso deja antes `series_manifest.json.bak`.

El escaneo mira `output_files/` de cada capítulo. Se queda con el capítulo más alto que tenga clips `Nombre_SxxExx_Line_NNNN.webm` o `.mp3`, y con el `Line_` mayor de ese capítulo. Una carpeta `S01E04` sin esos archivos no cuenta. `--last-season` y `--last-episode` limitan el escaneo y no se guardan en el JSON. `--last-line` es el respaldo si ese capítulo no tiene clips. Sin clips y sin `--last-line`, el programa se detiene y no inventa un número.

Desde la raíz del proyecto:

```bash
python3 tools/rebuild_series_manifest.py --series-dir /ruta/Spawn_S01 --series-name Todd_McFarlanes_Spawn
python3 tools/rebuild_series_manifest.py --series-dir /ruta/Spawn_S01 --series-name Todd_McFarlanes_Spawn --last-season 1 --last-episode 3 --apply
python3 -c 'import json; print(json.load(open("/ruta/Spawn_S01/series_manifest.json", encoding="utf-8")))'
```

La salida esperada es `last_sequence_number` 546 y `series_name` `Todd_McFarlanes_Spawn` cuando el último clip terminado es `Todd_McFarlanes_Spawn_S01E03_Line_0546.webm`.
