#!/usr/bin/env python3
"""
gui_app.py

Fase 2 del pipeline Anki-Video: interfaz gráfica para revisar, fusionar,
eliminar y ajustar los tiempos de cada oración, y cortar los clips sin
tener que editar el CSV a mano.

Requiere:
    sudo apt install libmpv2   # (o libmpv1, según tu versión de Debian)
    pip install PySide6 python-mpv --break-system-packages

Uso:
    python3 gui_app.py

Flujo:
    1. Archivo > Abrir vídeo... (mkv/mp4/webm)
    2. Archivo > Abrir subtítulo... (srt) — o extrae uno con inspect_media.py primero
    3. La lista de la derecha se llena con las oraciones agrupadas
    4. Seleccionas una línea -> se previsualiza en el panel izquierdo
    5. Ajustas Start/End si hace falta, das "Cortar" para exportar esa línea
    6. Al terminar todo el episodio: Archivo > Exportar TSV...

Notas de diseño:
    - La previsualización NO corta nada: carga el vídeo original una sola
      vez y usa el "A-B loop" nativo de mpv (ab-loop-a/ab-loop-b) para
      reproducir en bucle solo el segmento seleccionado. Cortar con ffmpeg
      solo ocurre al presionar "Cortar".
    - El corte corre en un hilo aparte (QThreadPool) para no congelar la UI.
    - "Fusionar con siguiente" une el texto y extiende el end al de la
      siguiente línea, igual que hacía la agrupación automática por oración.
    - Al exportar, se reescribe el TSV completo con las líneas restantes.
    - La traducción con DeepL es OPCIONAL: si no ingresas una API key, el
      TSV se exporta igual, solo que con la columna de traducción vacía.
"""

import os
import sys

from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QDoubleSpinBox,
    QFileDialog, QMessageBox, QFrame, QSplitter, QStatusBar, QGroupBox,
    QLineEdit, QCheckBox,
)

from core.subtitle_parser import generate_sentences
from core.clip_engine import (
    cut_single_clip, write_anki_tsv, detect_video_title,
    extract_episode_title, translate_texts,
)

try:
    import mpv
except (ImportError, OSError):
    mpv = None


# ---------------------------------------------------------------------------
# Corte en segundo plano
# ---------------------------------------------------------------------------

class CutSignals(QObject):
    finished = Signal(int, bool, str)  # segment_id, success, message


