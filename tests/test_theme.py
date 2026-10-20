"""Paleta y hoja de estilo, sin crear una ventana."""

from ui.theme import (
    ATTENTION,
    BORDER,
    BUTTON_RADIUS,
    DANGER,
    DIFF_BACKGROUND,
    DIFF_BORDER,
    DIFF_TEXT,
    ELEVATED,
    POSITIVE,
    POSITIVE_HOVER,
    PRIMARY,
    PRIMARY_HOVER,
    PRIMARY_PRESSED,
    SURFACE,
    TEXT,
    TEXT_DISABLED,
    TEXT_SECONDARY,
    VIDEO_BACKGROUND,
    VIDEO_OBJECT_NAME,
    WINDOW,
    build_palette,
    build_stylesheet,
)


def test_palette_constants():
    assert WINDOW == "#1E1E2E"
    assert SURFACE == "#28283C"
    assert ELEVATED == "#29315A"
    assert TEXT == "#F2F0F7"
    assert TEXT_SECONDARY == "#AEA4BF"
    assert TEXT_DISABLED == "#6E6A80"
    assert PRIMARY == "#43CCEA"
    assert PRIMARY_HOVER == "#7FD5EA"
    assert PRIMARY_PRESSED == "#2AA8C8"
    assert POSITIVE == "#42E66C"
    assert POSITIVE_HOVER == "#3EC669"
    assert ATTENTION == "#ff5722"
    assert DANGER == "#E64747"
    assert BORDER == "#3A3A52"
    assert DIFF_BACKGROUND == "#3A3418"
    assert DIFF_TEXT == "#F6E7B2"
    assert DIFF_BORDER == "#E4F34A"
    assert VIDEO_BACKGROUND == "#000000"
    assert BUTTON_RADIUS == 6
    assert VIDEO_OBJECT_NAME == "mpvVideo"


def test_palette_uses_explicit_window_and_danger():
    palette = build_palette()
    window = palette.color(palette.ColorRole.Window).name()
    danger = palette.color(palette.ColorRole.BrightText).name()
    assert window == WINDOW.lower()
    assert danger == DANGER.lower()


def test_sentence_foreground_keeps_the_current_priority():
    from ui.theme import sentence_foreground

    assert sentence_foreground("exported", preview=True) == PRIMARY
    assert sentence_foreground("outdated", preview=True) == PRIMARY
    assert sentence_foreground("outdated", preview=False) == ATTENTION
    assert sentence_foreground("exported", preview=False) == POSITIVE
    assert sentence_foreground("pending", preview=False) is None
    assert sentence_foreground("preview", preview=False) is None


def test_selected_row_keeps_its_status_color():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QStyleOptionViewItem

    from ui.theme import POSITIVE, StatusColorDelegate

    QApplication.instance() or QApplication([])
    widget = QListWidget()
    delegate = StatusColorDelegate(widget)
    widget.setItemDelegate(delegate)
    item = QListWidgetItem("[✓] exportada")
    item.setForeground(QColor(POSITIVE))
    widget.addItem(item)
    option = QStyleOptionViewItem()
    delegate.initStyleOption(option, widget.model().index(0, 0))
    painted = option.palette.color(option.palette.ColorRole.HighlightedText).name()
    assert painted == POSITIVE.lower()


def test_side_panel_styles_use_the_palette():
    from ui.theme import (
        donation_button_style,
        fingerprint_difference_style,
        note_style,
        reference_difference_style,
        search_active_style,
        search_toggle_style,
    )

    note = note_style()
    assert TEXT_SECONDARY in note
    assert "11px" in note
    assert TEXT_SECONDARY in search_active_style()
    assert BORDER in search_toggle_style()
    donation = donation_button_style()
    assert ELEVATED in donation
    assert TEXT in donation
    assert "QPushButton:hover" in donation
    reference = reference_difference_style()
    fingerprint = fingerprint_difference_style()
    for style in (reference, fingerprint):
        assert DIFF_BACKGROUND in style
        assert DIFF_TEXT in style
        assert DIFF_BORDER in style


def test_stylesheet_does_not_select_video_widget():
    css = build_stylesheet()
    # Qt 6 descarta la hoja entera si encuentra :not().
    assert ":not(" not in css
    assert "QFrame" not in css
    assert "QOpenGLWidget" not in css
    assert f"#{VIDEO_OBJECT_NAME}" not in css
    assert f"border-radius: {BUTTON_RADIUS}px" in css
