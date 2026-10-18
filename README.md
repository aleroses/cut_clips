# cut_clips

Programa de escritorio para convertir un vídeo con subtítulos en material de estudio para Anki. Funciona en Debian y en Windows. La forma de abrirlo cambia según el sistema; el uso dentro de la ventana es el mismo.

Abres un vídeo, cargas los subtítulos, ajustas cada frase, la escuchas en bucle y generas un clip de vídeo (`.webm`) y otro de audio (`.mp3`). Al final exportas un `.tsv` para importarlo en Anki.

## Qué hace

- Abre `.mkv`, `.mp4` o `.webm` y muestra las pistas de vídeo, audio y subtítulos.
- Si el vídeo trae subtítulos de texto integrados, se extraen desde la ventana y no hace falta un `.srt` externo. Un `.srt` aparte solo hace falta cuando el vídeo no trae pista de texto, o cuando se prefiere ese archivo. Acepta UTF-8, UTF-16, Windows-1252 y Latin-1. Los subtítulos de imagen (PGS, DVD) no se pueden extraer como texto: en ese caso sí hace falta un `.srt`.
- Deja corregir el texto y los tiempos, unir frases, dividirlas, borrarlas y deshacer.
- Previsualiza el tramo elegido en bucle sobre el vídeo original, sin crear un archivo.
- Corta un clip o todos los pendientes. Cada clip sale en `.webm` (vídeo) y `.mp3` (audio), con los mismos tiempos.
- Distingue película y serie. Una película se llama `Nombre_Line_0001`. Una serie se llama `Nombre_S01E01_Line_0001`. El capítulo siguiente de una serie continúa la numeración.
- Traduce con DeepL o Gemini. La clave no se guarda dentro del proyecto.
- Guarda el trabajo en un archivo `.anki-project.json` para retomarlo.
- Exporta un `.tsv` de nueve columnas, listo para Anki, con el texto, la traducción y las referencias `[sound:...]`.

También quedan tres scripts de terminal, por si se prefiere el flujo por archivos: `inspect_media.py`, `parse_srt_preview.py` y `cut_clips.py`. La ventana cubre ese mismo recorrido.

## Qué hace falta

- Python 3
- FFmpeg, con los comandos `ffmpeg` y `ffprobe`
- libmpv, para ver el vídeo dentro de la ventana

Opcional, solo si se va a traducir:

- Una clave de DeepL o de Gemini

Anki (o AnkiDroid) hace falta al importar el `.tsv`, no para generar los clips.

La guía larga de la ventana está en [docs/04-gui.md](docs/04-gui.md).

## Instalar y abrir en Debian

En la carpeta del proyecto:

```bash
cd /ruta/a/cut_clips
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
sudo apt install ffmpeg libmpv2
```

En algunas versiones el paquete se llama `libmpv1` en lugar de `libmpv2`.

Cada vez que se quiera usar el programa, desde esa misma carpeta y con el entorno ya activado:

```bash
python3 gui_app.py
```

Si la terminal es nueva, primero hay que volver a activar el entorno:

```bash
cd /ruta/a/cut_clips
source .venv/bin/activate
python3 gui_app.py
```

El audio de la previsualización usa PulseAudio, PipeWire o ALSA. No hay que definir variables de entorno.

## Instalar y abrir en Windows

Hace falta, aparte de Python 3:

- FFmpeg instalado de forma que `ffmpeg` y `ffprobe` respondan en PowerShell.
- La biblioteca de mpv en `%LOCALAPPDATA%\libmpv`. El archivo debe llamarse `libmpv-2.dll`, `mpv-2.dll` o `mpv-1.dll`. La ventana busca esa carpeta sola. No hay que añadirla al `PATH` en cada terminal.

En PowerShell, en la carpeta del proyecto:

