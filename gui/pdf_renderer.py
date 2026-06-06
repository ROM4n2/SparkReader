"""
PdfRenderer — renders PDF pages as images using PyMuPDF.
Uses QGraphicsView for zoom/scroll.
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import Qt, Signal, QTimer, QRectF
from PySide6.QtGui import QPixmap, QImage, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene
import fitz


class PdfRenderer(QWidget):
    """Renders PDF pages as images in a zoomable/pannable QGraphicsView."""

    page_changed = Signal(int)
    text_selected = Signal(str)
    zoom_changed = Signal(float)

    ZOOM_STEP = 0.25

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: fitz.Document | None = None
        self._page_num = 0
        self._total_pages = 0
        self._zoom = 1.0
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

    # ── Document lifecycle ──

    def load_document(self, doc: fitz.Document):
        self.doc = doc
        self._total_pages = doc.page_count
        self._page_num = 0
        self._zoom = 1.0
        self._render_current()
        # Fit to width once the view is laid out
        QTimer.singleShot(50, self._fit_in_view)

    def _fit_in_view(self):
        if self._pix_item is None:
            return
        self.view.fitInView(
            self._pix_item, Qt.AspectRatioMode.KeepAspectRatio
        )
        # Store the fitted zoom as baseline
        t = self.view.transform()
        self._zoom = t.m11()  # horizontal scale factor
        self.zoom_changed.emit(self._zoom)

    def _render_current(self):
        if self.doc is None:
            return
        page = self.doc[self._page_num]
        matrix = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=matrix)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img)

        self.scene.clear()
        self._pix_item = self.scene.addPixmap(self._pixmap)
        self.scene.setSceneRect(QRectF(self._pixmap.rect()))

        self.zoom_changed.emit(self._zoom)

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
            factor = 1.0 + self.ZOOM_STEP
            if event.angleDelta().y() < 0:
                factor = 1.0 / factor
            self.view.scale(factor, factor)
            t = self.view.transform()
            self._zoom = t.m11()
            self.zoom_changed.emit(self._zoom)
            event.accept()
        else:
            delta = event.angleDelta().y()
            if delta > 0:
                self.prev_page()
            else:
                self.next_page()
            event.accept()

    def set_zoom(self, zoom: float):
        self._zoom = zoom
        self._render_current()
        self._fit_in_view()

    def get_zoom(self) -> float:
        return self._zoom

    # ── Page navigation ──

    def goto_page(self, page_num: int):
        if self.doc is None:
            return
        page_num = max(0, min(page_num, self._total_pages - 1))
        if page_num == self._page_num:
            return
        self._page_num = page_num
        # Reset zoom for new page
        self._zoom = 1.0
        self._render_current()
        self._fit_in_view()
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

    def mousePressEvent(self, event):
        if self.doc is None or self._pixmap is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Map view click → scene coordinate
        scene_pos = self.view.mapToScene(event.position().toPoint())
        px = scene_pos.x() / self._zoom
        py = scene_pos.y() / self._zoom

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
