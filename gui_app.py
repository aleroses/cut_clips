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
    1. Archivo > Abrir vídeo... (mkv/mp4/webm) — diálogo ffprobe de pistas
    2. Archivo > Abrir subtítulo (.srt)... — con opciones de parseo
       o Archivo > Extraer subtítulos del vídeo... — desde pista embebida
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
from dataclasses import replace

from PySide6.QtCore import Qt, QRunnable, QThreadPool, Signal, QObject, QTimer
from PySide6.QtGui import QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel, QDoubleSpinBox,
    QFileDialog, QMessageBox, QFrame, QSplitter, QStatusBar, QGroupBox,
    QLineEdit, QCheckBox, QDialog, QSpinBox, QAbstractSpinBox, QPlainTextEdit,
    QProgressBar, QScrollArea,
)

from core.subtitle_parser import generate_sentences, normalize_case, parse_srt_blocks
from core.clip_engine import (
    cut_single_clip, write_anki_tsv, detect_video_title,
    extract_episode_title, translate_texts, compute_padded_window,
    sanitize_filename_component, run_batch, BatchCancelToken, MIN_DURATION,
)
from core.naming import clip_audio_filename, clip_video_filename, format_episode_label
from media.probe import (
    probe, summarize_media, extract_subtitle, find_subtitle_stream,
    find_sidecar_subtitle, subtitle_extract_path,
)
from ui.media_info_dialog import MediaInfoDialog
from ui.mpv_embed import configure_mpv_environment, mpv_player_kwargs
from ui.parser_options_widget import ParserOptions
from ui.subtitle_load_dialog import SubtitleLoadDialog
from ui.srt_split_dialog import SrtSplitDialog
from ui.undo_stack import EditHistory
from persistence.gui_bridge import (
    apply_outdated_status,
    build_project_from_gui,
    build_segment_fingerprint,
    clip_output_paths,
    guess_series_name,
    load_gui_state_from_project,
    parse_season_episode,
)
from persistence.store import default_project_path, load_project, save_project

try:
    import mpv
except (ImportError, OSError):
    mpv = None


def _ensure_mpv_numeric_locale():
    """libmpv exige LC_NUMERIC=C; Qt lo cambia al crear QApplication."""
    import locale
    locale.setlocale(locale.LC_NUMERIC, "C")


def _configure_qt_platform_for_mpv():
    """Wayland + XWayland: forzar xcb para que wid embeba mpv en el QFrame."""
    if os.environ.get("ANKI_FORCE_MPV_GL", "").lower() in ("1", "true", "yes"):
        return
    if os.environ.get("QT_QPA_PLATFORM"):
        return
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland" and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def _should_use_opengl_embed() -> bool:
    """Capa 2: Render API cuando wid no es viable (Wayland nativo sin XWayland)."""
    if os.environ.get("ANKI_FORCE_MPV_GL", "").lower() in ("1", "true", "yes"):
        return True
    if os.environ.get("ANKI_FORCE_MPV_WID", "").lower() in ("1", "true", "yes"):
        return False
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland" and not os.environ.get("DISPLAY"):
        return True
    app = QApplication.instance()
    if app is not None and app.platformName() == "wayland":
        return True
    return False


def _mpv_vo_for_embed() -> str:
    """VO recomendado para embed con wid según plataforma Qt efectiva."""
    app = QApplication.instance()
    if app is not None and app.platformName() in ("xcb", "linux"):
        return "x11,xv"
    return "gpu,x11"


def _mpv_log(level, prefix, text):
    """Registra mensajes de libmpv en consola (errores de carga/render)."""
    print(f"[mpv/{level}] {prefix}: {text}", file=sys.stderr, flush=True)


def format_playback_time(seconds: float) -> str:
    """Formatea segundos como H:MM:SS.mmm o MM:SS.mmm."""
    if seconds < 0:
        seconds = 0.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{secs:06.3f}"
    return f"{minutes:02d}:{secs:06.3f}"


def format_cue_range_label(cue_indices: list) -> str:
    """Etiqueta compacta de subtítulos SRT incluidos en un clip."""
    if not cue_indices:
        return ""
    nums = [i + 1 for i in cue_indices]
    if len(nums) == 1:
        return f"SRT #{nums[0]}"
    return f"SRT #{nums[0]}–#{nums[-1]} ({len(nums)} cues)"


# ---------------------------------------------------------------------------
# Corte en segundo plano
# ---------------------------------------------------------------------------

class CutSignals(QObject):
    finished = Signal(int, bool, str)  # segment_id, success, message


class BatchGenerateSignals(QObject):
    finished = Signal(bool, str, list)  # success, message, completed_segment_ids


class BatchGenerateTask(QRunnable):
    """Genera varios clips en una pasada ffmpeg (run_batch)."""

    def __init__(
        self,
        video_path,
        jobs,
        audio_track=0,
        video_track=0,
        cancel_token=None,
    ):
        super().__init__()
        self.video_path = video_path
        self.jobs = jobs
        self.audio_track = audio_track
        self.video_track = video_track
        self.cancel_token = cancel_token or BatchCancelToken()
        self.signals = BatchGenerateSignals()

    def run(self):
        try:
            if self.cancel_token.cancelled:
                self.signals.finished.emit(False, "Cancelado por el usuario.", [])
                return

            _vg, _ve, _ag, _ae, err = run_batch(
                self.video_path,
                self.jobs,
                width=640,
                height=480,
                crf=32,
                audio_bitrate="96k",
                mp3_bitrate="128k",
                audio_track=self.audio_track,
                video_track=self.video_track,
                cancel_token=self.cancel_token,
            )

            completed = []
            for job in self.jobs:
                video_ok = (
                    os.path.exists(job["video_path"])
                    and os.path.getsize(job["video_path"]) > 0
                )
                audio_ok = (
                    os.path.exists(job["audio_path"])
                    and os.path.getsize(job["audio_path"]) > 0
                )
                if video_ok and audio_ok:
                    completed.append(job["index"])

            if self.cancel_token.cancelled:
                self.signals.finished.emit(
                    False, "Cancelado por el usuario.", completed
                )
            elif err:
                self.signals.finished.emit(False, err, completed)
            else:
                self.signals.finished.emit(True, "", completed)
        except Exception as e:
            self.signals.finished.emit(False, str(e), [])


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


