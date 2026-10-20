"""Marca de preview al cambiar de fila, sin crear una ventana."""

from core.preview_marker import (
    preview_mark_after_delete,
    preview_mark_after_edit,
    preview_mark_after_probe,
    preview_mark_after_select,
    preview_mark_after_stop,
    row_shows_preview_mark,
)


def test_selecting_another_row_keeps_the_preview_mark():
    assert preview_mark_after_select(10) == 10


def test_returning_to_the_row_shows_the_mark():
    preview_id = preview_mark_after_select(10)
    assert row_shows_preview_mark(preview_id, 20) is False
    assert row_shows_preview_mark(preview_id, 10) is True


def test_probing_another_row_moves_the_mark():
    preview_id = preview_mark_after_probe(20)
    assert preview_id == 20
    assert row_shows_preview_mark(preview_id, 10) is False
    assert row_shows_preview_mark(preview_id, 20) is True


def test_stopping_clears_the_mark():
    assert preview_mark_after_stop() is None
    assert row_shows_preview_mark(preview_mark_after_stop(), 10) is False


def test_deleting_the_previewed_row_clears_the_mark():
    assert preview_mark_after_delete(10, 10) is None


def test_deleting_another_row_keeps_the_mark():
    assert preview_mark_after_delete(10, 20) == 10


def test_editing_the_previewed_clip_clears_the_mark_when_bounds_are_gone():
    assert preview_mark_after_edit(10, 10, kept_bounds=False) is None
    assert preview_mark_after_edit(10, 10, kept_bounds=True) == 10


def test_editing_another_clip_keeps_the_mark():
    assert preview_mark_after_edit(10, 20, kept_bounds=False) == 10
