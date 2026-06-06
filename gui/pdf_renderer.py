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
    """Renders PDF pages at high DPI in a zoomable/pannable QGraphicsView."""

    page_changed = Signal(int)
    text_selected = Signal(str)
    zoom_changed = Signal(float)

    # Quality multiplier: render at Nx the fit-to-width zoom, then scale down
    QUALITY = 2.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: fitz.Document | None = None
        self._page_num = 0
        self._total_pages = 0
        self._render_zoom = 1.0   # DPI multiplier used when rendering
        self._display_zoom = 1.0  # view transform scale (what user sees)
        self._pixmap: QPixmap | None = None
        self._pix_item = None

        self.setMinimumSize(300, 200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet(
            "QGraphicsView { background: #181825; border: none; }"
        )
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.view.setDragMode(QGraphicsView.ScrollHandDrag)
        self.view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        layout.addWidget(self.view)

        # Intercept clicks on viewport for text extraction
        self.view.viewport().installEventFilter(self)

    # ── Event filter for click-to-extract ──

    def eventFilter(self, obj, event):
        if obj == self.view.viewport():
            if event.type() == QEvent.Type.MouseButtonRelease:
                # Only trigger on short clicks (no drag)
                if hasattr(self, '_drag_start'):
                    moved = (event.position() - self._drag_start).manhattanLength()
                    if moved < 10:
                        self._extract_text(event.position())
                del self._drag_start
                return False  # let QGraphicsView handle it too
            if event.type() == QEvent.Type.MouseButtonPress:
                self._drag_start = event.position()
                return False  # let QGraphicsView handle drag
        return super().eventFilter(obj, event)

    # ── Document lifecycle ──

    def load_document(self, doc: fitz.Document):
        self.doc = doc
        self._total_pages = doc.page_count
        self._page_num = 0
        self._render_zoom = 1.0
        self._display_zoom = 1.0
        self._render_current()
        # Fit to width once layout is settled
        QTimer.singleShot(50, self._fit_in_view)

    def _fit_in_view(self):
        """Scale view to fit page width, rendering at high DPI beforehand."""
        if self._pix_item is None:
            return
        vpw = self.view.viewport().width()
        if vpw < 50:
            QTimer.singleShot(100, self._fit_in_view)
            return

        page_w = self._pixmap.width()  # already rendered at self._render_zoom
        # Current view scale to fit width
        fit_scale = vpw / page_w if page_w > 0 else 1.0

        # If we rendered at low zoom (< QUALITY * fit_scale), re-render at high DPI
        # Target: render at QUALITY * fit_scale for crisp text
        target_render = max(self.QUALITY * fit_scale, self._render_zoom)
        if target_render > self._render_zoom * 1.1:
            self._render_zoom = target_render
            self._render_current()

        # Reset view transform and fit
        self.view.resetTransform()
        self._fit_in_view_only()

    def _fit_in_view_only(self):
        """Just fit the current pixmap in the view (no re-render)."""
        if self._pix_item is None:
            return
        self.view.fitInView(
            self._pix_item, Qt.AspectRatioMode.KeepAspectRatio
        )
        t = self.view.transform()
        self._display_zoom = t.m11()
        self.zoom_changed.emit(self._display_zoom)

    def _render_current(self):
        """Render page at self._render_zoom DPI multiplier."""
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
        self.doc = None
        self._pixmap = None
        self._pix_item = None
        self.scene.clear()
        self.view.resetTransform()
        self._page_num = 0
        self._total_pages = 0

    # ── Zoom ──

    def wheelEvent(self, event):
        if self.doc is None:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # Zoom: re-render at higher/lower DPI, then fit to view
            factor = 1.25 if event.angleDelta().y() > 0 else 0.8
            self._render_zoom *= factor
            self._render_zoom = max(0.5, min(self._render_zoom, 8.0))
            self._render_current()
            self._fit_in_view_only()
            event.accept()
        else:
            if event.angleDelta().y() > 0:
                self.prev_page()
            else:
                self.next_page()
            event.accept()

    def set_zoom(self, zoom: float):
        self._render_zoom = max(0.5, min(zoom, 8.0))
        self._render_current()
        self._fit_in_view_only()

    def get_zoom(self) -> float:
        return self._display_zoom

    # ── Page navigation ──

    def goto_page(self, page_num: int):
        if self.doc is None:
            return
        page_num = max(0, min(page_num, self._total_pages - 1))
        if page_num == self._page_num:
            return
        self._page_num = page_num
        self._render_current()
        self._fit_in_view_only()
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
        """Convert viewport click to page coordinates and emit text."""
        if self.doc is None or self._pixmap is None:
            return

        scene_pos = self.view.mapToScene(viewport_pos.toPoint())
        # Convert scene coords → page points
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
