# Evaluación — cut_clips en Android

**Fecha:** 2026-10-17

## Veredicto

El programa de escritorio no se instala en Android. La ventana está hecha con PySide6 y libmpv, y el corte llama a `ffmpeg` y `ffprobe` del sistema. Android no tiene esa ventana ni esos programas en el `PATH`.

Sí es factible una app nueva que haga el mismo trabajo. El camino elegido es Kotlin y Jetpack Compose, Media3 para ver el vídeo, y un FFmpeg empaquetado para cortar. El parser, los nombres, el JSON y el TSV se reescriben en Kotlin. El escritorio de Windows y Debian se queda como está.

Chaquopy reutilizaría más Python, pero PySide6 y python-mpv no entran, y empaquetar `google-genai` es frágil. Termux puede correr la línea de comandos, pero no es la app.

## Dónde se trabaja

El inventario de lo que hace el escritorio, las consideraciones extra y todas las actividades están en el repositorio nuevo:

`D:\1-Learn\cut_clips_android\docs\PLAN.md`

## Consideraciones que cambian el plan

- El FFmpegKit original se retiró en enero de 2025 y sus binarios salieron de Maven. Hay que usar un fork mantenido o compilar FFmpegKitNext, y comprobar que traiga `libvpx` (VP9) y `libmp3lame`.
- Un MKV de película pesa varios GB. Android lo entrega como URI. FFmpeg necesita poder saltar dentro del archivo sin copiar la película entera.
- Google Play exige librerías nativas alineadas a páginas de 16 KB. El FFmpeg empaquetado tiene que cumplir eso.
- Llevar el TSV a AnkiDroid no es copiar una carpeta: el almacenamiento de otra app está cerrado. Hay que definir cómo el usuario importa el TSV y los medios.
- Un proyecto guardado en Windows trae rutas de Windows. Al abrirlo en el teléfono hay que volver a elegir el vídeo.
- La pausa breve de «Probar clip» en un H.264 también puede aparecer con Media3. No se va a generar un mp4 temporal para quitarla.
