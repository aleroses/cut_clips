# Tareas

Lista viva. Lo tachado ya está hecho. Lo demás sigue pendiente.

## Hechas

- ~~Leer `.srt` en Windows-1252 (byte `0xE8` / `è`) además de UTF-8. Ver [13-error-codificacion-srt.md](13-error-codificacion-srt.md).~~
- ~~En Windows, encontrar `libmpv` en `%LOCALAPPDATA%\libmpv` y usar audio `wasapi` sin definir variables en cada terminal.~~
- ~~Documentar cómo se ejecuta el proyecto en Windows, distinto de Debian. Ver [04-gui.md](04-gui.md) y el README.~~
- ~~Investigar la pausa de «Probar clip» y dejar el plan escrito. Ver [14-plan-pausa-preview.md](14-plan-pausa-preview.md).~~
- ~~Probar un mp4 temporal para quitar la pausa, y revertirlo: cada cambio de tiempos esperaba un encode y el programa podía cerrarse. «Probar clip» vuelve al bucle A–B del MKV original. Ver [15-reporte-preview-sin-pausa.md](15-reporte-preview-sin-pausa.md).~~
- ~~Separar película y serie en el nombre de los archivos. Ver [16-reporte-pelicula-o-serie.md](16-reporte-pelicula-o-serie.md).~~

## Pendientes

- [ ] **Traducciones de Gemini que no aparecen en el TSV.** Hay API key de Gemini y las líneas generadas no muestran la traducción en el TSV. Revisar el flujo: la exportación automática escribe el TSV antes de que termine la traducción en segundo plano y solo reescribe si esa tarea acaba bien; sin proyecto guardado esa exportación automática no corre; el parseo de la respuesta numerada puede dejar la columna vacía; solo entran clips `exported` u `outdated`.
