"""QDoubleSpinBox que no cambia de valor con la rueda del ratón sin foco."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()
