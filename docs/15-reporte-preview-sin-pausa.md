# Reporte — «Probar clip» otra vez sobre el vídeo original

**Fecha:** 2026-10-16

## Qué pasó con el mp4

«Probar clip» llegó a crear un mp4 temporal y a cambiar el archivo abierto en mpv. Al mover Start/End y volver a probar, cada tramo distinto esperaba un encode. Eso se sentía más lento que la pausa anterior, y en algún momento el programa se cerró: el reproductor embebido descargaba el MKV, abría el mp4 y, al cambiar de línea, volvía a cargar el MKV.

Ese camino ya no está. **Probar clip** no crea ningún mp4. El MKV original sigue cargado y mpv salta al inicio del tramo y, al llegar al final, salta otra vez al inicio (`ab-loop-a` / `ab-loop-b`).

**Generar clip** no cambió: sigue escribiendo el `.webm` y el `.mp3` en `output_files`.

## Por qué queda la pausa

En un H.264, mpv no puede caer en un segundo cualquiera al instante. Tiene que decodificar desde el fotograma clave anterior. Esa espera es la pausa al empezar y, otra vez, al repetir el bucle. El `.webm` exportado no la tiene porque ya empieza en el primer fotograma del clip.

No hay un ajuste de mpv que quite esa espera y a la vez empiece en el segundo exacto, sin un archivo ya recortado. Un salto al fotograma clave sería inmediato, pero sonaría diálogo de antes del corte. Acelerar el salto solo la acorta un poco. Por eso se dejó el comportamiento anterior: suena al momento, con esa pausa breve, y sin esperar a ffmpeg.

El audio no se tocó. En Debian sigue `pulse,pipewire,alsa`. En Windows sigue `wasapi`.

## Cómo probarlo

```powershell
Set-Location D:\1-Learn\cut_clips
.\.venv\Scripts\python.exe .\gui_app.py
```

1. Abre el MKV, carga el `.srt` y elige una línea.
2. Cambia Start o End y pulsa **Probar clip** varias veces.
3. Tiene que sonar enseguida. No debe aparecer «Preparando la escucha del clip…».
4. Puede seguir habiendo una pausa breve al entrar en el tramo y al volver a empezar el bucle.
5. El programa no debe cerrarse al repetir esa prueba.
6. No debe aparecer un mp4 nuevo en `output_files`.

## Sigue pendiente

La lista está en [TAREAS.md](TAREAS.md): nombres de película sin `S01E01`, y las traducciones de Gemini que no aparecen en el TSV.
