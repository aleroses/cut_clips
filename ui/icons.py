"""Iconos Lucide pintados por estado. Sin QtSvg el botón se queda en texto."""

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap

ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
ICON_SIZE = 16


def qtsvg_available() -> bool:
    try:
        from PySide6 import QtSvg  # noqa: F401
    except ImportError:
        return False
    return True


def load_icon(
    name: str,
    *,
    normal: str,
    hover: str,
    disabled: str,
    size: int = ICON_SIZE,
) -> QIcon | None:
    """QIcon con pixmaps normal, hover y deshabilitado. None si no hay QtSvg."""
    if not qtsvg_available():
        return None
    path = ICONS_DIR / f"{name}.svg"
    if not path.is_file():
        return None
    source = path.read_text(encoding="utf-8")
    if "currentColor" not in source:
        return None
    icon = QIcon()
    for mode, color in (
        (QIcon.Mode.Normal, normal),
        (QIcon.Mode.Active, hover),
        (QIcon.Mode.Disabled, disabled),
    ):
        pixmap = _render(source, color, size)
        if pixmap is None:
            return None
        icon.addPixmap(pixmap, mode, QIcon.State.Off)
    return icon


def _render(source: str, color: str, size: int) -> QPixmap | None:
    from PySide6.QtSvg import QSvgRenderer

    colored = source.replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(colored.encode("utf-8")))
    if not renderer.isValid():
        return None
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
