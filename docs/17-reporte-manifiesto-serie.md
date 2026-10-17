# Reporte — manifiesto de serie y carpeta data

**Fecha:** 2026-10-17

## Película

`series_manifest.json` guarda el último número de clip para que el capítulo siguiente continúe en `Line_XXXX`. Una película no tiene capítulo siguiente, así que no se crea ni se lee ese archivo. Los clips de la película empiezan en `Line_0001`.

## Serie dentro de data

Si el vídeo está en la carpeta `data`, el manifiesto se escribe ahí, por ejemplo `data/series_manifest.json`. Antes, al estar el vídeo dentro de `data`, el programa subía un nivel y lo dejaba en la raíz del proyecto.

Si la serie no está dentro de una carpeta llamada `data`, el manifiesto sigue en la carpeta padre del episodio, como hasta ahora.

El `series_manifest.json` que ya exista en la raíz del proyecto no se borra solo. Se puede eliminar a mano.

## Carpeta data

El repositorio trae `data/` vacía para quien clone el código. Usarla es opcional: ahí se pueden dejar el vídeo, los subtítulos y los clips generados. Git no versiona ese contenido.

## Cómo probarlo

```powershell
Set-Location D:\1-Learn\cut_clips
.\.venv\Scripts\python.exe .\gui_app.py
```

1. Abre un vídeo de `data` con el desplegable en Película y genera un clip. No debe aparecer un `series_manifest.json` nuevo.
2. Abre un vídeo de serie dentro de `data` y genera un clip. El manifiesto debe estar en `data`, no en la raíz del proyecto.
