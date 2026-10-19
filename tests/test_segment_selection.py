"""Selección de la línea siguiente tras eliminar un clip."""

from core.segment_selection import next_id_after_removal


def test_delete_first_line_selects_the_next():
    assert next_id_after_removal([10, 20, 30], 10) == 20


def test_delete_middle_line_selects_the_next():
    assert next_id_after_removal([10, 20, 30], 20) == 30


def test_delete_last_line_selects_the_previous():
    assert next_id_after_removal([10, 20, 30], 30) == 20


def test_delete_only_line_selects_nothing():
    assert next_id_after_removal([10], 10) is None
