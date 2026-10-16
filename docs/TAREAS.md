# Tareas

Lista viva. Lo tachado ya está hecho. Lo demás sigue pendiente.

## Hechas

- ~~Leer `.srt` en Windows-1252 (byte `0xE8` / `è`) además de UTF-8. Ver [13-error-codificacion-srt.md](13-error-codificacion-srt.md).~~
- ~~En Windows, encontrar `libmpv` en `%LOCALAPPDATA%\libmpv` y usar audio `wasapi` sin definir variables en cada terminal.~~
- ~~Documentar cómo se ejecuta el proyecto en Windows, distinto de Debian. Ver [04-gui.md](04-gui.md) y el README.~~
- ~~Investigar la pausa de «Probar clip» y dejar el plan escrito, sin cambiar todavía la reproducción. Ver [14-plan-pausa-preview.md](14-plan-pausa-preview.md).~~

## Pendientes

- [ ] **Pausa al previsualizar.** Implementar el plan de [14-plan-pausa-preview.md](14-plan-pausa-preview.md) solo después de revisarlo: reproducir un archivo corto (el `.webm` ya generado, o un temporal rápido) en bucle, en lugar de saltar dentro del MKV con A–B.
- [ ] **Película frente a serie en el nombre del archivo.** Los clips de Ratatouille salen como `Ratatouille_S01E01_Line_0001.webm` y `.mp3` en `data/output_files`. El vídeo no tiene temporada ni episodio; temporada 1 y episodio 1 son el valor por defecto cuando el nombre no trae `SxxExx` (`parse_season_episode` y `_file_episode_label()`). Hace falta un modo película, sin `S01E01` en el nombre, y un modo serie que sí lo lleve. El TSV usa la misma etiqueta.
- [ ] **Traducciones de Gemini que no aparecen en el TSV.** Hay API key de Gemini y las líneas generadas no muestran la traducción en el TSV. Revisar el flujo: la exportación automática escribe el TSV antes de que termine la traducción en segundo plano y solo reescribe si esa tarea acaba bien; sin proyecto guardado esa exportación automática no corre; el parseo de la respuesta numerada puede dejar la columna vacía; solo entran clips `exported` u `outdated`.
