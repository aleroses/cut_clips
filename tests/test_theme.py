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


def test_stylesheet_does_not_select_video_widget():
    css = build_stylesheet()
    # Qt 6 descarta la hoja entera si encuentra :not().
    assert ":not(" not in css
    assert "QFrame" not in css
    assert "QOpenGLWidget" not in css
    assert f"#{VIDEO_OBJECT_NAME}" not in css
    assert f"border-radius: {BUTTON_RADIUS}px" in css