class CutTask(QRunnable):
    def __init__(self, segment_id, video_path, start, end, output_path, media,
                 audio_track=0, video_track=0):
        super().__init__()
        self.segment_id = segment_id
        self.video_path = video_path
        self.start = start
        self.end = end
        self.output_path = output_path
        self.media = media
        self.audio_track = audio_track
        self.video_track = video_track
        self.signals = CutSignals()

    def run(self):
        try:
            ok, err = cut_single_clip(
                self.video_path, self.start, self.end, self.output_path,
                media=self.media, audio_track=self.audio_track, video_track=self.video_track,
            )
            self.signals.finished.emit(self.segment_id, ok, err if not ok else "")
        except Exception as e:
            self.signals.finished.emit(self.segment_id, False, str(e))


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anki Video Tool — Editor de clips")
        self.resize(1100, 650)

        self.video_path = None
        self.episode_title = ""
        self.segments = []  # lista de dicts: {id, start, end, text, status}
        self.next_id = 1
        self.player = None  # instancia de mpv.MPV

        self.thread_pool = QThreadPool()

        self._build_ui()
        self._build_menu()

    # -- UI ---------------------------------------------------------------

    def _build_menu(self):
        menu = self.menuBar().addMenu("Archivo")
        menu.addAction("Abrir vídeo...", self.open_video)
        menu.addAction("Abrir subtítulo (.srt)...", self.open_subtitle)
        menu.addSeparator()
        menu.addAction("Exportar TSV...", self.export_tsv)

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        # --- Panel izquierdo: previsualización + edición fina ---
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.video_frame = QFrame()
        self.video_frame.setStyleSheet("background-color: black;")
        self.video_frame.setMinimumHeight(300)
        left_layout.addWidget(self.video_frame)

        controls = QHBoxLayout()
        self.play_btn = QPushButton("▶ Reproducir")
        self.play_btn.clicked.connect(self.play_selected_segment)
        self.stop_btn = QPushButton("■ Detener")
        self.stop_btn.clicked.connect(self.stop_preview)
        controls.addWidget(self.play_btn)
        controls.addWidget(self.stop_btn)
        left_layout.addLayout(controls)

        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Start:"))
        self.start_spin = QDoubleSpinBox()
        self.start_spin.setDecimals(3)
        self.start_spin.setRange(0, 99999)
        self.start_spin.setSingleStep(0.1)
        time_layout.addWidget(self.start_spin)

        start_minus = QPushButton("-100ms")
        start_minus.clicked.connect(lambda: self._nudge(self.start_spin, -0.1))
        start_plus = QPushButton("+100ms")
        start_plus.clicked.connect(lambda: self._nudge(self.start_spin, 0.1))
        time_layout.addWidget(start_minus)
        time_layout.addWidget(start_plus)
        left_layout.addLayout(time_layout)

        end_layout = QHBoxLayout()
        end_layout.addWidget(QLabel("End:  "))
        self.end_spin = QDoubleSpinBox()
        self.end_spin.setDecimals(3)
        self.end_spin.setRange(0, 99999)
        self.end_spin.setSingleStep(0.1)
        end_layout.addWidget(self.end_spin)

        end_minus = QPushButton("-100ms")
        end_minus.clicked.connect(lambda: self._nudge(self.end_spin, -0.1))
        end_plus = QPushButton("+100ms")
        end_plus.clicked.connect(lambda: self._nudge(self.end_spin, 0.1))
        end_layout.addWidget(end_minus)
        end_layout.addWidget(end_plus)
        left_layout.addLayout(end_layout)

        apply_btn = QPushButton("Aplicar tiempos a la línea seleccionada")
        apply_btn.clicked.connect(self.apply_times_to_selected)
        left_layout.addWidget(apply_btn)

        cut_btn = QPushButton("✂ Cortar (vídeo + audio)")
        cut_btn.setStyleSheet("font-weight: bold;")
        cut_btn.clicked.connect(self.cut_selected_segment)
        left_layout.addWidget(cut_btn)

        # --- Traducción opcional (DeepL) ---
        translate_group = QGroupBox("Traducción (opcional)")
        translate_layout = QVBoxLayout(translate_group)

        self.translate_checkbox = QCheckBox("Traducir con DeepL al exportar el TSV")
        translate_layout.addWidget(self.translate_checkbox)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API key:"))
        self.deepl_key_edit = QLineEdit()
        self.deepl_key_edit.setEchoMode(QLineEdit.Password)
        self.deepl_key_edit.setPlaceholderText(
            "Opcional — o deja vacío y usa la variable de entorno DEEPL_API_KEY"
        )
        env_key = os.environ.get("DEEPL_API_KEY")
        if env_key:
            self.deepl_key_edit.setText(env_key)
        key_row.addWidget(self.deepl_key_edit)
        translate_layout.addLayout(key_row)

        left_layout.addWidget(translate_group)

        left_layout.addStretch()
        splitter.addWidget(left)

        # --- Panel derecho: lista dinámica de trabajo ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Oraciones pendientes:"))

        self.segment_list = QListWidget()
        self.segment_list.currentRowChanged.connect(self.on_segment_selected)
        right_layout.addWidget(self.segment_list)

        list_controls = QHBoxLayout()
        merge_btn = QPushButton("Fusionar con siguiente")
        merge_btn.clicked.connect(self.merge_with_next)
        delete_btn = QPushButton("Eliminar")
        delete_btn.clicked.connect(self.delete_selected)
        list_controls.addWidget(merge_btn)
        list_controls.addWidget(delete_btn)
        right_layout.addLayout(list_controls)

        splitter.addWidget(right)
        splitter.setSizes([650, 450])

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Abre un vídeo y un subtítulo para empezar.")

    # -- Carga de archivos --------------------------------------------------

    def open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir vídeo", "", "Vídeo (*.mkv *.mp4 *.webm);;Todos (*.*)"
        )
        if not path:
            return
        self.video_path = path
        self.episode_title = extract_episode_title(detect_video_title(path)) or ""

        if mpv is not None:
            if self.player is not None:
                self.player.terminate()
            self.player = mpv.MPV(
                wid=str(int(self.video_frame.winId())),
                vo="gpu",
                keep_open=True,
                idle=True,
                osc=False,
                input_default_bindings=False,
                input_vo_keyboard=False,
            )
            self.player.play(path)
            # Da tiempo a que mpv cargue el archivo antes de pausarlo, para
            # no arrancar reproduciendo el episodio completo de una.
            QTimer.singleShot(300, lambda: setattr(self.player, "pause", True))
        else:
            QMessageBox.warning(
                self, "python-mpv no disponible",
                "No se pudo cargar 'mpv' (revisa que libmpv esté instalado:\n"
                "  sudo apt install libmpv2\n"
                "  pip install python-mpv --break-system-packages\n\n"
                "Podrás seguir editando tiempos y cortando, pero sin previsualización."
            )

        self.statusBar().showMessage(f"Vídeo cargado: {os.path.basename(path)}"
                                      + (f'  |  Título: "{self.episode_title}"' if self.episode_title else ""))

    def open_subtitle(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir subtítulo", "", "Subtítulos (*.srt);;Todos (*.*)"
        )
        if not path:
            return

        result = generate_sentences(path)
        self.segments = []
        for s in result["sentences"]:
            self.segments.append({
                "id": self.next_id,
                "start": s["start"],
                "end": s["end"],
                "text": s["text"],
                "status": "pending",
            })
            self.next_id += 1

        self._refresh_list()
        self.statusBar().showMessage(
            f"{len(self.segments)} oraciones cargadas "
            f"({result['discarded_blocks']} descartadas, solo efectos de sonido)."
        )

    # -- Lista de segmentos --------------------------------------------------

    def _refresh_list(self):
        self.segment_list.clear()
        for seg in self.segments:
            if seg["status"] != "pending":
                continue
            label = f"[{seg['start']:.3f} - {seg['end']:.3f}]  {seg['text'][:60]}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, seg["id"])
            self.segment_list.addItem(item)

    def _pending_segments(self):
        return [s for s in self.segments if s["status"] == "pending"]

    def _get_selected_segment(self):
        item = self.segment_list.currentItem()
        if item is None:
            return None
        seg_id = item.data(Qt.UserRole)
        for seg in self.segments:
            if seg["id"] == seg_id:
                return seg
        return None

    def on_segment_selected(self, row):
        seg = self._get_selected_segment()
        if seg is None:
            return
        self.start_spin.setValue(seg["start"])
        self.end_spin.setValue(seg["end"])

    def apply_times_to_selected(self):
        seg = self._get_selected_segment()
        if seg is None:
            return
        new_start, new_end = self.start_spin.value(), self.end_spin.value()
        if new_end <= new_start:
            QMessageBox.warning(self, "Tiempos inválidos", "End debe ser mayor que Start.")
            return
        seg["start"], seg["end"] = new_start, new_end
        self._refresh_list()
        self.statusBar().showMessage(f"Tiempos actualizados para la línea id={seg['id']}.")

    def merge_with_next(self):
        seg = self._get_selected_segment()
        if seg is None:
            return
        pending = self._pending_segments()
        idx = next((i for i, s in enumerate(pending) if s["id"] == seg["id"]), None)
        if idx is None or idx + 1 >= len(pending):
            QMessageBox.information(self, "No se puede fusionar", "No hay una línea siguiente para fusionar.")
            return
        nxt = pending[idx + 1]
        seg["text"] = f"{seg['text']} {nxt['text']}"
        seg["end"] = nxt["end"]
        nxt["status"] = "deleted"  # se elimina de la lista, ya fue absorbida
        self._refresh_list()

    def delete_selected(self):
        seg = self._get_selected_segment()
        if seg is None:
            return
        seg["status"] = "deleted"
        self._refresh_list()

    # -- Previsualización (VLC, sin cortar nada) ----------------------------

    def play_selected_segment(self):
        if self.player is None or self.video_path is None:
            QMessageBox.warning(self, "Sin vídeo", "Primero abre un vídeo (y ten python-mpv instalado).")
            return
        start = self.start_spin.value()
        end = self.end_spin.value()
        if end <= start:
            return

        # A-B loop nativo de mpv: reproduce en bucle solo [start, end],
        # sin necesitar un timer externo que sondee la posición.
        self.player.command("seek", start, "absolute")
        self.player.ab_loop_a = start
        self.player.ab_loop_b = end
        self.player.pause = False

    def stop_preview(self):
        if self.player is not None:
            self.player.pause = True
            self.player.ab_loop_a = "no"
            self.player.ab_loop_b = "no"

    def _nudge(self, spinbox, delta):
        spinbox.setValue(max(0.0, spinbox.value() + delta))

    # -- Corte ---------------------------------------------------------------

    def cut_selected_segment(self):
        seg = self._get_selected_segment()
        if seg is None or self.video_path is None:
            QMessageBox.warning(self, "Falta información", "Selecciona una línea y abre un vídeo primero.")
            return

        output_dir = os.path.join(os.path.dirname(self.video_path), "output_files")
        os.makedirs(output_dir, exist_ok=True)
        base_name = f"clip_Line_{seg['id']:04d}"
        output_path = os.path.join(output_dir, base_name)

        seg["status"] = "cutting"
        self._refresh_list()
        self.statusBar().showMessage(f"Cortando línea id={seg['id']}...")

        task = CutTask(seg["id"], self.video_path, seg["start"], seg["end"], output_path, media="both")
        task.signals.finished.connect(self._on_cut_finished)
        self.thread_pool.start(task)

    def _on_cut_finished(self, segment_id, success, message):
        for seg in self.segments:
            if seg["id"] == segment_id:
                if success:
                    seg["status"] = "exported"
                    self.statusBar().showMessage(f"Línea id={segment_id} exportada correctamente.")
                else:
                    seg["status"] = "pending"
                    QMessageBox.critical(self, "Error al cortar", message[-800:])
                break
        self._refresh_list()

    # -- Exportar TSV ---------------------------------------------------------

    def export_tsv(self):
        if not self.segments:
            QMessageBox.information(self, "Nada que exportar", "No hay oraciones cargadas.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exportar TSV", "", "TSV (*.tsv)")
        if not path:
            return

        tsv_rows = []
        for seg in self.segments:
            if seg["status"] not in ("pending", "exported"):
                continue
            video_filename = f"clip_Line_{seg['id']:04d}.webm"
            audio_filename = f"clip_Line_{seg['id']:04d}.mp3"
            tsv_rows.append((seg["id"], seg["text"], video_filename, audio_filename,
                              "", self.episode_title))

        translations = {}
        if self.translate_checkbox.isChecked():
            api_key = self.deepl_key_edit.text().strip()
            if not api_key:
                QMessageBox.warning(
                    self, "Falta la API key",
                    "Marcaste traducir con DeepL pero no ingresaste una API key.\n"
                    "El TSV se exportará sin traducción."
                )
            else:
                cache_path = os.path.join(os.path.dirname(path), "translations_cache.json")
                all_texts = [text for _, text, _, _, _, _ in tsv_rows]
                try:
                    translations = translate_texts(all_texts, api_key, "ES", cache_path)
                except Exception as e:
                    QMessageBox.critical(self, "Error de traducción", str(e))

        write_anki_tsv(path, tsv_rows, translations)
        QMessageBox.information(self, "Exportado", f"TSV guardado en:\n{path}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()