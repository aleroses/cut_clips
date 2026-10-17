# Informe de cierre — cut_clips

**Fecha:** 2026-10-17

Este repositorio es el programa de escritorio. No quedan tareas abiertas. El trabajo de Android sigue en `D:\1-Learn\cut_clips_android`.

## Ya está en el remoto

La rama `portability` está en `origin/portability` hasta el commit `06ae92d` (*Skip the series manifest for movies and keep it inside data*).

Eso incluye lo hecho en esta etapa:

- Lectura de `.srt` en Windows-1252, además de UTF-8.
- Arranque en Windows sin variables de entorno en cada terminal (`libmpv` y audio WASAPI).
- «Probar clip» otra vez sobre el MKV original. El mp4 temporal se probó y se quitó.
- Nombres de película sin `S01E01`, y de serie con `SxxExx`.
- `series_manifest.json` solo para series, y dentro de `data` cuando el vídeo está en esa carpeta.
- Carpeta `data/` vacía en el repositorio. Usarla es opcional.

## Solo en esta máquina, y entra en el commit de cierre

- [18-evaluacion-android.md](18-evaluacion-android.md): el escritorio no se lleva a Android. La app nueva va en Kotlin.
- [TAREAS.md](TAREAS.md): esa evaluación queda hecha. No hay pendientes.
- [changelog.md](changelog.md): la misma nota.

## En esta máquina y no se sube

Está en `.gitignore` a propósito. No es código pendiente.

- `data/`: el MKV de Ratatouille, el `.srt`, el proyecto JSON, el TSV, los clips de `output_files/` y la caché de traducciones.
- `.venv/`, `__pycache__/`, `.pytest_cache/`.
- `questions.md`.

## Dónde seguir

`D:\1-Learn\cut_clips_android` ya tiene el inventario del escritorio y las actividades, de la fase 0 a la 11, en `docs/PLAN.md`. El commit local es `7493bcc`. Ese repositorio todavía no tiene remoto.

Se puede dejar `cut_clips` como está y trabajar solo en `cut_clips_android`.
