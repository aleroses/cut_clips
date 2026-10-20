"""Paleta oscura y hoja de estilo global.

El vídeo embebido (QFrame nativo en X11 y QOpenGLWidget en Wayland) no entra
en esta hoja. Su fondo negro se aplica con la paleta del propio widget.
Qt 6 rechaza ``:not()`` y, si aparece, descarta la hoja completa; por eso
ningún selector nombra ``QFrame``, ``QOpenGLWidget`` ni ``#mpvVideo``.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPalette
from PySide6.QtWidgets import QStyledItemDelegate

WINDOW = "#1E1E2E"
SURFACE = "#28283C"
ELEVATED = "#29315A"
TEXT = "#F2F0F7"
TEXT_SECONDARY = "#AEA4BF"
TEXT_DISABLED = "#6E6A80"
PRIMARY = "#43CCEA"
PRIMARY_HOVER = "#7FD5EA"
PRIMARY_PRESSED = "#2AA8C8"
POSITIVE = "#42E66C"
POSITIVE_HOVER = "#3EC669"
ATTENTION = "#ff5722"
DANGER = "#E64747"
BORDER = "#3A3A52"
DIFF_BACKGROUND = "#3A3418"
DIFF_TEXT = "#F6E7B2"
DIFF_BORDER = "#E4F34A"
VIDEO_BACKGROUND = "#000000"
BUTTON_RADIUS = 6
VIDEO_OBJECT_NAME = "mpvVideo"


def build_palette() -> QPalette:
    """Paleta Fusion explícita, igual en Debian y en Windows."""
    palette = QPalette()
    window = QColor(WINDOW)
    surface = QColor(SURFACE)
    elevated = QColor(ELEVATED)
    text = QColor(TEXT)
    disabled = QColor(TEXT_DISABLED)
    border = QColor(BORDER)

    roles = {
        QPalette.ColorRole.Window: window,
        QPalette.ColorRole.WindowText: text,
        QPalette.ColorRole.Base: surface,
        QPalette.ColorRole.AlternateBase: elevated,
        QPalette.ColorRole.ToolTipBase: surface,
        QPalette.ColorRole.ToolTipText: text,
        QPalette.ColorRole.Text: text,
        QPalette.ColorRole.Button: elevated,
        QPalette.ColorRole.ButtonText: text,
        QPalette.ColorRole.BrightText: QColor(DANGER),
        QPalette.ColorRole.Highlight: border,
        QPalette.ColorRole.HighlightedText: text,
        QPalette.ColorRole.Link: QColor(PRIMARY),
        QPalette.ColorRole.LinkVisited: QColor(PRIMARY_PRESSED),
        QPalette.ColorRole.PlaceholderText: disabled,
        QPalette.ColorRole.Light: elevated,
        QPalette.ColorRole.Midlight: elevated,
        QPalette.ColorRole.Mid: border,
        QPalette.ColorRole.Dark: border,
        QPalette.ColorRole.Shadow: window,
    }
    for role, color in roles.items():
        palette.setColor(role, color)

    disabled_group = QPalette.ColorGroup.Disabled
    palette.setColor(disabled_group, QPalette.ColorRole.WindowText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Text, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(disabled_group, QPalette.ColorRole.Button, elevated)
    palette.setColor(disabled_group, QPalette.ColorRole.Base, surface)
    palette.setColor(disabled_group, QPalette.ColorRole.Highlight, border)
    palette.setColor(disabled_group, QPalette.ColorRole.HighlightedText, disabled)
    return palette


def build_stylesheet() -> str:
    """QSS global. No selecciona el vídeo embebido."""
    return f"""
