"""Carga de iconos, con QtSvg y sin él. No abre una ventana."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui import icons  # noqa: E402
from ui.icons import ICON_SIZE, ICONS_DIR, load_icon, qtsvg_available  # noqa: E402


def test_icons_dir_is_relative_to_the_module():
    module_dir = Path(icons.__file__).resolve().parent
    assert ICONS_DIR == module_dir.parent / "assets" / "icons"
    for name in ("play", "repeat", "pause", "save", "zap", "search", "x", "coffee"):
        assert (ICONS_DIR / f"{name}.svg").is_file()
    assert (ICONS_DIR / "LICENSE").is_file()


def test_load_icon_without_qtsvg(monkeypatch):
    monkeypatch.setattr(icons, "qtsvg_available", lambda: False)
    assert (
        load_icon("play", normal="#F2F0F7", hover="#AEA4BF", disabled="#6E6A80")
        is None
    )


def test_load_icon_with_qtsvg():
    pytest.importorskip("PySide6.QtSvg")
    assert qtsvg_available()
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    icon = load_icon("coffee", normal="#F2F0F7", hover="#43CCEA", disabled="#6E6A80")
    assert icon is not None
    assert not icon.isNull()
    samples = {
        mode: _opaque_colors(icon, mode)
        for mode in (QIcon.Mode.Normal, QIcon.Mode.Active, QIcon.Mode.Disabled)
    }
    assert all(samples.values())
    assert samples[QIcon.Mode.Normal] != samples[QIcon.Mode.Disabled]
    assert samples[QIcon.Mode.Normal] != samples[QIcon.Mode.Active]


def test_missing_icon_returns_none():
    pytest.importorskip("PySide6.QtSvg")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    assert (
        load_icon("missing", normal="#F2F0F7", hover="#F2F0F7", disabled="#6E6A80")
        is None
    )


def _opaque_colors(icon, mode) -> list[tuple[int, int, int]]:
    from PySide6.QtGui import QIcon
    image = icon.pixmap(ICON_SIZE, ICON_SIZE, mode, QIcon.State.Off).toImage()
    colors = []
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() > 128:
                colors.append((color.red(), color.green(), color.blue()))
    return colors
