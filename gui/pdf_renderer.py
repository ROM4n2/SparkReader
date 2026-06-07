"""
PdfRenderer — renders PDF pages as images using PyMuPDF.
Uses QGraphicsView for zoom/scroll with high-DPI rendering.
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene
import fitz


class PdfRenderer(QWidget):
    """Renders PDF at high DPI, fit to viewport, Ctrl+wheel to zoom in/out."""

    page_changed = Signal(int)
    text_selected = Signal(str)
    zoom_changed = Signal(float)
    auto_analyze_requested = Signal(str)  # full page text after idle timeout

    IDLE_TIMEOUT = 8000  # ms — auto-analyze after this long on same page

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: fitz.Document | None = None
        self._page_num = 0
        self._total_pages = 0
        # Render at 216 DPI (72×3) for crisp text on modern displays
        self._render_zoom = 3.0
        self._pixmap: QPixmap | None = None
        self._pix_item = None

        # Idle timer for auto-analyze
        self._idle_timer = QTimer()
        self._idle_timer.setSingleShot(True)
        self._idle_timer.setInterval(self.IDLE_TIMEOUT)
        self._idle_timer.timeout.connect(self._on_idle_timeout)

        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet(
            "QGraphicsView { background: #171721; border: none; }"
        )
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        layout.addWidget(self.view)

        # Intercept clicks for text extraction
        self.view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.view.viewport():
            if event.type() == QEvent.Type.MouseButtonPress:
                self._drag_start = event.position()
                return False  # let QGraphicsView handle drag
            if event.type() == QEvent.Type.MouseButtonRelease:
                if hasattr(self, '_drag_start'):
                    dist = (event.position() - self._drag_start).manhattanLength()
                    if dist < 10:
                        self._extract_text(event.position())
                    del self._drag_start
                return False
        return super().eventFilter(obj, event)

    # ── Document lifecycle ──

    def _reset_idle_timer(self):
        """Reset the auto-analyze idle timer."""
        self._idle_timer.stop()
        self._idle_timer.start()

    def _on_idle_timeout(self):
        """Emit full page text for auto-analysis."""
        if self.doc is not None:
            text = self.get_current_page_text()
            if len(text.strip()) > 50:
                self.auto_analyze_requested.emit(text[:2000])

    def load_document(self, doc: fitz.Document):
        self.doc = doc
        self._total_pages = doc.page_count
        self._page_num = 0
        self._render_current()
        self._reset_idle_timer()
        # Wait for layout, then fit to viewport
        QTimer.singleShot(50, self._fit_in_view)

    def _fit_in_view(self):
        if self._pix_item is None:
            return
        self.view.fitInView(
            self._pix_item, Qt.AspectRatioMode.KeepAspectRatio
        )
        t = self.view.transform()
        self.zoom_changed.emit(t.m11())

    def _render_current(self):
        if self.doc is None:
            return
        page = self.doc[self._page_num]
        matrix = fitz.Matrix(self._render_zoom, self._render_zoom)
        pix = page.get_pixmap(matrix=matrix)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img)
        self.scene.clear()
        self._pix_item = self.scene.addPixmap(self._pixmap)
        self.scene.setSceneRect(QRectF(self._pixmap.rect()))

    def close_document(self):
        self._idle_timer.stop()
        self.doc = None
        self._pixmap = None
        self._pix_item = None
        self.scene.clear()
        self.view.resetTransform()
        self._page_num = 0
        self._total_pages = 0

    # ── Zoom via view transform (text gets bigger/smaller visually) ──

    def wheelEvent(self, event):
        if self.doc is None:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self.view.scale(factor, factor)
            self.zoom_changed.emit(self.view.transform().m11())
            self._reset_idle_timer()
            event.accept()
        else:
            if event.angleDelta().y() > 0:
                self.prev_page()
            else:
                self.next_page()
            event.accept()

    def set_zoom(self, zoom: float):
        self.view.resetTransform()
        self.view.scale(zoom, zoom)

    def get_zoom(self) -> float:
        return self.view.transform().m11()

    # ── Page navigation ──

    def goto_page(self, page_num: int):
        if self.doc is None:
            return
        page_num = max(0, min(page_num, self._total_pages - 1))
        if page_num == self._page_num:
            return
        # Save current user zoom before fitInView resets it
        saved_zoom = self.view.transform().m11()
        self._page_num = page_num
        self._render_current()
        self._fit_in_view()
        # Restore user zoom if it was changed from default fit
        fit_zoom = self.view.transform().m11()
        if abs(saved_zoom - fit_zoom) > 0.01:
            self.set_zoom(saved_zoom)
        self._reset_idle_timer()
        self.page_changed.emit(self._page_num)

    def prev_page(self):
        if self._page_num > 0:
            self.goto_page(self._page_num - 1)

    def next_page(self):
        if self._page_num < self._total_pages - 1:
            self.goto_page(self._page_num + 1)

    def current_page(self) -> int:
        return self._page_num

    def page_count(self) -> int:
        return self._total_pages

    # ── Keyboard ──

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.prev_page()
        elif event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down):
            self.next_page()
        elif event.key() == Qt.Key.Key_Home:
            self.goto_page(0)
        elif event.key() == Qt.Key.Key_End:
            self.goto_page(self._total_pages - 1)
        else:
            super().keyPressEvent(event)

    # ── Click-to-extract text ──

    def _extract_text(self, viewport_pos):
        if self.doc is None or self._pixmap is None:
            return
        scene_pos = self.view.mapToScene(viewport_pos.toPoint())
        px = scene_pos.x() / self._render_zoom
        py = scene_pos.y() / self._render_zoom

        page = self.doc[self._page_num]
        clip = fitz.Rect(px - 100, py - 50, px + 100, py + 50)
        words = page.get_text("words", clip=clip)
        if not words:
            return

        sorted_words = sorted(
            words,
            key=lambda w: ((w[0] + w[2]) / 2 - px) ** 2 + ((w[1] + w[3]) / 2 - py) ** 2,
        )
        text = " ".join(w[4] for w in sorted_words[:10])
        if len(text) < 5:
            return
        self.text_selected.emit(text.strip())

    def get_current_page_text(self) -> str:
        if self.doc is None:
            return ""
        return self.doc[self._page_num].get_text()
