"""Widget Qt OpenGL para embeber libmpv vía Render API (Wayland nativo)."""

from __future__ import annotations

import os
import sys
from ctypes import CFUNCTYPE, c_char_p, c_void_p

from PySide6.QtCore import QTimer
from PySide6.QtGui import QOpenGLContext, QSurfaceFormat
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from ui.mpv_embed import mpv_player_kwargs

try:
    import mpv
except (ImportError, OSError):
    mpv = None

GetProcAddressFn = CFUNCTYPE(c_void_p, c_void_p, c_char_p)


class MpvGlWidget(QOpenGLWidget):
    """Reproductor mpv embebido usando libmpv Render API + OpenGL."""

    def __init__(self, parent=None, *, locale_fn=None, log_handler=None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
        fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
        fmt.setVersion(2, 1)
        self.setFormat(fmt)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        self._locale_fn = locale_fn
        self._log_handler = log_handler
        self.player = None
        self._render_ctx = None
        self._pending_path: str | None = None
        self._gl_ready = False

    def load(self, path: str):
        """Carga un vídeo; inicializa GL cuando el widget ya es visible."""
        path = os.path.abspath(path)
        self._pending_path = path
        if not self.isVisible() or self.width() < 2 or self.height() < 2:
            QTimer.singleShot(50, self._retry_load_when_ready)
            return
        if self._gl_ready and self.player is not None:
            try:
                self.player.command("loadfile", path, "replace")
            except Exception as e:
                print(f"[mpv-gl] Error al cargar {path!r}: {e}", file=sys.stderr, flush=True)
                raise
            QTimer.singleShot(300, self._pause_after_load)
            self._request_repaint()
        else:
            self.update()

    def _retry_load_when_ready(self):
        if self._pending_path is None:
            return
        if not self.isVisible() or self.width() < 2 or self.height() < 2:
            QTimer.singleShot(50, self._retry_load_when_ready)
            return
        self.load(self._pending_path)

    def _pause_after_load(self):
        if self.player is not None:
            self.player.pause = True
        self._request_repaint()

    def _request_repaint(self):
        self.update()
        QTimer.singleShot(50, self.update)
        QTimer.singleShot(150, self.update)

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending_path or self._gl_ready:
            self.update()

    def initializeGL(self):
        if mpv is None or self._gl_ready:
            return
        if self._locale_fn is not None:
            self._locale_fn()

        try:
            @GetProcAddressFn
            def get_proc_address(_ctx, name):
                ctx = QOpenGLContext.currentContext()
                if ctx is None:
                    return 0
                if isinstance(name, bytes):
                    name = name.decode("ascii", errors="ignore")
                addr = ctx.getProcAddress(name)
                if addr is None:
                    return 0
                return int(addr)

            self.makeCurrent()
            mpv_kwargs = mpv_player_kwargs(vo="libmpv")
            if self._log_handler is not None:
                self.player = mpv.MPV(log_handler=self._log_handler, **mpv_kwargs)
            else:
                self.player = mpv.MPV(**mpv_kwargs)
            self._render_ctx = mpv.MpvRenderContext(
                self.player,
                "opengl",
                opengl_init_params={"get_proc_address": get_proc_address},
            )
            self._render_ctx.update_cb = self.update
            self._gl_ready = True

            if self._pending_path:
                self.player.command("loadfile", self._pending_path, "replace")
                QTimer.singleShot(300, self._pause_after_load)
            self._request_repaint()
        except Exception as e:
            print(f"[mpv-gl] Error en initializeGL: {e}", file=sys.stderr, flush=True)
            self.player = None
            self._render_ctx = None
            self._gl_ready = False
            raise

    def paintGL(self):
        if self._render_ctx is None:
            return
        self.makeCurrent()
        if not self._render_ctx.update():
            return
        ratio = self.devicePixelRatio()
        w = max(1, int(self.width() * ratio))
        h = max(1, int(self.height() * ratio))
        fbo = int(self.defaultFramebufferObject())
        self._render_ctx.render(
            opengl_fbo={"w": w, "h": h, "fbo": fbo, "internal_format": 0},
            flip_y=True,
        )
        self._render_ctx.report_swap()

    def resizeGL(self, _w, _h):
        self.update()

    def shutdown(self):
        """Libera render context y player mpv."""
        self._gl_ready = False
        self._pending_path = None
        render_ctx = self._render_ctx
        player = self.player
        self._render_ctx = None
        self.player = None
        if render_ctx is not None:
            try:
                render_ctx.free()
            except Exception:
                pass
        if player is not None:
            try:
                player.pause = True
                player.terminate()
            except Exception:
                pass