class ExtractSubtitleTask(QRunnable):
    def __init__(self, video_path, stream_index, output_path):
        super().__init__()
        self.video_path = video_path
        self.stream_index = stream_index
        self.output_path = output_path
        self.signals = CutSignals()

    def run(self):
        try:
            extract_subtitle(
                self.video_path, self.stream_index, self.output_path, exit_on_error=False
            )
            self.signals.finished.emit(0, True, self.output_path)
        except FileNotFoundError:
            self.signals.finished.emit(0, False, "FFmpeg no está instalado.")
        except RuntimeError as e:
            self.signals.finished.emit(0, False, str(e))
        except Exception as e:
            self.signals.finished.emit(0, False, str(e))


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
        self._mpv_gl_widget = None
        self._pending_mpv_path = None
        self._use_opengl_embed = False
        self.probe_data = None
        self.media_summary = None
        self.audio_track = 0
        self.video_track = 0
        self.subtitle_track_index = None
        self.subtitle_language = "en"
        self.subtitle_path = None
        self.parser_options = ParserOptions(language="en")
        self.cue_map = {}  # índice de bloque SRT -> {index, start, end, text}

        self._project_path = None
        self._project_modified = False
        self._series_name = ""
        self._season = 1
        self._episode_num = 1
        self._project_root_dir = "."
        self.padding_start = 0.0
        self.padding_end = 0.0

        self._batch_active = False
        self._batch_cancel_token = None
        self._batch_previous_status = {}

        self.thread_pool = QThreadPool()
        self._pending_extract_options = None
        self._segment_loop_active = False
        self._seek_step_sec = 1.0
        self._text_edit_undo_pending = False
        self._preview_display_id: int | None = None
        self._refreshing_list = False

        self._playback_timer = QTimer(self)
        self._playback_timer.setInterval(200)
        self._playback_timer.timeout.connect(self._update_position_label)

        self._history = EditHistory()
        self._undo_action = None
        self._redo_action = None

        self._build_ui()
        self._build_menu()
        self._update_window_title()

    # -- UI ---------------------------------------------------------------

    def _build_menu(self):
        menu = self.menuBar().addMenu("Archivo")
        menu.addAction("Abrir proyecto...", self.open_project)
        menu.addAction("Guardar proyecto", self.save_project).setShortcut(
            QKeySequence.StandardKey.Save
        )
        menu.addAction("Guardar proyecto como...", self.save_project_as)
        menu.addSeparator()
        menu.addAction("Abrir vídeo...", self.open_video)
        menu.addAction("Abrir subtítulo (.srt)...", self.open_subtitle)
        menu.addAction("Extraer subtítulos del vídeo...", self.extract_subtitles_from_video)
        menu.addSeparator()
        menu.addAction("Exportar TSV...", self.export_tsv)

        edit_menu = self.menuBar().addMenu("Edición")
        self._undo_action = edit_menu.addAction("Deshacer")
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_action.triggered.connect(self.undo_edit)
        self._redo_action = edit_menu.addAction("Rehacer")
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_action.triggered.connect(self.redo_edit)
        self._update_undo_actions()

    def _edit_shortcuts_blocked(self) -> bool:
        fw = self.focusWidget()
        return isinstance(fw, (QLineEdit, QSpinBox, QDoubleSpinBox, QAbstractSpinBox))

    def _current_selected_id(self):
        item = self.segment_list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _push_undo(self):
        self._history.push(self.segments, self.next_id, self._current_selected_id())
        self._update_undo_actions()

    def _update_undo_actions(self):
        if self._undo_action is not None:
            self._undo_action.setEnabled(self._history.can_undo())
        if self._redo_action is not None:
            self._redo_action.setEnabled(self._history.can_redo())

    def _mark_project_modified(self):
        if not self._project_modified:
            self._project_modified = True
            self._update_window_title()

    def _clear_project_modified(self):
        self._project_modified = False
        self._update_window_title()

    def _update_window_title(self):
        base = "Anki Video Tool — Editor de clips"
        if self._project_path:
            name = os.path.basename(self._project_path)
            prefix = "* " if self._project_modified else ""
            self.setWindowTitle(f"{prefix}{name} — {base}")
        elif self._project_modified:
            self.setWindowTitle(f"* Sin guardar — {base}")
        else:
            self.setWindowTitle(base)

    def _confirm_discard_unsaved(self, action: str) -> bool:
        if not self._project_modified:
            return True
        reply = QMessageBox.question(
            self,
            "Cambios sin guardar",
            f"Hay cambios sin guardar.\n¿Descartarlos y {action}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _prompt_save_before_close(self) -> bool:
        """True si se puede continuar (guardado, descartado o sin cambios). False = cancelar."""
        if not self._project_modified:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Cambios sin guardar")
        box.setText("¿Guardar el proyecto antes de salir?")
        box.setInformativeText(
            "Los cambios en clips, tiempos y subtítulos se perderán si no guardas."
        )
        save_btn = box.addButton("Guardar", QMessageBox.AcceptRole)
        discard_btn = box.addButton("No guardar", QMessageBox.DestructiveRole)
        cancel_btn = box.addButton("Cancelar", QMessageBox.RejectRole)
        box.setDefaultButton(save_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked == cancel_btn:
            return False
        if clicked == discard_btn:
            return True
        if clicked == save_btn:
            self.save_project()
            return not self._project_modified
        return False

    def _suggest_project_path(self) -> str:
        if self._project_path:
            return self._project_path
        if self.video_path:
            series = self._series_name or guess_series_name(self.video_path)
            from core.naming import format_episode_label
            label = format_episode_label(self._season, self._episode_num)
            root = os.path.dirname(self.video_path)
            return default_project_path(series, label, root)
        return ""

    def _build_current_project(self):
        last_id = max((s["id"] for s in self.segments), default=0)
        last_id = max(last_id, self.next_id - 1)
        return build_project_from_gui(
            series_name=self._effective_series_name(),
            season=self._season,
            episode_num=self._episode_num,
            video_path=self.video_path,
            episode_title=self.episode_title,
            subtitle_path=self.subtitle_path,
            subtitle_track_index=self.subtitle_track_index,
            subtitle_language=self.subtitle_language,
            audio_track=self.audio_track,
            video_track=self.video_track,
            media_summary=self.media_summary,
            parser_options=self.parser_options,
            cue_map=self.cue_map,
            segments=self.segments,
            translate_enabled=self.translate_checkbox.isChecked(),
            last_clip_id=last_id,
            root_dir=self._project_root_dir,
            padding_start=self.padding_start,
            padding_end=self.padding_end,
        )

    def save_project(self):
        if not self.video_path and not self.segments:
            QMessageBox.information(
                self, "Nada que guardar",
                "Abre un vídeo o carga subtítulos antes de guardar el proyecto."
            )
            return
        if not self._project_path:
            self.save_project_as()
            return
        try:
            project = self._build_current_project()
            save_project(project, self._project_path)
            self._clear_project_modified()
            self.statusBar().showMessage(f"Proyecto guardado: {self._project_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))

    def save_project_as(self):
        if not self.video_path and not self.segments:
            QMessageBox.information(
                self, "Nada que guardar",
                "Abre un vídeo o carga subtítulos antes de guardar el proyecto."
            )
            return
        suggested = self._suggest_project_path()
        start_dir = os.path.dirname(suggested) if suggested else ""
        start_name = os.path.basename(suggested) if suggested else "proyecto.anki-project.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar proyecto",
            os.path.join(start_dir, start_name) if start_dir else start_name,
            "Proyecto Anki (*.anki-project.json);;JSON (*.json);;Todos (*.*)",
        )
        if not path:
            return
        if not path.endswith(".anki-project.json") and not path.endswith(".json"):
            path += ".anki-project.json"
        try:
            project = self._build_current_project()
            save_project(project, path)
            self._project_path = path
            self._project_root_dir = os.path.dirname(os.path.abspath(path)) or "."
            self._clear_project_modified()
            self.statusBar().showMessage(f"Proyecto guardado: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))

    def open_project(self):
        if not self._confirm_discard_unsaved("abrir otro proyecto"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir proyecto",
            "",
            "Proyecto Anki (*.anki-project.json);;JSON (*.json);;Todos (*.*)",
        )
        if not path:
            return
        self._stop_mpv_playback()
        self._reset_gui_for_project_load()
        try:
            project = load_project(path)
            state = load_gui_state_from_project(project)
        except Exception as e:
            QMessageBox.critical(self, "Error al abrir proyecto", str(e))
            return

        self._apply_loaded_project_state(state, path)

    def _reset_gui_for_project_load(self):
        """Limpia estado editable antes de aplicar un proyecto JSON (sin destruir mpv)."""
        self.stop_preview()
        self._clear_preview_display()
        self.segments = []
        self.cue_map = {}
        self.next_id = 1
        self.video_path = None
        self.probe_data = None
        self.media_summary = None
        self.subtitle_path = None
        self._history.clear()
        self._update_undo_actions()
        self.segment_text_edit.blockSignals(True)
        self.segment_text_edit.clear()
        self.segment_text_edit.blockSignals(False)
        self._update_cues_detail(None)
        self._refresh_list()

    def _apply_loaded_project_state(self, state, project_path: str):
        self._project_path = project_path
        self._project_root_dir = state.root_dir
        self._series_name = state.series_name
        self._season = state.season
        self._episode_num = state.episode_num
        self.padding_start = state.padding_start
        self.padding_end = state.padding_end
        self.episode_title = state.episode_title
        self.subtitle_path = state.subtitle_path
        self.subtitle_track_index = state.subtitle_track_index
        self.subtitle_language = state.subtitle_language
        self.parser_options = state.parser_options
        self.audio_track = state.audio_track
        self.video_track = state.video_track
        self.media_summary = state.media_summary
        self.cue_map = state.cue_map
        self.segments = state.segments
        self.next_id = state.next_id
        self.translate_checkbox.setChecked(state.translate_enabled)
        self.series_name_edit.setText(state.series_name)
        self.padding_start_spin.setValue(state.padding_start)
        self.padding_end_spin.setValue(state.padding_end)

        self._history.clear()
        self._update_undo_actions()
        self._refresh_list()
        if self.segment_list.count():
            self.segment_list.setCurrentRow(0)

        missing_video = False
        if state.video_path:
            if os.path.isfile(state.video_path):
                video_path = os.path.abspath(state.video_path)
                self.video_path = video_path
                try:
                    self.probe_data = probe(video_path, exit_on_error=False)
                    self.media_summary = summarize_media(self.probe_data)
                except (FileNotFoundError, RuntimeError):
                    self.probe_data = None
                if mpv is not None:
                    if not self._use_opengl_embed:
                        self._ensure_native_video_window()
                    self._load_media_in_player(video_path)
            else:
                missing_video = True
                self.video_path = state.video_path
        else:
            self.video_path = None

        self._clear_project_modified()
        if self._reevaluate_outdated_segments():
            self._refresh_list()
        msg = f"Proyecto cargado: {os.path.basename(project_path)}"
        if missing_video:
            msg += f"  |  Vídeo no encontrado: {state.video_path}"
        self.statusBar().showMessage(msg)
        if missing_video:
            QMessageBox.warning(
                self,
                "Vídeo no encontrado",
                f"No se encontró el archivo de vídeo:\n{state.video_path}\n\n"
                "Se cargaron subtítulos y clips; abre el vídeo manualmente si lo tienes en otra ruta."
            )

    def _load_video_from_path(self, path: str, *, show_media_dialog: bool = True):
        path = os.path.abspath(path)
        try:
            self.probe_data = probe(path, exit_on_error=False)
        except (FileNotFoundError, RuntimeError) as e:
            if show_media_dialog:
                QMessageBox.critical(self, "Error al analizar el vídeo", str(e))
            return False

        if show_media_dialog:
            dialog = MediaInfoDialog(path, self.probe_data, self, language=self.subtitle_language)
            if dialog.exec() != MediaInfoDialog.Accepted:
                return False
            tracks = dialog.selection()
            self.audio_track = tracks.audio_track
            self.video_track = tracks.video_track
            self.subtitle_track_index = tracks.subtitle_track_index
            self.subtitle_language = tracks.subtitle_language
            self.parser_options.language = tracks.subtitle_language
        elif self.media_summary is None:
            self.media_summary = summarize_media(self.probe_data)

        self.video_path = path
        self.media_summary = summarize_media(self.probe_data)

        raw_title = self.media_summary["format"].get("title") or detect_video_title(path)
        if not self.episode_title:
            self.episode_title = extract_episode_title(raw_title) or ""
        if not self._series_name:
            self._series_name = guess_series_name(path)
        if self._season == 1 and self._episode_num == 1:
            self._season, self._episode_num = parse_season_episode(raw_title)

        if mpv is not None:
            if not self._use_opengl_embed:
                self._ensure_native_video_window()
            self._stop_mpv_playback()
            self._load_media_in_player(path)
        return True

    def _finish_video_open(self, path: str) -> bool:
        """Carga vídeo, subtítulos automáticos y sincroniza la GUI."""
        path = os.path.abspath(path)
        if not self._load_video_from_path(path, show_media_dialog=False):
            return False
        self._try_load_subtitles_after_video(path)
        self._sync_playback_ui_after_load()
        return True

    def _try_load_subtitles_after_video(self, video_path: str):
        """Carga subtítulos automáticamente: sidecar .srt o pista embebida textual."""
        video_path = os.path.abspath(video_path)
        sidecar = find_sidecar_subtitle(video_path)
        if sidecar:
            if self._load_subtitles_from_file(
                sidecar,
                replace(self.parser_options, language=self.subtitle_language),
                source=f"Sidecar {os.path.basename(sidecar)}",
                skip_confirm=True,
            ):
                return

        if self.subtitle_track_index is not None:
            subtitles = (self.media_summary or {}).get("subtitles", [])
            stream = find_subtitle_stream(subtitles, self.subtitle_track_index)
            if stream and stream.get("is_text") and not stream.get("is_image"):
                out_path = subtitle_extract_path(video_path, self.subtitle_track_index)
                self._pending_extract_options = replace(
                    self.parser_options, language=self.subtitle_language
                )
                self.statusBar().showMessage("Extrayendo subtítulos del vídeo…")
                task = ExtractSubtitleTask(
                    video_path, self.subtitle_track_index, out_path
                )
                task.signals.finished.connect(self._on_extract_finished)
                self.thread_pool.start(task)
                return

        msg = self.statusBar().currentMessage()
        hint = "Sin subtítulos auto: Archivo → Abrir subtítulo (.srt) o Extraer subtítulos."
        self.statusBar().showMessage(f"{msg}  |  {hint}" if msg else hint)

    def _sync_playback_ui_after_load(self):
        """Selecciona primera oración y actualiza controles tras abrir vídeo."""
        if self.segments:
            self._select_first_segment()
        else:
            self._update_position_label()
        self._update_preview_controls()

    def _select_first_segment(self):
        if self.segment_list.count() > 0:
            self.segment_list.setCurrentRow(0)
        elif self.segments:
            self.on_segment_selected(0)

    def _update_preview_controls(self):
        has_player = self.player is not None
        has_segment = self._get_selected_segment() is not None
        self.preview_btn.setEnabled(has_player and has_segment)
        self._update_play_button()

    def _sync_gl_player_ref(self):
        if not self._use_opengl_embed or self._mpv_gl_widget is None:
            return
        if self._mpv_gl_widget.player is not None:
            self.player = self._mpv_gl_widget.player
            self._update_preview_controls()
            self._update_position_label()
            return
        QTimer.singleShot(50, self._sync_gl_player_ref)

    def _ensure_native_video_window(self):
        """Garantiza ventana nativa del QFrame antes de pasar wid a mpv."""
        if self.video_frame is None:
            return
        if not self.video_frame.testAttribute(Qt.WA_WState_Created):
            self.video_frame.create()
        _ = self.video_frame.winId()
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def _stop_mpv_playback(self):
        """Detiene reproducción y A-B loop sin destruir la instancia mpv."""
        self._stop_playback_timer()
        self._segment_loop_active = False
        player = self.player
        if player is None and self._mpv_gl_widget is not None:
            player = self._mpv_gl_widget.player
        if player is None:
            return
        try:
            player.pause = True
            player.command("stop")
            player.ab_loop_a = "no"
            player.ab_loop_b = "no"
        except Exception:
            pass

    def _ensure_mpv_player(self) -> bool:
        """Crea una única instancia mpv embebida (Capa 1 wid) si aún no existe."""
        if mpv is None:
            return False
        if self.player is not None:
            return True
        if self._use_opengl_embed:
            if self._mpv_gl_widget is not None and self._mpv_gl_widget.player is not None:
                self.player = self._mpv_gl_widget.player
                return True
            return False
        self._ensure_native_video_window()
        _ensure_mpv_numeric_locale()
        try:
            win_id = int(self.video_frame.winId())
            self.player = mpv.MPV(
                log_handler=_mpv_log,
                **mpv_player_kwargs(
                    vo=_mpv_vo_for_embed(),
                    wid=str(win_id),
                ),
            )
            return True
        except Exception as e:
            print(f"[mpv] Error al crear reproductor: {e}", file=sys.stderr, flush=True)
            self.player = None
            return False

    def _mpv_loadfile(self, player, path: str):
        player.command("loadfile", path, "replace")

    def _deferred_load_media_in_player(self):
        path = self._pending_mpv_path
        if not path:
            return
        self._pending_mpv_path = None
        self._load_media_in_player(path)

    def _load_media_in_player(self, path: str):
        """Carga un vídeo en la instancia mpv existente (sin terminate/recreate)."""
        if mpv is None:
            return
        path = os.path.abspath(path)
        try:
            if self._use_opengl_embed and self._mpv_gl_widget is not None:
                self._mpv_gl_widget.load(path)
                self._sync_gl_player_ref()
            else:
                if self.player is None and self.video_frame is not None:
                    if not self.video_frame.testAttribute(Qt.WA_WState_Created):
                        self._pending_mpv_path = path
                        QTimer.singleShot(0, self._deferred_load_media_in_player)
                        return
                if not self._ensure_mpv_player():
                    QMessageBox.warning(
                        self,
                        "Error de reproducción",
                        f"No se pudo inicializar mpv para:\n{path}",
                    )
                    return
                self._mpv_loadfile(self.player, path)
                QTimer.singleShot(300, self._pause_mpv_after_load)
            QTimer.singleShot(500, lambda p=path: self._verify_mpv_playback(p))
        except Exception as e:
            print(f"[mpv] Error al cargar {path!r}: {e}", file=sys.stderr, flush=True)
            QMessageBox.warning(
                self,
                "Error de reproducción",
                f"No se pudo cargar el vídeo en mpv:\n\n{e}",
            )
        self._segment_loop_active = False
        self._update_preview_controls()
        self._update_position_label()

    def _pause_mpv_after_load(self):
        if self.player is not None:
            try:
                self.player.pause = True
            except Exception:
                pass

    def _verify_mpv_playback(self, path: str):
        player = self.player
        if player is None and self._mpv_gl_widget is not None:
            player = self._mpv_gl_widget.player
            if player is not None:
                self.player = player
        if player is None:
            QMessageBox.warning(
                self,
                "Reproducción mpv",
                f"No se pudo crear el reproductor para:\n{path}",
            )
            return
        try:
            loaded = player.path
            if not loaded:
                print(
                    f"[mpv] Advertencia: ningún archivo cargado tras loadfile({path!r})",
                    file=sys.stderr,
                    flush=True,
                )
                QMessageBox.warning(
                    self,
                    "Reproducción mpv",
                    f"mpv no cargó el archivo:\n{path}\n\n"
                    "Revisa la consola para mensajes [mpv/error].",
                )
        except Exception as e:
            print(f"[mpv] Advertencia al verificar carga: {e}", file=sys.stderr, flush=True)
        self._update_preview_controls()

    def _shutdown_mpv_player(self):
        """Destruye mpv solo al cerrar la aplicación."""
        self._stop_playback_timer()
        self._segment_loop_active = False
        self._pending_mpv_path = None
        if self._mpv_gl_widget is not None:
            self._mpv_gl_widget.shutdown()
        elif self.player is not None:
            try:
                self.player.pause = True
                self.player.command("stop")
                self.player.ab_loop_a = "no"
                self.player.ab_loop_b = "no"
                self.player.wid = "0"
            except Exception:
                pass
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
            try:
                self.player.terminate()
            except Exception:
                pass
        self.player = None

    def _select_segment_by_id(self, seg_id):
        for row in range(self.segment_list.count()):
            item = self.segment_list.item(row)
            if item.data(Qt.UserRole) == seg_id:
                self.segment_list.setCurrentRow(row)
                return
        pending = self._pending_segments()
        if pending:
            self.segment_list.setCurrentRow(0)

    def _restore_snapshot(self, snap):
        self.segments = snap["segments"]
        self.next_id = snap["next_id"]
        self._refresh_list()
        selected_id = snap.get("selected_id")
        if selected_id is not None:
            self._select_segment_by_id(selected_id)
        elif self.segment_list.count():
            self.segment_list.setCurrentRow(0)
        self._on_segment_bounds_changed()
        self._update_undo_actions()
        seg = self._get_selected_segment()
        self._update_cues_detail(seg)
        self._mark_project_modified()

    def undo_edit(self):
        if self._edit_shortcuts_blocked():
            return
        snap = self._history.undo(self.segments, self.next_id, self._current_selected_id())
        if snap is None:
            return
        self._restore_snapshot(snap)
        self.statusBar().showMessage("Deshecho.")

    def redo_edit(self):
        if self._edit_shortcuts_blocked():
            return
        snap = self._history.redo(self.segments, self.next_id, self._current_selected_id())
        if snap is None:
            return
        self._restore_snapshot(snap)
        self.statusBar().showMessage("Rehecho.")

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        # --- Panel izquierdo: previsualización + edición fina (scroll) ---
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)

        self._use_opengl_embed = _should_use_opengl_embed()
        if self._use_opengl_embed and mpv is not None:
            from ui.mpv_gl_widget import MpvGlWidget
            self._mpv_gl_widget = MpvGlWidget(
                self,
                locale_fn=_ensure_mpv_numeric_locale,
                log_handler=_mpv_log,
            )
            self._mpv_gl_widget.setStyleSheet("background-color: black;")
            self._mpv_gl_widget.setMinimumHeight(300)
            left_layout.addWidget(self._mpv_gl_widget)
            self.video_frame = None
        else:
            self.video_frame = QFrame()
            self.video_frame.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
            self.video_frame.setAttribute(Qt.WA_NativeWindow, True)
            self.video_frame.setStyleSheet("background-color: black;")
            self.video_frame.setMinimumHeight(300)
            left_layout.addWidget(self.video_frame)
            self._mpv_gl_widget = None

        playback_group = QGroupBox("Previsualización (mpv — no genera archivos)")
        playback_layout = QVBoxLayout(playback_group)

        preview_note = QLabel(
            "«Probar clip» reproduce el segmento en bucle con el vídeo original. "
            "No se crea ningún archivo en disco."
        )
        preview_note.setWordWrap(True)
        preview_note.setStyleSheet("color: gray; font-size: 11px;")
        playback_layout.addWidget(preview_note)

        row1 = QHBoxLayout()
        self.preview_btn = QPushButton("🔁 Probar clip")
        self.preview_btn.clicked.connect(self.preview_selected_clip)
        self.play_btn = QPushButton("⏸ Pausar")
        self.play_btn.clicked.connect(self.toggle_play_pause)
        self.stop_btn = QPushButton("■ Detener")
        self.stop_btn.clicked.connect(self.stop_preview)
        row1.addWidget(self.preview_btn)
        row1.addWidget(self.play_btn)
        row1.addWidget(self.stop_btn)
        playback_layout.addLayout(row1)

        row2 = QHBoxLayout()
        goto_start = QPushButton("⏮ Inicio clip")
        goto_start.clicked.connect(self.seek_to_segment_start)
        goto_end = QPushButton("⏭ Final clip")
        goto_end.clicked.connect(self.seek_to_segment_end)
        seek_back = QPushButton("◀ −1 s")
        seek_back.clicked.connect(lambda: self.seek_relative(-self._seek_step_sec))
        seek_fwd = QPushButton("+1 s ▶")
        seek_fwd.clicked.connect(lambda: self.seek_relative(self._seek_step_sec))
        row2.addWidget(goto_start)
        row2.addWidget(goto_end)
        row2.addWidget(seek_back)
        row2.addWidget(seek_fwd)
        playback_layout.addLayout(row2)

        self.position_label = QLabel("Posición: —")
        playback_layout.addWidget(self.position_label)

        hint = QLabel(
            "Atajos: Espacio = probar/pausa  |  ←/→ = ±1 s  |  "
            "Ctrl+Z / Ctrl+Shift+Z = deshacer/rehacer"
        )
        hint.setStyleSheet("color: gray; font-size: 11px;")
        playback_layout.addWidget(hint)

        left_layout.addWidget(playback_group)

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

        self.start_spin.valueChanged.connect(self._on_segment_bounds_changed)
        self.end_spin.valueChanged.connect(self._on_segment_bounds_changed)

        end_minus = QPushButton("-100ms")
        end_minus.clicked.connect(lambda: self._nudge(self.end_spin, -0.1))
        end_plus = QPushButton("+100ms")
        end_plus.clicked.connect(lambda: self._nudge(self.end_spin, 0.1))
        end_layout.addWidget(end_minus)
        end_layout.addWidget(end_plus)
        left_layout.addLayout(end_layout)

        left_layout.addWidget(QLabel("Texto:"))
        self.segment_text_edit = QPlainTextEdit()
        self.segment_text_edit.setPlaceholderText("Texto de la oración seleccionada…")
        self.segment_text_edit.setMaximumHeight(80)
        self.segment_text_edit.textChanged.connect(self._on_segment_text_changed)
        left_layout.addWidget(self.segment_text_edit)

        apply_btn = QPushButton("Aplicar tiempos a la línea seleccionada")
        apply_btn.clicked.connect(self.apply_times_to_selected)
        left_layout.addWidget(apply_btn)

        generate_group = QGroupBox("Generación (FFmpeg — crea archivos)")
        generate_layout = QVBoxLayout(generate_group)
        gen_note = QLabel(
            "«Generar clip» escribe .webm y .mp3 en output_files/ con el mismo "
            "formato de nombre que cut_clips.py. El padding se aplica al cortar, "
            "no a la previsualización mpv."
        )
        gen_note.setWordWrap(True)
        gen_note.setStyleSheet("color: gray; font-size: 11px;")
        generate_layout.addWidget(gen_note)

        series_row = QHBoxLayout()
        series_row.addWidget(QLabel("Serie:"))
        self.series_name_edit = QLineEdit()
        self.series_name_edit.setPlaceholderText("Nombre para archivos (ej. Spawn_Anki_Video)")
        self.series_name_edit.textChanged.connect(self._on_series_name_changed)
        series_row.addWidget(self.series_name_edit)
        generate_layout.addLayout(series_row)

        padding_row = QHBoxLayout()
        padding_row.addWidget(QLabel("Padding inicio:"))
        self.padding_start_spin = QDoubleSpinBox()
        self.padding_start_spin.setDecimals(3)
        self.padding_start_spin.setRange(0, 30)
        self.padding_start_spin.setSingleStep(0.05)
        self.padding_start_spin.valueChanged.connect(self._on_padding_changed)
        padding_row.addWidget(self.padding_start_spin)
        padding_row.addWidget(QLabel("final:"))
        self.padding_end_spin = QDoubleSpinBox()
        self.padding_end_spin.setDecimals(3)
        self.padding_end_spin.setRange(0, 30)
        self.padding_end_spin.setSingleStep(0.05)
        self.padding_end_spin.valueChanged.connect(self._on_padding_changed)
        padding_row.addWidget(self.padding_end_spin)
        generate_layout.addLayout(padding_row)

        self.generate_btn = QPushButton("💾 Generar clip (WebM + MP3)")
        self.generate_btn.setStyleSheet("font-weight: bold;")
        self.generate_btn.clicked.connect(self.generate_selected_clip)
        generate_layout.addWidget(self.generate_btn)

        batch_row = QHBoxLayout()
        self.batch_generate_btn = QPushButton("⚡ Generar todos pendientes")
        self.batch_generate_btn.clicked.connect(self.generate_all_pending)
        batch_row.addWidget(self.batch_generate_btn)
        self.batch_cancel_btn = QPushButton("Cancelar lote")
        self.batch_cancel_btn.setEnabled(False)
        self.batch_cancel_btn.clicked.connect(self.cancel_batch_generation)
        batch_row.addWidget(self.batch_cancel_btn)
        generate_layout.addLayout(batch_row)

        self.batch_progress = QProgressBar()
        self.batch_progress.setVisible(False)
        self.batch_progress.setRange(0, 0)
        generate_layout.addWidget(self.batch_progress)

        left_layout.addWidget(generate_group)

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

        left_scroll.setWidget(left_content)
        splitter.addWidget(left_scroll)

        # --- Panel derecho: lista dinámica de trabajo ---
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.list_header_label = QLabel("Oraciones pendientes:")
        right_layout.addWidget(self.list_header_label)

        self.segment_list = QListWidget()
        self.segment_list.currentRowChanged.connect(self.on_segment_selected)
        right_layout.addWidget(self.segment_list)

        list_controls = QHBoxLayout()
        merge_btn = QPushButton("Fusionar con siguiente")
        merge_btn.clicked.connect(self.merge_with_next)
        split_btn = QPushButton("Dividir clip")
        split_btn.clicked.connect(self.split_selected_clip)
        delete_btn = QPushButton("Eliminar")
        delete_btn.clicked.connect(self.delete_selected)
        list_controls.addWidget(merge_btn)
        list_controls.addWidget(split_btn)
        list_controls.addWidget(delete_btn)
        right_layout.addLayout(list_controls)

        cues_group = QGroupBox("Subtítulos incluidos en el clip")
        cues_layout = QVBoxLayout(cues_group)
        self.cues_detail = QPlainTextEdit()
        self.cues_detail.setReadOnly(True)
        self.cues_detail.setMaximumHeight(120)
        self.cues_detail.setPlaceholderText(
            "Selecciona una línea para ver qué bloques SRT componen este clip."
        )
        cues_layout.addWidget(self.cues_detail)
        right_layout.addWidget(cues_group)

        splitter.addWidget(right)
        splitter.setSizes([650, 450])

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Abre un vídeo y un subtítulo para empezar.")

    # -- Carga de archivos --------------------------------------------------

    def open_video(self):
        if not self._confirm_discard_unsaved("abrir otro vídeo"):
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir vídeo", "", "Vídeo (*.mkv *.mp4 *.webm);;Todos (*.*)"
        )
        if not path:
            return
        path = os.path.abspath(path)

        try:
            self.probe_data = probe(path, exit_on_error=False)
        except FileNotFoundError:
            QMessageBox.critical(
                self, "ffprobe no disponible",
                "FFprobe no está instalado.\n\n"
                "Instálalo con tu gestor de paquetes, por ejemplo:\n"
                "  sudo apt install ffmpeg"
            )
            return
        except RuntimeError as e:
            QMessageBox.critical(
                self, "Error al analizar el vídeo",
                f"No se pudo analizar el archivo:\n\n{e}"
            )
            return

        dialog = MediaInfoDialog(path, self.probe_data, self, language=self.subtitle_language)
        if dialog.exec() != MediaInfoDialog.Accepted:
            return

        tracks = dialog.selection()
        self.audio_track = tracks.audio_track
        self.video_track = tracks.video_track
        self.subtitle_track_index = tracks.subtitle_track_index
        self.subtitle_language = tracks.subtitle_language
        self.parser_options.language = tracks.subtitle_language

        self._series_name = guess_series_name(path)
        self.series_name_edit.blockSignals(True)
        self.series_name_edit.setText(self._series_name)
        self.series_name_edit.blockSignals(False)
        raw_title = summarize_media(self.probe_data)["format"].get("title") or detect_video_title(path)
        self._season, self._episode_num = parse_season_episode(raw_title)
        self.episode_title = extract_episode_title(raw_title) or ""
        self._project_path = None
        self._project_root_dir = os.path.dirname(os.path.abspath(path)) or "."

        self._stop_mpv_playback()
        if not self._finish_video_open(path):
            return

        self._reevaluate_outdated_segments()
        self._mark_project_modified()

        if mpv is None:
            QMessageBox.warning(
                self, "python-mpv no disponible",
                "No se pudo cargar 'mpv' (revisa que libmpv esté instalado:\n"
                "  sudo apt install libmpv2\n"
                "  pip install python-mpv --break-system-packages\n\n"
                "Podrás seguir editando tiempos y cortando, pero sin previsualización."
            )

        track_info = f"audio={self.audio_track}, video={self.video_track}"
        if self.subtitle_track_index is not None:
            track_info += f", subtítulo abs={self.subtitle_track_index}"
        self.statusBar().showMessage(
            f"Vídeo cargado: {os.path.basename(path)}"
            + (f'  |  Título: "{self.episode_title}"' if self.episode_title else "")
            + f"  |  Pistas: {track_info}"
        )

    def open_subtitle(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir subtítulo", "", "Subtítulos (*.srt);;Todos (*.*)"
        )
        if not path:
            return

        dialog = SubtitleLoadDialog(
            self,
            srt_path=path,
            source_label="Archivo externo",
            options=replace(self.parser_options, language=self.subtitle_language),
        )
        dialog.options_panel.set_language(self.subtitle_language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._load_subtitles_from_file(path, dialog.options(), source="Archivo externo")

    def extract_subtitles_from_video(self):
        if not self.video_path:
            QMessageBox.information(
                self, "Sin vídeo",
                "Primero abre un vídeo (Archivo → Abrir vídeo…)."
            )
            return
        if self.subtitle_track_index is None:
            QMessageBox.information(
                self, "Sin pista de subtítulos",
                "No hay pista de subtítulos seleccionada.\n\n"
                "Vuelve a abrir el vídeo y elige una pista de subtítulos embebida, "
                "o usa Archivo → Abrir subtítulo (.srt) con un archivo externo."
            )
            return

        subtitles = (self.media_summary or {}).get("subtitles", [])
        stream = find_subtitle_stream(subtitles, self.subtitle_track_index)
        if stream is None:
            QMessageBox.warning(
                self, "Pista no encontrada",
                f"No se encontró la pista de subtítulos con índice {self.subtitle_track_index}."
            )
            return
        if stream.get("is_image"):
            QMessageBox.critical(
                self, "Subtítulos gráficos",
                "La pista seleccionada es gráfica (PGS/VobSub) y no puede convertirse "
                "directamente a texto editable.\n\n"
                "Necesitas un archivo .srt de otra fuente."
            )
            return
        if not stream.get("is_text"):
            QMessageBox.critical(
                self, "Formato no soportado",
                f"La pista seleccionada ({stream['codec_name']}) no es un subtítulo "
                "textual reconocido.\n\n"
                "Formatos soportados: SRT, ASS, SSA, WebVTT, mov_text."
            )
            return

        out_path = subtitle_extract_path(self.video_path, self.subtitle_track_index)
        source_label = (
            f"Pista embebida abs={self.subtitle_track_index} "
            f"({stream['codec_name']}, {stream['language']})"
        )

        dialog = SubtitleLoadDialog(
            self,
            srt_path=out_path,
            source_label=source_label,
            options=replace(self.parser_options, language=self.subtitle_language),
        )
        dialog.options_panel.set_language(self.subtitle_language)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self._pending_extract_options = dialog.options()
        self.statusBar().showMessage("Extrayendo subtítulos del vídeo…")
        task = ExtractSubtitleTask(self.video_path, self.subtitle_track_index, out_path)
        task.signals.finished.connect(self._on_extract_finished)
        self.thread_pool.start(task)

    def _on_extract_finished(self, _segment_id, success, message):
        if not success:
            QMessageBox.critical(
                self, "Error al extraer subtítulos",
                message[-800:] if message else "Error desconocido."
            )
            self._pending_extract_options = None
            return

        srt_path = message
        options = self._pending_extract_options
        self._pending_extract_options = None
        if self._load_subtitles_from_file(
            srt_path, options,
            source=f"Pista embebida abs={self.subtitle_track_index}",
            skip_confirm=True,
        ):
            self._sync_playback_ui_after_load()

    def _confirm_replace_segments(self) -> bool:
        active = [s for s in self.segments if s["status"] in ("pending", "exported")]
        if not active:
            return True
        reply = QMessageBox.question(
            self,
            "Reemplazar subtítulos",
            f"Ya hay {len(active)} línea(s) cargada(s).\n"
            "¿Reemplazarlas con los nuevos subtítulos?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _load_subtitles_from_file(
        self,
        srt_path,
        options: ParserOptions,
        source: str = "",
        *,
        skip_confirm: bool = False,
    ) -> bool:
        srt_path = os.path.abspath(srt_path)
        if not skip_confirm and not self._confirm_replace_segments():
            return False

        try:
            result = generate_sentences(srt_path, **options.as_generate_kwargs())
        except Exception as e:
            QMessageBox.critical(
                self, "Error al parsear subtítulos",
                f"No se pudo procesar el archivo:\n\n{e}"
            )
            return False

        self.parser_options = options
        self.subtitle_path = srt_path
        self.subtitle_language = options.language

        blocks = parse_srt_blocks(
            srt_path, offset=options.offset, scale=options.scale
        )
        self.cue_map = {
            i: {
                "index": i,
                "start": b["start"],
                "end": b["end"],
                "text": b["raw_text"].strip(),
            }
            for i, b in enumerate(blocks)
        }

        self.segments = []
        for s in result["sentences"]:
            self.segments.append({
                "id": self.next_id,
                "start": s["start"],
                "end": s["end"],
                "text": s["text"],
                "status": "pending",
                "cue_indices": list(s.get("cue_indices", [])),
            })
            self.next_id += 1

        self._history.clear()
        self._update_undo_actions()
        self._refresh_list()
        self._select_first_segment()
        self._mark_project_modified()
        filter_note = ""
        if result["skipped_by_filter"]:
            filter_note = f", {result['skipped_by_filter']} filtradas por duración/palabras"
        self.statusBar().showMessage(
            f"{len(self.segments)} oraciones cargadas "
            f"({result['discarded_blocks']} bloques SDH descartados{filter_note})."
            + (f"  Origen: {source}" if source else "")
        )
        return True

    # -- Lista de segmentos --------------------------------------------------

    def _segment_list_label(self, seg: dict) -> str:
        if seg["status"] == "outdated":
            tag = "[OUTDATED] "
        elif seg["id"] == self._preview_display_id:
            tag = "[PREVIEW] "
        else:
            tag = ""
        check = "[✓] " if seg["status"] == "exported" else ""
        return (
            f"{tag}{check}[{seg['start']:.3f} - {seg['end']:.3f}]  "
            f"{seg['text'][:60]}"
        )

    def _refresh_list(self, *, select_id: int | None = None):
        if self._refreshing_list:
            return
        self._refreshing_list = True
        try:
            self.segment_list.blockSignals(True)
            try:
                if select_id is None:
                    item = self.segment_list.currentItem()
                    select_id = item.data(Qt.UserRole) if item else None
                self.segment_list.clear()
                for seg in self.segments:
                    if seg["status"] == "deleted":
                        continue
                    label = self._segment_list_label(seg)
                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, seg["id"])
                    if seg["id"] == self._preview_display_id:
                        item.setForeground(Qt.darkGreen)
                    elif seg["status"] == "outdated":
                        item.setForeground(Qt.darkYellow)
                    elif seg["status"] == "exported":
                        item.setForeground(Qt.darkCyan)
                    self.segment_list.addItem(item)

                exported = self._exported_count()
                outdated = self._outdated_count()
                header = "Oraciones pendientes:"
                if outdated:
                    header += f"  ({outdated} desactualizada(s))"
                if exported:
                    header += f"  ({exported} generada(s))"
                self.list_header_label.setText(header)

                if select_id is not None:
                    self._select_segment_by_id(select_id)
            finally:
                self.segment_list.blockSignals(False)
        finally:
            self._refreshing_list = False

    def _pending_segments(self):
        return [s for s in self.segments if s["status"] in ("pending", "preview")]

    def _get_selected_segment(self):
        item = self.segment_list.currentItem()
        if item is None:
            return None
        seg_id = item.data(Qt.UserRole)
        for seg in self.segments:
            if seg["id"] == seg_id:
                return seg
        return None

    def _clear_preview_display(self):
        self._preview_display_id = None

    def _revert_preview_status_on_others(self, keep_id: int | None = None):
        for s in self.segments:
            if s["id"] == keep_id or s["status"] != "preview":
                continue
            s.pop("preview_start", None)
            s.pop("preview_end", None)
            s["status"] = "pending"

    def _sync_editor_widgets_to_segment(self, seg: dict):
        """Actualiza spinboxes, texto y cues_detail desde un segment dict (sin refrescar lista)."""
        self.start_spin.blockSignals(True)
        self.end_spin.blockSignals(True)
        self.start_spin.setValue(seg["start"])
        self.end_spin.setValue(seg["end"])
        self.start_spin.blockSignals(False)
        self.end_spin.blockSignals(False)
        self.segment_text_edit.blockSignals(True)
        self.segment_text_edit.setPlainText(seg["text"])
        self.segment_text_edit.blockSignals(False)
        self._update_position_label()
        self._update_cues_detail(seg)

    def on_segment_selected(self, row):
        self._clear_preview_display()
        self._revert_preview_status_on_others()
        seg = self._get_selected_segment()
        self._text_edit_undo_pending = False
        if seg is None:
            self.segment_text_edit.blockSignals(True)
            self.segment_text_edit.clear()
            self.segment_text_edit.blockSignals(False)
            self._update_cues_detail(None)
            self.segment_list.blockSignals(True)
            self._refresh_list()
            self.segment_list.blockSignals(False)
            return
        self._sync_editor_widgets_to_segment(seg)
        self.segment_list.blockSignals(True)
        self._refresh_list(select_id=seg["id"])
        self.segment_list.blockSignals(False)

    def _on_segment_text_changed(self):
        seg = self._get_selected_segment()
        if seg is None:
            return
        new_text = self.segment_text_edit.toPlainText()
        if seg["text"] == new_text:
            return
        if not self._text_edit_undo_pending:
            self._push_undo()
            self._text_edit_undo_pending = True
        seg["text"] = new_text
        self._refresh_list(select_id=seg["id"])
        self._mark_project_modified()

    def _update_cues_detail(self, seg):
        if seg is None:
            self.cues_detail.clear()
            return
        indices = seg.get("cue_indices", [])
        if not indices:
            self.cues_detail.setPlainText(
                "(Sin trazabilidad de subtítulos — recarga el SRT para activarla.)"
            )
            return
        lines = []
        for idx in indices:
            cue = self.cue_map.get(idx)
            if cue is None:
                lines.append(f"  #{idx + 1}: (bloque no encontrado)")
                continue
            lines.append(
                f"  #{idx + 1}  [{cue['start']:.3f} – {cue['end']:.3f}]  "
                f"{cue['text'][:70]}"
            )
        header = f"Clip id={seg['id']} — {len(indices)} bloque(s) SRT:\n"
        self.cues_detail.setPlainText(header + "\n".join(lines))

    def _format_cue_summary(self, cue_indices: list) -> str:
        return format_cue_range_label(cue_indices)

    def apply_times_to_selected(self):
        seg = self._get_selected_segment()
        if seg is None:
            return
        new_start, new_end = self.start_spin.value(), self.end_spin.value()
        if new_end <= new_start:
            QMessageBox.warning(self, "Tiempos inválidos", "End debe ser mayor que Start.")
            return
        self._push_undo()
        seg["start"], seg["end"] = new_start, new_end
        if seg["status"] == "preview":
            seg["preview_start"] = new_start
            seg["preview_end"] = new_end
        elif seg["status"] in ("exported", "outdated"):
            current = self._segment_fingerprint(seg)
            apply_outdated_status(seg, current)
        self._refresh_list(select_id=seg["id"])
        self._mark_project_modified()
        self.statusBar().showMessage(f"Tiempos actualizados para la línea id={seg['id']}.")

    def _text_from_cue_indices(self, cue_indices: list) -> str:
        parts = []
        for idx in cue_indices:
            cue = self.cue_map.get(idx)
            if cue:
                parts.append(cue["text"].strip())
        combined = " ".join(parts)
        if not combined:
            return combined
        return normalize_case(combined, language=self.parser_options.language)

    def _bounds_from_cue_indices(self, cue_indices: list) -> tuple[float, float]:
        starts, ends = [], []
        for idx in cue_indices:
            cue = self.cue_map.get(idx)
            if cue:
                starts.append(cue["start"])
                ends.append(cue["end"])
        if not starts:
            return 0.0, 0.0
        return min(starts), max(ends)

    def _restore_segment_text_and_bounds(self, seg: dict):
        cues = seg.get("cue_indices", [])
        if not cues:
            return
        seg["text"] = self._text_from_cue_indices(cues)
        seg["start"], seg["end"] = self._bounds_from_cue_indices(cues)

    def _split_text_by_words(self, text: str, ratio: float = 0.5):
        words = text.split()
        if len(words) <= 1:
            mid = max(1, len(text) // 2)
            return text[:mid].strip(), text[mid:].strip()
        cut = max(1, min(len(words) - 1, int(len(words) * ratio)))
        return " ".join(words[:cut]), " ".join(words[cut:])

    def _reset_segment_after_edit(self, seg: dict):
        seg["status"] = "pending"
        seg.pop("preview_start", None)
        seg.pop("preview_end", None)
        seg.pop("generation_fingerprint", None)

    def split_selected_clip(self):
        seg = self._get_selected_segment()
        if seg is None:
            return
        cue_indices = list(seg.get("cue_indices", []))
        if len(cue_indices) >= 2:
            split_after = self._prompt_srt_split_index(seg)
            if split_after is None:
                return
            self._push_undo()
            new_seg = self._split_at_srt_boundary(seg, split_after)
            self._refresh_list(select_id=seg["id"])
            self._sync_editor_widgets_to_segment(seg)
            self._mark_project_modified()
            self.statusBar().showMessage(
                f"Dividido id={seg['id']} tras bloque SRT → nuevo id={new_seg['id']}."
            )
            return
        start, end = seg["start"], seg["end"]
        split_time = (start + end) / 2
        if self.player is not None:
            pos = self.player.time_pos
            if pos is not None and start < float(pos) < end:
                split_time = float(pos)
        if split_time - start < MIN_DURATION or end - split_time < MIN_DURATION:
            QMessageBox.warning(
                self,
                "No se puede dividir",
                f"Cada fragmento debe durar al menos {MIN_DURATION} s.",
            )
            return
        self._push_undo()
        self._split_by_time(seg, split_time, end)

    def _prompt_srt_split_index(self, seg) -> int | None:
        playhead = None
        if self.player is not None:
            pos = self.player.time_pos
            if pos is not None:
                playhead = float(pos)
        dialog = SrtSplitDialog(
            self,
            cue_indices=list(seg.get("cue_indices", [])),
            cue_map=self.cue_map,
            playhead_pos=playhead,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.split_after_index()

    def _split_at_srt_boundary(self, seg: dict, split_after_idx: int) -> dict:
        cues = list(seg.get("cue_indices", []))
        first_cues = cues[: split_after_idx + 1]
        second_cues = cues[split_after_idx + 1 :]
        if not first_cues or not second_cues:
            raise ValueError("División SRT inválida: un fragmento quedaría vacío.")
        seg["cue_indices"] = first_cues
        self._restore_segment_text_and_bounds(seg)
        self._reset_segment_after_edit(seg)
        new_seg = {
            "id": self.next_id,
            "start": 0.0,
            "end": 0.0,
            "text": "",
            "status": "pending",
            "cue_indices": second_cues,
        }
        self._restore_segment_text_and_bounds(new_seg)
        self.next_id += 1
        idx = self.segments.index(seg)
        self.segments.insert(idx + 1, new_seg)
        return new_seg

    def _split_by_time(self, seg: dict, split_time: float, end: float):
        start = seg["start"]
        ratio = (split_time - start) / (end - start) if end > start else 0.5
        first_text, second_text = self._split_text_by_words(seg["text"], ratio)
        seg["end"] = split_time
        seg["text"] = first_text.strip() or seg["text"]
        seg["cue_indices"] = []
        self._reset_segment_after_edit(seg)
        new_seg = {
            "id": self.next_id,
            "start": split_time,
            "end": end,
            "text": second_text.strip() or "…",
            "status": "pending",
            "cue_indices": [],
        }
        self.next_id += 1
        idx = self.segments.index(seg)
        self.segments.insert(idx + 1, new_seg)
        self._refresh_list(select_id=seg["id"])
        self._sync_editor_widgets_to_segment(seg)
        self._mark_project_modified()
        self.statusBar().showMessage(
            f"Dividido id={seg['id']} en {split_time:.3f} s → nuevo id={new_seg['id']}."
        )

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
        self._push_undo()
        merged_indices = list(seg.get("cue_indices", [])) + list(nxt.get("cue_indices", []))
        seg["cue_indices"] = merged_indices
        if merged_indices:
            self._restore_segment_text_and_bounds(seg)
        else:
            seg["text"] = f"{seg['text']} {nxt['text']}"
            seg["end"] = nxt["end"]
        if seg["status"] == "preview":
            seg.pop("preview_start", None)
            seg.pop("preview_end", None)
            seg["status"] = "pending"
        nxt["status"] = "deleted"
        self._refresh_list(select_id=seg["id"])
        self._sync_editor_widgets_to_segment(seg)
        self._mark_project_modified()
        self.statusBar().showMessage(
            f"Fusionado: clip id={seg['id']} ahora incluye {self._format_cue_summary(merged_indices)}."
        )

    def delete_selected(self):
        seg = self._get_selected_segment()
        if seg is None:
            return
        self._push_undo()
        seg["status"] = "deleted"
        self._refresh_list()
        self._mark_project_modified()

    # -- Previsualización mpv (sin cortar nada) ------------------------------

    def _on_segment_bounds_changed(self):
        if self._segment_loop_active and self.player is not None and self._valid_segment_bounds():
            start, end = self._segment_bounds()
            self.player.ab_loop_a = start
            self.player.ab_loop_b = end
        self._invalidate_preview_status()
        self._update_position_label()

    def _invalidate_preview_status(self):
        """Si los spinboxes difieren de la última previsualización, vuelve a pending."""
        seg = self._get_selected_segment()
        if seg is None or seg["status"] != "preview":
            return
        spin_start, spin_end = self._segment_bounds()
        ps = seg.get("preview_start")
        pe = seg.get("preview_end")
        if ps is None or pe is None:
            return
        if abs(spin_start - ps) > 0.001 or abs(spin_end - pe) > 0.001:
            seg["status"] = "pending"
            seg.pop("preview_start", None)
            seg.pop("preview_end", None)
            self._refresh_list(select_id=seg["id"])

    def _require_player(self) -> bool:
        if self.player is None or self.video_path is None:
            QMessageBox.warning(
                self, "Sin vídeo",
                "Primero abre un vídeo (y ten python-mpv instalado)."
            )
            return False
        return True

    def _segment_bounds(self):
        start = self.start_spin.value()
        end = self.end_spin.value()
        return start, end

    def _valid_segment_bounds(self) -> bool:
        start, end = self._segment_bounds()
        return end > start

    def _update_play_button(self):
        if not self._segment_loop_active:
            self.play_btn.setEnabled(False)
            self.play_btn.setText("⏸ Pausar")
            return
        self.play_btn.setEnabled(True)
        if self.player is not None and not self.player.pause:
            self.play_btn.setText("⏸ Pausar")
        else:
            self.play_btn.setText("▶ Reanudar")

    def _mark_segment_previewed(self, seg, start: float, end: float):
        self._preview_display_id = seg["id"]
        if seg["status"] not in ("exported", "outdated"):
            seg["status"] = "preview"
            seg["preview_start"] = start
            seg["preview_end"] = end
        seg["start"] = start
        seg["end"] = end
        self._refresh_list(select_id=seg["id"])

    def _update_position_label(self):
        if not self.segments:
            self.position_label.setText("Posición: — (sin oraciones cargadas)")
            return
        start, end = self._segment_bounds()
        if not self._valid_segment_bounds():
            self.position_label.setText("Posición: — (tiempos inválidos)")
            return

        current = start
        if self.player is not None:
            pos = self.player.time_pos
            if pos is not None:
                current = float(pos)

        self.position_label.setText(
            f"Posición: {format_playback_time(current)}  "
            f"(segmento {format_playback_time(start)} → {format_playback_time(end)})"
        )

    def _start_playback_timer(self):
        self._playback_timer.start()

    def _stop_playback_timer(self):
        self._playback_timer.stop()

    def _enable_segment_loop(self, start: float, end: float):
        self.player.command("seek", start, "absolute")
        self.player.ab_loop_a = start
        self.player.ab_loop_b = end
        self.player.pause = False
        self._segment_loop_active = True
        self._start_playback_timer()
        self._update_play_button()
        self._update_position_label()

    def preview_selected_clip(self):
        """Previsualiza el segmento con mpv (A–B loop). No genera archivos."""
        if not self._require_player():
            return
        seg = self._get_selected_segment()
        if seg is None:
            QMessageBox.information(self, "Sin selección", "Selecciona una línea de la lista.")
            return
        start, end = self._segment_bounds()
        if end <= start:
            QMessageBox.warning(self, "Tiempos inválidos", "End debe ser mayor que Start.")
            return
        self._enable_segment_loop(start, end)
        self._mark_segment_previewed(seg, start, end)
        self._mark_project_modified()
        self.statusBar().showMessage(
            f"Previsualizando id={seg['id']} (sin generar archivos). "
            "Pulsa «Probar clip» de nuevo para repetir."
        )

    def play_selected_segment(self):
        """Alias interno — usar preview_selected_clip()."""
        self.preview_selected_clip()

    def toggle_play_pause(self):
        if not self._require_player():
            return
        if not self._valid_segment_bounds():
            QMessageBox.warning(self, "Tiempos inválidos", "End debe ser mayor que Start.")
            return

        if self.player.pause or not self._segment_loop_active:
            if not self._segment_loop_active:
                self.preview_selected_clip()
            else:
                self.player.pause = False
                self._start_playback_timer()
                self._update_play_button()
                self._update_position_label()
        else:
            self.player.pause = True
            self._stop_playback_timer()
            self._update_play_button()
            self._update_position_label()

    def stop_preview(self):
        if self.player is not None:
            self.player.pause = True
            self.player.ab_loop_a = "no"
            self.player.ab_loop_b = "no"
            self._segment_loop_active = False
            self._stop_playback_timer()
            self._update_play_button()
            self._update_position_label()
        self._preview_display_id = None
        self._refresh_list(select_id=self._current_selected_id())

    def seek_relative(self, delta: float):
        if not self._require_player():
            return
        start, end = self._segment_bounds()
        current = self.player.time_pos
        if current is None:
            current = start
        new_pos = float(current) + delta
        if self._segment_loop_active and self._valid_segment_bounds():
            new_pos = max(start, min(end, new_pos))
        else:
            new_pos = max(0.0, new_pos)
        self.player.command("seek", new_pos, "absolute")
        self._update_position_label()

    def seek_to_segment_start(self):
        if not self._require_player():
            return
        start, _ = self._segment_bounds()
        self.player.command("seek", start, "absolute")
        self._update_position_label()

    def seek_to_segment_end(self):
        if not self._require_player():
            return
        _, end = self._segment_bounds()
        preview_end = max(0.0, end - 0.05)
        self.player.command("seek", preview_end, "absolute")
        self.player.pause = True
        self._stop_playback_timer()
        self._update_play_button()
        self._update_position_label()

    def keyPressEvent(self, event: QKeyEvent):
        fw = self.focusWidget()
        if isinstance(fw, (QLineEdit, QSpinBox, QDoubleSpinBox, QAbstractSpinBox)):
            super().keyPressEvent(event)
            return

        key = event.key()
        if key == Qt.Key.Key_Space:
            self.toggle_play_pause()
            event.accept()
            return
        if key == Qt.Key.Key_Left:
            self.seek_relative(-self._seek_step_sec)
            event.accept()
            return
        if key == Qt.Key.Key_Right:
            self.seek_relative(self._seek_step_sec)
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Undo):
            self.undo_edit()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            self.redo_edit()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if not self._prompt_save_before_close():
            event.ignore()
            return
        self._shutdown_mpv_player()
        super().closeEvent(event)

    def _nudge(self, spinbox, delta):
        spinbox.setValue(max(0.0, spinbox.value() + delta))

    def _on_series_name_changed(self, text: str):
        self._series_name = text.strip()
        if self._reevaluate_outdated_segments():
            self._refresh_list()
        self._mark_project_modified()

    def _on_padding_changed(self, _value):
        self.padding_start = self.padding_start_spin.value()
        self.padding_end = self.padding_end_spin.value()
        if self._reevaluate_outdated_segments():
            self._refresh_list()
        self._mark_project_modified()

    def _segment_fingerprint(self, seg: dict) -> dict:
        return build_segment_fingerprint(
            seg,
            video_path=self.video_path or "",
            audio_track=self.audio_track,
            video_track=self.video_track,
            padding_start=self.padding_start,
            padding_end=self.padding_end,
        )

    def _reevaluate_outdated_segments(self) -> bool:
        """Marca clips generados como outdated si la config difiere. Devuelve True si hubo cambios."""
        if not self.video_path:
            return False
        changed = False
        for seg in self.segments:
            if seg.get("status") not in ("exported", "outdated"):
                continue
            current = self._segment_fingerprint(seg)
            before = seg["status"]
            apply_outdated_status(seg, current)
            if seg["status"] != before:
                changed = True
        return changed

    def _outdated_count(self) -> int:
        return sum(1 for s in self.segments if s["status"] == "outdated")

    def _exported_count(self) -> int:
        return sum(1 for s in self.segments if s["status"] == "exported")

    def _effective_series_name(self) -> str:
        raw = self.series_name_edit.text().strip() or self._series_name or "Series"
        safe = sanitize_filename_component(raw)
        return safe or "Series"

    def _episode_label(self) -> str:
        return format_episode_label(self._season, self._episode_num)

    def _file_episode_label(self) -> str:
        return format_episode_label(self._season, self._episode_num, style="compact")

    def _export_sequence_number(self, seg_id: int) -> int:
        """Posición 1-based entre segmentos activos, en orden de self.segments."""
        seq = 0
        for seg in self.segments:
            if seg["status"] == "deleted":
                continue
            seq += 1
            if seg["id"] == seg_id:
                return seq
        raise ValueError(f"Segmento id={seg_id} no encontrado entre segmentos activos")

    def _output_dir(self) -> str:
        if not self.video_path:
            return "output_files"
        return os.path.join(os.path.dirname(self.video_path), "output_files")

    def _sorted_active_segments(self):
        return sorted(
            (s for s in self.segments if s["status"] != "deleted"),
            key=lambda s: (s["start"], s["id"]),
        )

    def _neighbor_bounds(self, seg_id: int):
        active = self._sorted_active_segments()
        idx = next((i for i, s in enumerate(active) if s["id"] == seg_id), None)
        if idx is None:
            return None, None
        prev_end = active[idx - 1]["end"] if idx > 0 else None
        next_start = active[idx + 1]["start"] if idx + 1 < len(active) else None
        return prev_end, next_start

    def _compute_cut_window(self, seg: dict) -> tuple[float, float]:
        prev_end, next_start = self._neighbor_bounds(seg["id"])
        return compute_padded_window(
            seg["start"],
            seg["end"],
            padding_start=self.padding_start,
            padding_end=self.padding_end,
            prev_end=prev_end,
            next_start=next_start,
        )

    def _segments_needing_generation(self):
        return [
            s for s in self._sorted_active_segments()
            if s["status"] in ("pending", "preview", "outdated")
        ]

    def _set_batch_ui_active(self, active: bool):
        self._batch_active = active
        self.batch_generate_btn.setEnabled(not active)
        self.generate_btn.setEnabled(not active)
        self.batch_cancel_btn.setEnabled(active)
        self.batch_progress.setVisible(active)

    def _prepare_segment_for_cut(self, seg: dict) -> tuple[float, float] | None:
        cut_start, cut_end = self._compute_cut_window(seg)
        if cut_end - cut_start < MIN_DURATION:
            return None
        seg.pop("preview_start", None)
        seg.pop("preview_end", None)
        seg["padding_start"] = self.padding_start
        seg["padding_end"] = self.padding_end
        seg["cut_start"] = cut_start
        seg["cut_end"] = cut_end
        return cut_start, cut_end

    def _build_batch_jobs(self, segments, *, overwrite: bool):
        series_name = self._effective_series_name()
        file_episode_label = self._file_episode_label()
        output_dir = self._output_dir()
        os.makedirs(output_dir, exist_ok=True)
        jobs = []
        for seg in segments:
            cut_start, cut_end = self._compute_cut_window(seg)
            if cut_end - cut_start < MIN_DURATION:
                continue
            seq_num = self._export_sequence_number(seg["id"])
            webm_path, mp3_path, _base = clip_output_paths(
                series_name, file_episode_label, seq_num, output_dir
            )
            if not overwrite and (os.path.exists(webm_path) or os.path.exists(mp3_path)):
                continue
            seg.pop("preview_start", None)
            seg.pop("preview_end", None)
            seg["padding_start"] = self.padding_start
            seg["padding_end"] = self.padding_end
            seg["cut_start"] = cut_start
            seg["cut_end"] = cut_end
            jobs.append({
                "index": seg["id"],
                "start": cut_start,
                "end": cut_end,
                "need_video": True,
                "need_audio": True,
                "video_path": webm_path,
                "audio_path": mp3_path,
            })
        return jobs

    def _mark_segment_generated(self, seg: dict):
        seg["generation_fingerprint"] = self._segment_fingerprint(seg)
        seg["status"] = "exported"
        seg.pop("preview_start", None)
        seg.pop("preview_end", None)

    def _restore_segment_status(self, seg: dict):
        prev = self._batch_previous_status.get(seg["id"])
        if prev is not None:
            seg["status"] = prev
        elif seg.get("preview_start"):
            seg["status"] = "preview"
        else:
            seg["status"] = "pending"

    def generate_all_pending(self):
        """Genera todos los clips pending/preview/outdated en una pasada ffmpeg."""
        if self._batch_active:
            return
        if not self.video_path:
            QMessageBox.warning(self, "Sin vídeo", "Abre un vídeo primero.")
            return

        candidates = self._segments_needing_generation()
        if not candidates:
            QMessageBox.information(
                self, "Nada que generar",
                "No hay clips pendientes, en preview o desactualizados."
            )
            return

        series_name = self._effective_series_name()
        episode_label = self._episode_label()
        output_dir = self._output_dir()
        existing = 0
        for seg in candidates:
            webm_path, mp3_path, _ = clip_output_paths(
                series_name, episode_label, seg["id"], output_dir
            )
            if os.path.exists(webm_path) or os.path.exists(mp3_path):
                existing += 1

        msg = (
            f"Se generarán hasta {len(candidates)} clip(s) en una sola pasada FFmpeg "
            f"(más rápido que uno a uno).\n\n"
            f"Pendientes/preview/outdated: {len(candidates)}"
        )
        if existing:
            msg += f"\nArchivos ya existentes: {existing} (se omitirán salvo que elijas sobrescribir)."

        box = QMessageBox(self)
        box.setWindowTitle("Generar lote")
        box.setText(msg)
        box.setInformativeText(
            "Puedes cancelar durante la decodificación con «Cancelar lote»."
        )
        proceed_btn = box.addButton("Generar", QMessageBox.AcceptRole)
        overwrite_btn = box.addButton("Generar (sobrescribir)", QMessageBox.AcceptRole)
        box.addButton("Cancelar", QMessageBox.RejectRole)
        box.setDefaultButton(proceed_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked not in (proceed_btn, overwrite_btn):
            return
        overwrite = clicked == overwrite_btn

        jobs = self._build_batch_jobs(candidates, overwrite=overwrite)
        if not jobs:
            QMessageBox.information(
                self, "Nada que generar",
                "Todos los clips pendientes ya tienen archivos en disco.\n"
                "Usa «Generar (sobrescribir)» para regenerarlos."
            )
            return

        self._batch_previous_status = {}
        job_ids = {job["index"] for job in jobs}
        for seg in self.segments:
            if seg["id"] in job_ids:
                self._batch_previous_status[seg["id"]] = seg["status"]
                seg["status"] = "cutting"

        self._batch_cancel_token = BatchCancelToken()
        self._set_batch_ui_active(True)
        self._refresh_list()
        self.statusBar().showMessage(
            f"Generando lote: {len(jobs)} clip(s) en una pasada FFmpeg…"
        )

        task = BatchGenerateTask(
            self.video_path,
            jobs,
            audio_track=self.audio_track,
            video_track=self.video_track,
            cancel_token=self._batch_cancel_token,
        )
        task.signals.finished.connect(self._on_batch_finished)
        self.thread_pool.start(task)

    def cancel_batch_generation(self):
        if self._batch_cancel_token is not None:
            self._batch_cancel_token.request_cancel()
            self.batch_cancel_btn.setEnabled(False)
            self.statusBar().showMessage("Cancelando lote…")

    def _on_batch_finished(self, success: bool, message: str, completed_ids: list):
        job_count = len(self._batch_previous_status)
        completed_set = set(completed_ids)
        for seg in self.segments:
            if seg["id"] not in self._batch_previous_status:
                continue
            if seg["id"] in completed_set:
                self._mark_segment_generated(seg)
            else:
                self._restore_segment_status(seg)

        self._batch_previous_status = {}
        self._batch_cancel_token = None
        self._set_batch_ui_active(False)
        self._mark_project_modified()
        self._refresh_list()

        if success and not message:
            self.statusBar().showMessage(
                f"Lote completado: {len(completed_ids)} clip(s) generados."
            )
            QMessageBox.information(
                self, "Lote completado",
                f"Se generaron {len(completed_ids)} clip(s) en output_files/."
            )
        elif message and "Cancelado" in message:
            self.statusBar().showMessage(
                f"Lote cancelado. Completados: {len(completed_ids)} clip(s)."
            )
        else:
            detail = message[-800:] if message else "Error desconocido."
            self.statusBar().showMessage(
                f"Lote con errores. Completados: {len(completed_ids)} clip(s)."
            )
            QMessageBox.critical(
                self, "Error en lote",
                f"Completados: {len(completed_ids)} de {job_count}.\n\n{detail}"
            )

    # -- Generación de clips (FFmpeg) ----------------------------------------

    def generate_selected_clip(self):
        """Genera WebM + MP3 en disco. Distinto de previsualizar con mpv."""
        if self._batch_active:
            QMessageBox.information(
                self, "Lote en curso",
                "Espera a que termine o cancela el lote antes de generar un clip individual."
            )
            return
        seg = self._get_selected_segment()
        if seg is None or self.video_path is None:
            QMessageBox.warning(
                self, "Falta información",
                "Selecciona una línea y abre un vídeo primero."
            )
            return

        new_start, new_end = self.start_spin.value(), self.end_spin.value()
        if new_end <= new_start:
            QMessageBox.warning(self, "Tiempos inválidos", "End debe ser mayor que Start.")
            return

        seg["start"], seg["end"] = new_start, new_end
        window = self._prepare_segment_for_cut(seg)
        if window is None:
            QMessageBox.warning(
                self, "Ventana de corte inválida",
                "Con el padding actual la ventana de corte es demasiado corta o inválida.\n"
                "Reduce el padding o ajusta los tiempos."
            )
            return
        cut_start, cut_end = window

        series_name = self._effective_series_name()
        file_episode_label = self._file_episode_label()
        output_dir = self._output_dir()
        os.makedirs(output_dir, exist_ok=True)
        seq_num = self._export_sequence_number(seg["id"])
        webm_path, mp3_path, output_path = clip_output_paths(
            series_name, file_episode_label, seq_num, output_dir
        )

        if os.path.exists(webm_path) or os.path.exists(mp3_path):
            reply = QMessageBox.question(
                self,
                "Archivos existentes",
                f"Ya existen archivos para el clip {seq_num:04d}:\n"
                f"{os.path.basename(webm_path)}\n"
                "¿Regenerarlos con los tiempos actuales?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        seg["status"] = "cutting"
        self._refresh_list()
        self.statusBar().showMessage(
            f"Generando clip id={seg['id']} "
            f"({cut_start:.3f}–{cut_end:.3f}s con padding)…"
        )

        task = CutTask(
            seg["id"], self.video_path, cut_start, cut_end, output_path, media="both",
            audio_track=self.audio_track, video_track=self.video_track,
        )
        task.signals.finished.connect(self._on_cut_finished)
        self.thread_pool.start(task)

    def cut_selected_segment(self):
        """Compatibilidad — redirige a generate_selected_clip()."""
        self.generate_selected_clip()

    def _on_cut_finished(self, segment_id, success, message):
        for seg in self.segments:
            if seg["id"] == segment_id:
                if success:
                    self._mark_segment_generated(seg)
                    self._mark_project_modified()
                    series_name = self._effective_series_name()
                    episode_label = self._episode_label()
                    clip_name = clip_video_filename(series_name, episode_label, seg["id"])
                    self.statusBar().showMessage(
                        f"Clip id={segment_id} generado: {clip_name}"
                    )
                else:
                    seg["status"] = "preview" if seg.get("preview_start") else "pending"
                    QMessageBox.critical(self, "Error al generar clip", message[-800:])
                break
        self._refresh_list()

    # -- Exportar TSV ---------------------------------------------------------

    def export_tsv(self):
        if not self.segments:
            QMessageBox.information(self, "Nada que exportar", "No hay oraciones cargadas.")
            return

        exported = [s for s in self.segments if s["status"] == "exported"]
        outdated = [s for s in self.segments if s["status"] == "outdated"]
        if outdated:
            QMessageBox.warning(
                self,
                "Clips desactualizados",
                f"{len(outdated)} clip(s) tienen cambios sin regenerar.\n\n"
                "Regenera los clips marcados [OUTDATED] antes de exportar, "
                "o el TSV no coincidirá con los archivos en disco."
            )
        if not exported:
            if outdated:
                return
            QMessageBox.information(
                self, "Nada que exportar",
                "No hay clips generados y actualizados.\n"
                "Regenera los clips [OUTDATED] o genera nuevos antes de exportar el TSV."
            )
            return

        path, _ = QFileDialog.getSaveFileName(self, "Exportar TSV", "", "TSV (*.tsv)")
        if not path:
            return

        tsv_rows = []
        series_name = self._effective_series_name()
        episode_label = self._episode_label()
        file_episode_label = self._file_episode_label()
        for seg in self.segments:
            if seg["status"] != "exported":
                continue
            seq_num = self._export_sequence_number(seg["id"])
            video_filename = clip_video_filename(series_name, file_episode_label, seq_num)
            audio_filename = clip_audio_filename(series_name, file_episode_label, seq_num)
            tsv_rows.append((seq_num, seg["text"], video_filename, audio_filename,
                              episode_label, self.episode_title))

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
    configure_mpv_environment()
    _configure_qt_platform_for_mpv()
    app = QApplication(sys.argv)
    _ensure_mpv_numeric_locale()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()