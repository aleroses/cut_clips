# Por qué falla al añadir un .srt y cómo arrancar la app en Windows

**Fecha:** 2026-10-16

Este documento explica el mensaje que aparece al usar **Archivo → Abrir subtítulo (.srt)** con archivos como el de *Ratatouille*, y qué comandos hacen falta para abrir el programa en PowerShell.

## El mensaje

```text
No se pudo procesar el archivo:

'UTF-8' codec can't decode byte 0xe8 in position 7448: invalid continuation byte.
```

El segundo archivo falló igual, solo cambió el número de posición (`7374` en vez de `7448`).

## A qué se debe

La aplicación abría el `.srt` obligando la codificación **UTF-8**. Esos archivos no están en UTF-8.

El byte `0xe8` (232 en decimal) en la codificación **Windows-1252** —la que Windows llama a menudo ANSI, y la de muchos subtítulos de BDRip y fansubs— es la letra **è**. En UTF-8, ese mismo byte no es una letra: es el comienzo de un carácter de tres bytes. El byte siguiente no continúa la secuencia, y Python se detiene con `invalid continuation byte`.

El trozo que se ve al principio del archivo (*Subs Sync Checked*, *Although each of the world's countries*, *Chef Auguste Gusteau*) es ASCII puro y se leería bien. El byte problemático está más adelante, cerca del byte 7400: alguna `è` (o un carácter equivalente) guardada en Windows-1252. Por eso los dos `.srt` dan el mismo tipo de error con posiciones parecidas: los dos están guardados en la misma codificación, no es un fallo del texto que se pega en el chat.

No hace falta convertir el archivo a mano. Al cargarlo, el programa prueba en este orden:

1. UTF-8, con o sin BOM.
2. UTF-16, si el archivo empieza con BOM de UTF-16.
3. Windows-1252 (`cp1252`), que es el caso de estos `.srt`.
4. Latin-1, que acepta cualquier byte si las anteriores fallan.

Si la codificación no es UTF-8, la barra de estado lo indica, por ejemplo: `Codificación: cp1252.`

## Cómo probarlo

Desde la raíz del proyecto, con el entorno virtual:

```powershell
Set-Location D:\1-Learn\cut_clips
.\.venv\Scripts\python.exe .\gui_app.py
```

Luego **Archivo → Abrir subtítulo (.srt)** y elige el mismo archivo de *Ratatouille*. Tiene que cargar las oraciones en lugar de mostrar el error de UTF-8.

Prueba automática del mismo caso (un `.srt` con el byte `0xe8`):

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_subtitle_encoding.py
```

## ¿Hay que repetir todos los comandos de PowerShell?

No. Estos dos solo valían para **esa ventana** de PowerShell. Al cerrarla, se pierden:

```powershell
$env:PATH = "$env:LOCALAPPDATA\libmpv;$env:PATH"
$env:ANKI_MPV_AO = "wasapi"
```

- `PATH` hacía falta porque `python-mpv` busca `libmpv-2.dll` al importarse, y esa DLL está en `%LOCALAPPDATA%\libmpv`. La aplicación ahora añade esa carpeta sola, antes de importar mpv, si encuentra `libmpv-2.dll`, `mpv-2.dll` o `mpv-1.dll`.
- `ANKI_MPV_AO = wasapi` hacía falta porque el valor por defecto era el de Linux (`pulse,pipewire,alsa`). En Windows el valor por defecto pasa a ser `wasapi`.

`Set-Location` solo sirve para que la ruta relativa `.\gui_app.py` exista. Desde otra carpeta también vale:

```powershell
D:\1-Learn\cut_clips\.venv\Scripts\python.exe D:\1-Learn\cut_clips\gui_app.py
```

Cada vez que quieras usar el programa hay que **lanzarlo** (el `python.exe ... gui_app.py`). No hace falta volver a definir `PATH` ni `ANKI_MPV_AO` en cada terminal.

Si en el futuro la DLL de mpv no está en `%LOCALAPPDATA%\libmpv`, entonces sí habría que añadir su carpeta al `PATH` de esa sesión, o mover la DLL a `%LOCALAPPDATA%\libmpv`.
