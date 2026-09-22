"""Historial de deshacer/rehacer para edición de segmentos."""

from __future__ import annotations

import copy
from typing import Any


class EditHistory:
    """Pila undo/redo basada en instantáneas del estado de segmentos."""

    def __init__(self, max_size: int = 50):
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []
        self._max_size = max_size

    def snapshot(self, segments, next_id: int, selected_id: int | None = None) -> dict[str, Any]:
        return {
            "segments": copy.deepcopy(segments),
            "next_id": next_id,
            "selected_id": selected_id,
        }

    def push(self, segments, next_id: int, selected_id: int | None = None):
        self._undo.append(self.snapshot(segments, next_id, selected_id))
        if len(self._undo) > self._max_size:
            self._undo.pop(0)
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def undo(self, segments, next_id: int, selected_id: int | None = None):
        if not self._undo:
            return None
        self._redo.append(self.snapshot(segments, next_id, selected_id))
        return self._undo.pop()

    def redo(self, segments, next_id: int, selected_id: int | None = None):
        if not self._redo:
            return None
        self._undo.append(self.snapshot(segments, next_id, selected_id))
        return self._redo.pop()

    def clear(self):
        self._undo.clear()
        self._redo.clear()
