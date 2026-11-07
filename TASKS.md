# Tareas pendientes

Lista de funciones nuevas. No forman parte del comportamiento actual.

## Reglas

- No cambiar funciones ni características que ya funcionan.
- No modificar código que ya hace su trabajo, salvo el punto de entrada mínimo para abrir una pestaña nueva.
- El diseño de cada pestaña está por ver. Se pueden proponer opciones, pero no se implementa un diseño hasta que se autorice.
- Se pueden añadir más tareas aquí. Por ahora solo estas tres.

## Pestañas

La ventana tendrá pestañas para no mezclar estas herramientas con el editor actual:

1. **Editor** — la interfaz clásica, tal como está ahora.
2. **yt-dlp** — descarga desde un enlace.
3. **Whisper** — generar subtítulos cuando los existentes no sirven.

## Tareas

### 1. Cortar audio con un SRT

Poder abrir un audio (podcast u otro archivo solo de audio) junto con su `.srt` y cortar por los tiempos elegidos.

- Genera un `.mp3` con el tramo cortado.
- Genera un `.tsv` que se subira en Anki.
- Genera todo lo que genera cuando se trabaja con videos pero sin el clip `.webm`.
- No genera clip de vídeo.
- El resto del flujo (revisar tiempos, cortar, exportar) debe poder usarse igual que con un vídeo, limitado a audio.

Hoy la interfaz abre vídeo y, al generar, escribe `.webm` y `.mp3`. El corte solo de audio existe en la línea de comandos (`cut_clips.py --media audio`), no como flujo de la interfaz.

### 2. Descargar con yt-dlp

En la pestaña de yt-dlp, pegar un enlace de YouTube y descargar el vídeo con su `.srt`.

- Al terminar, poder pasar ese archivo al editor como vídeo para cortar.
- Valorar también pasarlo como audio, si el material se va a cortar solo en `.mp3`.

### 3. Subtítulos con Whisper

En la pestaña de Whisper, generar subtítulos cuando los que vienen con el archivo no están bien y hace falta otra opción.

- El resultado debe poder usarse como el `.srt` del editor.
- La herramienta concreta (Whisper u otra) y dónde queda el archivo generado se deciden con el diseño de esa pestaña.
