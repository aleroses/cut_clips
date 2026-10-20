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
SELECTION = "#4B4B6B"
DIFF_BACKGROUND = "#3A3418"
DIFF_TEXT = "#F6E7B2"
DIFF_BORDER = "#E4F34A"
VIDEO_BACKGROUND = "#000000"
BUTTON_RADIUS = 6
BUTTON_GRADIENT_TOP = "#29315A"
BUTTON_GRADIENT_BOTTOM = "#232846"
BUTTON_HOVER_TOP = "#34406F"
BUTTON_HOVER_BOTTOM = "#2B3560"
BUTTON_PRESSED_TOP = "#232846"
BUTTON_PRESSED_BOTTOM = "#1E1E2E"
BUTTON_DISABLED_BG = "#28283C"
BUTTON_PADDING_V = 6
BUTTON_PADDING_H = 14
LOAD_REFERENCE_PADDING_H = 12
COFFEE_TOP = "#FF8A5B"
COFFEE_BOTTOM = "#FF5722"
COFFEE_HOVER_TOP = "#FFA07A"
COFFEE_HOVER_BOTTOM = "#FF6F3C"
COFFEE_PRESSED_TOP = "#E64A19"
COFFEE_PRESSED_BOTTOM = "#D84315"
VIDEO_OBJECT_NAME = "mpvVideo"


def _vertical_gradient(top: str, bottom: str) -> str:
    return (
        f"qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {top}, stop:1 {bottom})"
    )


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
    background-color: {SELECTION};
}}
QPushButton {{
    background: {_vertical_gradient(BUTTON_GRADIENT_TOP, BUTTON_GRADIENT_BOTTOM)};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: {BUTTON_RADIUS}px;
    padding: {BUTTON_PADDING_V}px {BUTTON_PADDING_H}px;
}}
QPushButton:hover {{
    background: {_vertical_gradient(BUTTON_HOVER_TOP, BUTTON_HOVER_BOTTOM)};
    border-color: {PRIMARY};
}}
QPushButton:pressed {{
    background: {_vertical_gradient(BUTTON_PRESSED_TOP, BUTTON_PRESSED_BOTTOM)};
}}
QPushButton:disabled {{
    color: {TEXT_DISABLED};
    background: {BUTTON_DISABLED_BG};
    border-color: {BORDER};
}}
QPushButton#loadReferenceButton {{
    padding: {BUTTON_PADDING_V}px {LOAD_REFERENCE_PADDING_H}px;
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
    border-color: {PRIMARY};
}}
QPushButton#previewButton:pressed,
QPushButton#generateButton:pressed {{
    color: {PRIMARY_PRESSED};
}}
QPushButton#batchGenerateButton {{
    color: {POSITIVE};
}}
QPushButton#batchGenerateButton:hover {{
    color: {POSITIVE_HOVER};
    border-color: {POSITIVE};
}}
QPushButton#batchGenerateButton:pressed {{
    color: {POSITIVE_HOVER};
}}
QPushButton#batchCancelButton,
QPushButton#deleteButton {{
    color: {ATTENTION};
}}
QPushButton#batchCancelButton:hover,
QPushButton#deleteButton:hover {{
    color: {ATTENTION};
    border-color: {ATTENTION};
}}
QPushButton#batchCancelButton:pressed,
QPushButton#deleteButton:pressed {{
    color: {ATTENTION};
}}
QPushButton#previewButton:disabled,
QPushButton#generateButton:disabled,
QPushButton#batchGenerateButton:disabled,
QPushButton#batchCancelButton:disabled,
QPushButton#deleteButton:disabled {{
    color: {TEXT_DISABLED};
    background: {BUTTON_DISABLED_BG};
    border-color: {BORDER};
}}
QGroupBox#previewGroup::title,
QGroupBox#textGroup::title,
QGroupBox#generateGroup::title,
QGroupBox#translateGroup::title,
QGroupBox#cuesGroup::title,
QLabel#sentenceListHeader {{
    font-weight: 600;
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
    """Único botón relleno. El hover cambia el degradado, no el texto."""
    return (
        "QPushButton {"
        f"  background: {_vertical_gradient(COFFEE_TOP, COFFEE_BOTTOM)};"
        f"  color: {WINDOW};"
        "  border: none;"
        f"  border-radius: {BUTTON_RADIUS}px;"
        "  padding: 4px 10px;"
        "  font-size: 12px;"
        "  font-weight: bold;"
        "}"
        "QPushButton:hover {"
        f"  background: {_vertical_gradient(COFFEE_HOVER_TOP, COFFEE_HOVER_BOTTOM)};"
        f"  color: {WINDOW};"
        "}"
        "QPushButton:pressed {"
        f"  background: {_vertical_gradient(COFFEE_PRESSED_TOP, COFFEE_PRESSED_BOTTOM)};"
        f"  color: {WINDOW};"
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
