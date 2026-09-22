"""Diálogo de análisis multimedia (ffprobe) y selección de pistas."""

from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from media.probe import (
    classify_streams,
    get_format_info,
    language_matches,
    subtitle_kind_label,
    suggest_tracks,
)


@dataclass
class TrackSelection:
    video_track: int = 0
    audio_track: int = 0
    subtitle_track_index: int | None = None
    subtitle_language: str = "en"


def _format_bitrate(bitrate):
    if not bitrate:
        return "—"
    try:
        kbps = int(bitrate) / 1000
        return f"{kbps:.0f} kbps"
    except (TypeError, ValueError):
        return str(bitrate)


def _video_summary_lines(video_streams) -> list[str]:
    lines = []
    for v in video_streams:
        br = _format_bitrate(v.get("bitrate"))
        lines.append(
            f"[video_track={v.get('relative_index', 0)}] "
            f"{v['codec_name']}  {v['resolution']}  "
            f"{v.get('fps', '?')} fps  {br}"
        )
    return lines


def _audio_label(a) -> str:
    title = f'  título="{a["title"]}"' if a.get("title") else ""
    return (
        f"[audio_track={a['relative_index']}, abs={a['index']}] "
        f"{a['codec_name']}  idioma={a['language']}  "
        f"canales={a['channels']}  {a.get('sample_rate', '?')} Hz{title}"
    )


def _subtitle_label(s) -> str:
    kind = subtitle_kind_label(s)
    title = f'  título="{s["title"]}"' if s.get("title") else ""
    return f"[abs={s['index']}] {s['codec_name']}  idioma={s['language']}  → {kind}{title}"