```powershell
Set-Location D:\ruta\cut_clips
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cada vez que se quiera abrir el programa:

```powershell
Set-Location D:\ruta\cut_clips
.\.venv\Scripts\python.exe .\gui_app.py
```

`Set-Location` solo hace falta para la ruta relativa `.\gui_app.py`. Desde cualquier carpeta también vale la ruta completa:

```powershell
D:\ruta\cut_clips\.venv\Scripts\python.exe D:\ruta\cut_clips\gui_app.py
```

Sustituye `D:\ruta\cut_clips` por la carpeta donde está el código. El audio de la previsualización usa WASAPI. No hay que definir `ANKI_MPV_AO` ni tocar el `PATH` en cada sesión. Sí hay que lanzar ese `python.exe` cada vez: no queda un icono instalado.

Si la ventana dice que no encuentra `libmpv-2.dll`, la DLL no está en `%LOCALAPPDATA%\libmpv`.

## Cómo se usa

1. **Archivo → Abrir vídeo…** y elige el `.mkv`, `.mp4` o `.webm`.
2. En el análisis del archivo, elige la pista de audio y, si existe, la de subtítulos. **OK** carga el vídeo. **Cancelar** lo deja como estaba.
3. Si en el paso anterior elegiste una pista de subtítulos de texto, **Archivo → Extraer subtítulos del vídeo…** crea las frases sin un `.srt` externo. Si el vídeo no trae esa pista, o trae solo subtítulos de imagen, usa **Archivo → Abrir subtítulo (.srt)…**. En los dos casos se puede desplazar o recortar el tiempo de todas las frases antes de crearlas.
4. Elige **Película** o **Serie**. En una serie aparecen la temporada y el episodio. Si el nombre del archivo trae `S01E01` o `Episode 2`, el programa propone serie. Si no, propone película. Se puede cambiar a mano.
5. Elige una frase. **Probar clip** la repite entre el inicio y el final. Ajusta los tiempos y pulsa **Aplicar tiempos** para guardarlos en esa frase. El texto se guarda al escribirlo.
6. **Generar clip** crea el `.webm` y el `.mp3` de la frase elegida. **Generar todos pendientes** hace el resto y se puede cancelar.
7. Si quieres traducción, elige DeepL o Gemini, pega la clave y traduce antes de exportar. La clave puede quedar en un archivo de tu usuario (`~/.config/anki_video_tool/`). No entra en el proyecto ni en git.
8. **Archivo → Exportar TSV…** escribe el archivo para Anki. Solo entran los clips ya generados.
9. **Archivo → Guardar proyecto** deja un `.anki-project.json` para seguir otro día. Al volver, **Archivo → Abrir proyecto…**.

Atajos con el foco fuera de un campo de texto: `Espacio` pausa o sigue, `←` y `→` saltan un segundo, `Ctrl+Z` deshace y `Ctrl+Mayús+Z` rehace. `Ctrl+S` guarda el proyecto.

En un vídeo H.264, **Probar clip** puede mostrar una pausa breve al entrar y al repetir. El `.webm` y el `.mp3` generados no tienen esa pausa: el reproductor de la ventana tiene que saltar dentro del archivo original, y los clips ya cortados empiezan en el punto justo.

## Carpeta data

El repositorio incluye una carpeta `data/` vacía. Ahí se puede guardar el vídeo, el `.srt` si se usa uno, y dejar que el programa cree los clips, el proyecto y el TSV, por ejemplo en `data/output_files/`. Trabajar dentro de `data/` no es obligatorio: el programa abre y escribe archivos en cualquier carpeta que elijas.

Si el vídeo de una serie está dentro de `data`, el archivo `series_manifest.json` (el último número de clip, para el capítulo siguiente) se crea dentro de `data`. Una película no crea ese archivo. Git ignora lo que se añada en `data/` (vídeos, subtítulos, clips, proyectos y el manifiesto). Solo se versiona la carpeta vacía, para que exista al clonar el repositorio.

## Línea de comandos

Los tres scripts usan el mismo Python del entorno. En Debian, con el entorno activado, el comando es `python3`. En Windows es `.\.venv\Scripts\python.exe`.

Ver pistas y extraer un subtítulo de texto:

```bash
python3 inspect_media.py "episodio.mkv" --language en
python3 inspect_media.py "episodio.mkv" --extract-subtitle 2 -o episodio.srt
```

El número de `--extract-subtitle` es el índice absoluto que muestra el informe (`abs=N`).

Pasar el `.srt` a un CSV revisable y cortar:

```bash
python3 parse_srt_preview.py episodio.srt -o episodio.csv

python3 cut_clips.py \
  --video episodio.mkv \
  --csv episodio.csv \
  --series-name Nombre_Serie \
  --episode-label S01-Ep01 \
  --media both
```

`--media audio` genera solo `.mp3`. `--media video` genera solo `.webm`. `--limit 5` corta las cinco primeras frases. `--translate` usa DeepL y lee la clave de `DEEPL_API_KEY`. `--start-index` continúa la numeración de un episodio anterior. En la ventana, esa continuación la hace `series_manifest.json` y no hace falta calcular el índice a mano.

## Estructura

```text
.
├── gui_app.py              # Ventana principal
├── cut_clips.py            # Corte y TSV desde un CSV
├── parse_srt_preview.py    # SRT → CSV
├── inspect_media.py        # Pistas y extracción de subtítulos
├── core/                   # Subtítulos, corte, nombres
├── media/                  # ffprobe
├── persistence/            # Proyecto JSON y manifiesto de serie
├── ui/                     # Diálogos y reproductor
├── data/                   # Vacía en git; lugar opcional de trabajo
├── docs/                   # Guías y notas de cada cambio
└── requirements.txt
```

## Más documentación

- Ventana, Debian y Windows: [docs/04-gui.md](docs/04-gui.md)
- Modelo del proyecto: [docs/03-data-model.md](docs/03-data-model.md)
- Subtítulos que no son UTF-8: [docs/13-error-codificacion-srt.md](docs/13-error-codificacion-srt.md)
- Película o serie: [docs/16-reporte-pelicula-o-serie.md](docs/16-reporte-pelicula-o-serie.md)
- Dónde se guarda la numeración de una serie: [docs/17-reporte-manifiesto-serie.md](docs/17-reporte-manifiesto-serie.md)
- Historial: [docs/changelog.md](docs/changelog.md)
