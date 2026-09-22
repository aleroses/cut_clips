"""Diálogo para dividir un clip en un límite entre bloques SRT."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)


def suggest_split_after_index(
    cue_indices: list,
    cue_map: dict,
    playhead_pos: float | None,
) -> int:
    """Índice del bloque tras el cual dividir (0 … len-2)."""
    if len(cue_indices) < 2:
        return 0
    max_idx = len(cue_indices) - 2
    if playhead_pos is None:
        return min((len(cue_indices) - 1) // 2, max_idx)
    best = 0
    for i, idx in enumerate(cue_indices[:-1]):
        cue = cue_map.get(idx)
        if cue is not None and cue["start"] <= playhead_pos:
            best = i
    return min(best, max_idx)


class SrtSplitDialog(QDialog):
    """Elige el bloque SRT tras el cual cortar el clip."""

    def __init__(
        self,
        parent=None,
        *,
        cue_indices: list,
        cue_map: dict,
        playhead_pos: float | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Dividir clip por bloque SRT")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "El clip se dividirá en dos en un límite entre bloques SRT. "
                "Los tiempos Start/End se ajustarán a los bloques incluidos."
            )
        )

        self._combo = QComboBox()
        for i in range(len(cue_indices) - 1):
            idx = cue_indices[i]
            cue = cue_map.get(idx, {})
            start = cue.get("start", 0.0)
            end = cue.get("end", 0.0)
            text = cue.get("text", "")[:55]
            label = f"Dividir después de #{idx + 1}  [{start:.3f} – {end:.3f}]  {text}"
            self._combo.addItem(label, i)

        default = suggest_split_after_index(cue_indices, cue_map, playhead_pos)
        self._combo.setCurrentIndex(default)
        layout.addWidget(self._combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def split_after_index(self) -> int:
        return int(self._combo.currentData())
