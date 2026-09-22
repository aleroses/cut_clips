"""Opciones compartidas para embeber libmpv en Qt (Capa 1 wid y Capa 2 OpenGL)."""

from __future__ import annotations

import os


def configure_mpv_environment():
    """Reduce ruido no fatal de PipeWire/Pulse antes de crear mpv."""
    os.environ.setdefault("PIPEWIRE_LOG", "0")
    os.environ.setdefault("PULSE_LOG", "0")


def mpv_hwdec_option() -> str:
    """Decodificación segura: evita CUDA/NVDEC si no hay drivers NVIDIA."""
    return os.environ.get("ANKI_MPV_HWDEC", "auto-safe")


def mpv_ao_option() -> str:
    """Orden de drivers de audio; evita 'auto' que falla en algunos entornos Linux."""
    return os.environ.get("ANKI_MPV_AO", "pulse,pipewire,alsa")


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