class MediaInfoDialog(QDialog):
    """Muestra información ffprobe y permite elegir pistas de audio/vídeo/subtítulos."""

    def __init__(self, video_path: str, probe_data: dict, parent=None, language: str = "en"):
        super().__init__(parent)
        self.video_path = video_path
        self.probe_data = probe_data
        self.video_streams, self.audio_streams, self.subtitle_streams = classify_streams(probe_data)
        self.format_info = get_format_info(probe_data)
        self._language = language

        self.setWindowTitle("Análisis del archivo multimedia")
        self.setMinimumWidth(620)
        self._build_ui()
        self._apply_language_filter()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(
            f"<b>{os.path.basename(self.video_path)}</b><br>"
            f"Duración: {self.format_info['duration_min']:.1f} min"
            + (f"  |  Título: {self.format_info['title']}" if self.format_info.get("title") else "")
            + (f"  |  Bitrate: {_format_bitrate(self.format_info.get('bitrate'))}"
               if self.format_info.get("bitrate") else "")
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        video_group = QGroupBox("Vídeo")
        video_layout = QVBoxLayout(video_group)
        self.video_detail = QPlainTextEdit()
        self.video_detail.setReadOnly(True)
        self.video_detail.setMaximumHeight(90)
        self.video_detail.setPlainText("\n".join(_video_summary_lines(self.video_streams)) or "(sin pista de vídeo)")
        video_layout.addWidget(self.video_detail)

        self.video_combo = QComboBox()
        if len(self.video_streams) > 1:
            for v in self.video_streams:
                self.video_combo.addItem(
                    f"video_track {v['relative_index']}: {v['codec_name']} {v['resolution']}",
                    v["relative_index"],
                )
            video_layout.addWidget(QLabel("Pista de vídeo para cortar:"))
            video_layout.addWidget(self.video_combo)
        else:
            self.video_combo.hide()
        layout.addWidget(video_group)

        audio_group = QGroupBox("Audio")
        audio_layout = QVBoxLayout(audio_group)
        if self.audio_streams:
            self.audio_combo = QComboBox()
            for a in self.audio_streams:
                self.audio_combo.addItem(_audio_label(a), a["relative_index"])
            audio_layout.addWidget(QLabel("Pista de audio para los clips:"))
            audio_layout.addWidget(self.audio_combo)
        else:
            self.audio_combo = None
            audio_layout.addWidget(QLabel("(ninguna pista de audio)"))
        layout.addWidget(audio_group)

        sub_group = QGroupBox("Subtítulos")
        sub_layout = QVBoxLayout(sub_group)
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Filtrar por idioma:"))
        self.language_edit = QLineEdit(self._language)
        self.language_edit.setPlaceholderText("en, es, fr…")
        self.language_edit.setMaximumWidth(80)
        self.language_edit.editingFinished.connect(self._apply_language_filter)
        lang_row.addWidget(self.language_edit)
        lang_row.addStretch()
        sub_layout.addLayout(lang_row)

        if self.subtitle_streams:
            self.subtitle_combo = QComboBox()
            self.subtitle_combo.addItem("(Ninguno — usar archivo .srt externo)", None)
            for s in self.subtitle_streams:
                self.subtitle_combo.addItem(_subtitle_label(s), s["index"])
            sub_layout.addWidget(QLabel("Pista de subtítulos embebida:"))
            sub_layout.addWidget(self.subtitle_combo)
            self.subtitle_combo.currentIndexChanged.connect(self._update_subtitle_warning)
        else:
            self.subtitle_combo = None
            sub_layout.addWidget(
                QLabel("No hay pistas de subtítulos en el contenedor.\n"
                       "Usa Archivo → Abrir subtítulo (.srt) con un archivo externo.")
            )

        self.subtitle_warning = QLabel()
        self.subtitle_warning.setWordWrap(True)
        self.subtitle_warning.setStyleSheet("color: #a60;")
        sub_layout.addWidget(self.subtitle_warning)
        layout.addWidget(sub_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_language_filter(self):
        self._language = self.language_edit.text().strip() or "en"
        suggested = suggest_tracks(
            self.video_streams, self.audio_streams, self.subtitle_streams, self._language
        )

        if self.video_streams and len(self.video_streams) > 1:
            idx = self.video_combo.findData(suggested["video_track"])
            if idx >= 0:
                self.video_combo.setCurrentIndex(idx)

        if self.audio_combo is not None:
            idx = self.audio_combo.findData(suggested["audio_track"])
            if idx >= 0:
                self.audio_combo.setCurrentIndex(idx)

        if self.subtitle_combo is not None:
            sub_idx = suggested["subtitle_track_index"]
            if sub_idx is not None:
                idx = self.subtitle_combo.findData(sub_idx)
                if idx >= 0:
                    self.subtitle_combo.setCurrentIndex(idx)

        self._update_subtitle_warning()

    def _update_subtitle_warning(self):
        if self.subtitle_combo is None:
            self.subtitle_warning.clear()
            return
        data = self.subtitle_combo.currentData()
        if data is None:
            self.subtitle_warning.setText("")
            return
        sub = next((s for s in self.subtitle_streams if s["index"] == data), None)
        if sub is None:
            self.subtitle_warning.setText("")
            return
        if sub.get("is_image"):
            self.subtitle_warning.setText(
                "La pista seleccionada es gráfica (PGS/VobSub) y no puede convertirse "
                "directamente a texto editable. Necesitarías un .srt de otra fuente."
            )
        elif not sub.get("is_text"):
            self.subtitle_warning.setText(
                f"Formato de subtítulo no reconocido como texto ({sub['codec_name']})."
            )
        elif not language_matches(sub["language"], self._language):
            self.subtitle_warning.setText(
                f"El idioma de la pista ({sub['language']}) no coincide con "
                f"'{self._language}'. Revisa que sea la pista correcta."
            )
        else:
            self.subtitle_warning.setText("")

    def _on_accept(self):
        if self.subtitle_combo is not None:
            data = self.subtitle_combo.currentData()
            if data is not None:
                sub = next((s for s in self.subtitle_streams if s["index"] == data), None)
                if sub and sub.get("is_image"):
                    reply = QMessageBox.warning(
                        self,
                        "Subtítulos gráficos",
                        "La pista seleccionada es gráfica y no se puede editar como texto.\n"
                        "¿Continuar de todos modos? (Podrás usar un .srt externo.)",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    if reply != QMessageBox.Yes:
                        return
        self.accept()

    def selection(self) -> TrackSelection:
        video_track = 0
        if self.video_streams:
            if len(self.video_streams) > 1:
                video_track = int(self.video_combo.currentData())
            else:
                video_track = self.video_streams[0].get("relative_index", 0)

        audio_track = 0
        if self.audio_combo is not None:
            audio_track = int(self.audio_combo.currentData())

        subtitle_index = None
        if self.subtitle_combo is not None:
            subtitle_index = self.subtitle_combo.currentData()

        return TrackSelection(
            video_track=video_track,
            audio_track=audio_track,
            subtitle_track_index=subtitle_index,
            subtitle_language=self._language,
        )
