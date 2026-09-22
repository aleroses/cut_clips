"""Opciones del parser de subtítulos (equivalente a parse_srt_preview.py)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


@dataclass
class ParserOptions:
    offset: float = 0.0
    scale: float = 1.0
    trim_start: float = 0.0
    trim_end: float = 0.0
    shift: float = 0.0
    min_duration: float = 0.0
    min_words: int = 0
    language: str = "en"

    def as_generate_kwargs(self) -> dict:
        return {
            "offset": self.offset,
            "scale": self.scale,
            "trim_start": self.trim_start,
            "trim_end": self.trim_end,
            "shift": self.shift,
            "min_duration": self.min_duration,
            "min_words": self.min_words,
            "language": self.language,
        }


class ParserOptionsWidget(QGroupBox):
    """Widget reutilizable con los parámetros de generate_sentences()."""

    def __init__(self, parent=None, options: ParserOptions | None = None):
        super().__init__("Opciones de parseo", parent)
        opts = options or ParserOptions()
        self._build_ui(opts)

    def _build_ui(self, opts: ParserOptions):
        layout = QFormLayout(self)

        self.language_edit = QLineEdit(opts.language)
        self.language_edit.setPlaceholderText("en, es, fr, de, ja…")
        layout.addRow("Idioma:", self.language_edit)

        self.offset_spin = self._float_spin(opts.offset, -999, 999, 0.05)
        layout.addRow("Offset (s):", self.offset_spin)

        self.scale_spin = self._float_spin(opts.scale, 0.01, 10.0, 0.001, decimals=4)
        layout.addRow("Scale:", self.scale_spin)

        self.shift_spin = self._float_spin(opts.shift, -999, 999, 0.05)
        layout.addRow("Shift (s):", self.shift_spin)

        self.trim_start_spin = self._float_spin(opts.trim_start, 0, 60, 0.05)
        layout.addRow("Trim inicio (s):", self.trim_start_spin)

        self.trim_end_spin = self._float_spin(opts.trim_end, 0, 60, 0.05)
        layout.addRow("Trim final (s):", self.trim_end_spin)

        self.min_duration_spin = self._float_spin(opts.min_duration, 0, 60, 0.1)
        layout.addRow("Duración mín. (s):", self.min_duration_spin)

        self.min_words_spin = QSpinBox()
        self.min_words_spin.setRange(0, 100)
        self.min_words_spin.setValue(opts.min_words)
        layout.addRow("Palabras mín.:", self.min_words_spin)

    @staticmethod
    def _float_spin(value, min_v, max_v, step, decimals=3):
        spin = QDoubleSpinBox()
        spin.setDecimals(decimals)
        spin.setRange(min_v, max_v)
        spin.setSingleStep(step)
        spin.setValue(value)
        return spin

    def options(self) -> ParserOptions:
        return ParserOptions(
            offset=self.offset_spin.value(),
            scale=self.scale_spin.value(),
            trim_start=self.trim_start_spin.value(),
            trim_end=self.trim_end_spin.value(),
            shift=self.shift_spin.value(),
            min_duration=self.min_duration_spin.value(),
            min_words=self.min_words_spin.value(),
            language=self.language_edit.text().strip() or "en",
        )

    def set_language(self, language: str):
        self.language_edit.setText(language)


class ParserOptionsPanel(QWidget):
    """Panel compacto para incrustar en un diálogo."""

    def __init__(self, parent=None, options: ParserOptions | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.widget = ParserOptionsWidget(options=options)
        layout.addWidget(self.widget)

    def options(self) -> ParserOptions:
        return self.widget.options()

    def set_language(self, language: str):
        self.widget.set_language(language)