QMainWindow,
QDialog,
QScrollArea,
QStatusBar {{
    background-color: {WINDOW};
}}
QDialog,
QStatusBar {{
    color: {TEXT};
}}
QScrollArea {{
    border: none;
}}
QWidget#sidePanel {{
    background-color: {ELEVATED};
}}
QLineEdit,
QPlainTextEdit,
QTextEdit,
QListWidget {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {BUTTON_RADIUS}px;
}}
QLineEdit,
QPlainTextEdit {{
    color: {TEXT};
}}
QListWidget::item:selected,
QListWidget::item:selected:!active {{
    background-color: {BORDER};
}}
QPushButton {{
    background-color: {ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {BUTTON_RADIUS}px;
}}
QPushButton:hover {{
    border-color: {TEXT_SECONDARY};
}}
QPushButton:pressed {{
    background-color: {SURFACE};
}}
QPushButton:disabled {{
    color: {TEXT_DISABLED};
    background-color: {ELEVATED};
    border-color: {BORDER};
}}
QPushButton#previewButton,
QPushButton#generateButton {{
    color: {PRIMARY};
}}
QPushButton#generateButton {{
    font-weight: bold;
}}
QPushButton#previewButton:hover,
QPushButton#generateButton:hover {{
    color: {PRIMARY_HOVER};
}}
QPushButton#previewButton:pressed,
QPushButton#generateButton:pressed {{
    color: {PRIMARY_PRESSED};
}}
QPushButton#batchGenerateButton {{
    color: {POSITIVE};
}}
QPushButton#batchGenerateButton:hover,
QPushButton#batchGenerateButton:pressed {{
    color: {POSITIVE_HOVER};
}}
QPushButton#batchCancelButton,
QPushButton#deleteButton {{
    color: {ATTENTION};
}}
QPushButton#batchCancelButton:hover,
QPushButton#batchCancelButton:pressed,
QPushButton#deleteButton:hover,
QPushButton#deleteButton:pressed {{
    color: {ATTENTION};
    border-color: {ATTENTION};
}}
QPushButton#previewButton:disabled,
QPushButton#generateButton:disabled,
QPushButton#batchGenerateButton:disabled,
QPushButton#batchCancelButton:disabled,
QPushButton#deleteButton:disabled {{
    color: {TEXT_DISABLED};
    border-color: {BORDER};
}}
QMenu {{
    background-color: {SURFACE};
    color: {TEXT};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background-color: {ELEVATED};
}}
"""


def note_style() -> str:
    return f"color: {TEXT_SECONDARY}; font-size: 11px;"


def search_toggle_style() -> str:
    return (
        "QToolButton { border: none; padding: 0 4px; font-size: 13px; }"
        f"QToolButton:checked {{ background-color: {BORDER};"
        f" border-radius: {BUTTON_RADIUS}px; }}"
    )


def search_active_style() -> str:
    return f"QLineEdit {{ border: 1px solid {TEXT_SECONDARY}; }}"


def donation_button_style() -> str:
    """El hover cambia el color, no el texto."""
    return (
        "QPushButton {"
        f"  background-color: {ELEVATED};"
        f"  color: {TEXT};"
        f"  border: 1px solid {BORDER};"
        f"  border-radius: {BUTTON_RADIUS}px;"
        "  padding: 4px 10px;"
        "  font-size: 12px;"
        "}"
        "QPushButton:hover {"
        f"  color: {TEXT_SECONDARY};"
        "}"
        "QPushButton:pressed {"
        f"  color: {TEXT_DISABLED};"
        "}"
    )


def reference_difference_style() -> str:
    return (
        "QPlainTextEdit {"
        f" background-color: {DIFF_BACKGROUND};"
        f" color: {DIFF_TEXT};"
        f" border: 1px solid {DIFF_BORDER};"
        "}"
    )


def fingerprint_difference_style() -> str:
    return (
        "QTextEdit {"
        f" background-color: {DIFF_BACKGROUND};"
        f" color: {DIFF_TEXT};"
        f" border: 1px solid {DIFF_BORDER};"
        " font-size: 11px;"
        "}"
    )


def sentence_foreground(status: str, *, preview: bool) -> str | None:
    """Color de la fila. La preview visible gana sobre el estado guardado."""
    if preview:
        return PRIMARY
    if status == "outdated":
        return ATTENTION
    if status == "exported":
        return POSITIVE
    return None


class StatusColorDelegate(QStyledItemDelegate):
    """La selección conserva el color de estado en lugar de un texto único."""

    def initStyleOption(self, option, index) -> None:
        super().initStyleOption(option, index)
        foreground = index.data(Qt.ItemDataRole.ForegroundRole)
        if foreground is None:
            return
        color = foreground.color() if isinstance(foreground, QBrush) else QColor(foreground)
        if not color.isValid():
            return
        option.palette.setColor(QPalette.ColorRole.Text, color)
        option.palette.setColor(QPalette.ColorRole.HighlightedText, color)


def apply_theme(app) -> None:
    """Fija Fusion, la paleta y el QSS en la aplicación."""
    app.setStyle("Fusion")
    app.setPalette(build_palette())
    app.setStyleSheet(build_stylesheet())


def apply_video_background(widget) -> None:
    """Fondo negro sin QSS, para no romper el embed nativo ni OpenGL."""
    widget.setObjectName(VIDEO_OBJECT_NAME)
    black = QColor(VIDEO_BACKGROUND)
    palette = widget.palette()
    for group in (
        QPalette.ColorGroup.Active,
        QPalette.ColorGroup.Inactive,
        QPalette.ColorGroup.Disabled,
    ):
        palette.setColor(group, QPalette.ColorRole.Window, black)
        palette.setColor(group, QPalette.ColorRole.Base, black)
    widget.setPalette(palette)
    widget.setAutoFillBackground(True)
