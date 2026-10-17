# Reporte — película o serie en el nombre del archivo

**Fecha:** 2026-10-16

## Cómo se elige

En el panel de generación, al lado del nombre de los archivos, hay un desplegable **Película / Serie**.

Al abrir un vídeo:

- Si el nombre del archivo o el título trae `S02E04` o `Episode 12`, queda en **Serie** y se rellenan temporada y episodio. Esos números se pueden corregir.
- Si no trae eso, queda en **Película**. Temporada y episodio no se muestran y no entran en el nombre.

Se puede cambiar el desplegable a mano. La elección se guarda en el proyecto (`media_kind`). Un proyecto antiguo que no tenga ese dato sigue como serie, para no cambiar nombres que ya eran `S01E01`.

Los archivos ya generados, como `Ratatouille_S01E01_Line_0001.webm`, no se renombran solos. Al generar de nuevo, con el desplegable en Película, salen con el nombre nuevo.

## Nombres

| Tipo | Clip | TSV | Columna de episodio |
| --- | --- | --- | --- |
| Serie | `Show_S02E04_Line_0001.webm` y `.mp3` | `Show_S02E04_anki.tsv` | `S02E04` |
| Película | `Ratatouille_Line_0001.webm` y `.mp3` | `Ratatouille_anki.tsv` | vacía |

Si la película tiene título de episodio en el programa, el TSV puede ser `Ratatouille_Titulo_anki.tsv`. El clip sigue sin `S01E01`.

## Cómo probarlo

```powershell
Set-Location D:\1-Learn\cut_clips
.\.venv\Scripts\python.exe .\gui_app.py
```

1. Abre un archivo cuyo nombre tenga `S02E04`. El desplegable debe decir Serie, temporada 2, episodio 4.
2. Abre `Ratatouille (2007).mkv`. El desplegable debe decir Película. Pon el nombre `Ratatouille` si quieres ese prefijo.
3. Genera un clip. El archivo debe llamarse `Ratatouille_Line_0001.webm`, no `Ratatouille_S01E01_Line_0001.webm`.

## Sigue pendiente

Las traducciones de Gemini que no aparecen en el TSV. La lista está en [TAREAS.md](TAREAS.md).
