"""Opciones compartidas para embeber libmpv en Qt (Capa 1 wid y Capa 2 OpenGL)."""

from __future__ import annotations

import os


_added_dll_dirs = []


def prepare_mpv_library_path():
    """En Windows, añade %LOCALAPPDATA%\\libmpv al PATH antes de importar mpv.

    python-mpv busca mpv-2.dll / libmpv-2.dll con ctypes al importarse.
    Hay que llamar a esta función antes de ``import mpv``.
    """
    if os.name != "nt":
        return
    local = os.environ.get("LOCALAPPDATA", "")
    if not local:
        return
    lib_dir = os.path.join(local, "libmpv")
    names = ("mpv-2.dll", "libmpv-2.dll", "mpv-1.dll")
    if not any(os.path.isfile(os.path.join(lib_dir, name)) for name in names):
        return
    path = os.environ.get("PATH", "")
    entries = [entry for entry in path.split(os.pathsep) if entry]
    if lib_dir not in entries:
        os.environ["PATH"] = lib_dir + os.pathsep + path
    if hasattr(os, "add_dll_directory"):
        _added_dll_dirs.append(os.add_dll_directory(lib_dir))


def configure_mpv_environment():
    """Reduce ruido no fatal de PipeWire/Pulse antes de crear mpv."""
    os.environ.setdefault("PIPEWIRE_LOG", "0")
    os.environ.setdefault("PULSE_LOG", "0")


def mpv_hwdec_option() -> str:
    """Decodificación segura: evita CUDA/NVDEC si no hay drivers NVIDIA."""
    return os.environ.get("ANKI_MPV_HWDEC", "auto-safe")


def mpv_ao_option() -> str:
    """Driver de audio. En Windows el default de Linux (pulse) no existe."""
    if os.name == "nt":
        default = "wasapi"
    else:
        default = "pulse,pipewire,alsa"
    return os.environ.get("ANKI_MPV_AO", default)


def mpv_player_kwargs(*, vo: str, wid: str | None = None, log_handler=None) -> dict:
    """Opciones comunes de mpv.MPV para preview embebido en la GUI."""
    kwargs = {
        "vo": vo,
        "hwdec": mpv_hwdec_option(),
        "ao": mpv_ao_option(),
        "keep_open": True,
        "idle": True,
        "osc": False,
        "input_default_bindings": False,
        "input_vo_keyboard": False,
    }
    if wid is not None:
        kwargs["wid"] = wid
    if log_handler is not None:
        kwargs["log_handler"] = log_handler
    return kwargs
