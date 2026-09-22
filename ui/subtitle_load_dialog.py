"""Diálogo para cargar subtítulos con opciones de parseo."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

from ui.parser_options_widget import ParserOptions, ParserOptionsPanel


class SubtitleLoadDialog(QDialog):
    """Muestra opciones de parseo antes de cargar un SRT (archivo o extraído)."""

    def __init__(
        self,
        parent=None,
        *,
        srt_path: str,
        source_label: str = "",
        options: ParserOptions | None = None,
    ):
        super().__init__(parent)
        self.srt_path = srt_path
        self.setWindowTitle("Cargar subtítulos")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        if source_label:
            layout.addWidget(QLabel(f"<b>Origen:</b> {source_label}"))
        layout.addWidget(QLabel(f"<b>Archivo:</b> {os.path.basename(srt_path)}"))

        self.options_panel = ParserOptionsPanel(options=options)
        layout.addWidget(self.options_panel)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> ParserOptions:
        return self.options_panel.options()
