"""
PdfRenderer — renders PDF pages as images using PyMuPDF.
Supports zoom, page navigation, and click-to-text extraction.
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
import fitz


class PdfRenderer(QWidget):
    """Renders PDF pages as images. Handles zoom, paging, click detection."""

    page_changed = Signal(int)
    text_selected = Signal(str)
    zoom_changed = Signal(float)

    ZOOM_MIN = 0.5
    ZOOM_MAX = 3.0
    ZOOM_STEP = 0.25

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: fitz.Document | None = None
        self._page_num = 0
        self._total_pages = 0
        self._zoom = 2.0
        self._pixmap: QPixmap | None = None
        self._fit_pending = False

        # Dark background
        self.setStyleSheet("background-color: #181825;")
        self.setMinimumSize(300, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background-color: #181825; border: none; }"
            "QScrollArea > QWidget > QWidget { background-color: #181825; }"
        )
        layout.addWidget(self.scroll_area)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet(
            "background-color: #181825; padding: 8px;"
        )
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.viewport().installEventFilter(self)

    # ── Document lifecycle ──

    def eventFilter(self, obj, event):
        """Intercept scroll area viewport events → PdfRenderer handlers."""
        if obj == self.scroll_area.viewport():
            if event.type() == QEvent.Type.Wheel:
                self.wheelEvent(event)
                return True
            if event.type() == QEvent.Type.MouseButtonPress:
                self.mousePressEvent(event)
                return True
        return super().eventFilter(obj, event)

    def load_document(self, doc: fitz.Document):
        """Load document and schedule first render."""
        self.doc = doc
        self._total_pages = doc.page_count
        self._page_num = 0
        self._zoom = 2.0
        self._fit_pending = False
        self._render_current()
        # Schedule fit-to-width after layout settles
        if not self._fit_pending:
            self._fit_pending = True
            QTimer.singleShot(100, self._fit_to_width)

    def _fit_to_width(self):
        """Adjust zoom so page width fills the viewport."""
        self._fit_pending = False
        if self.doc is None:
            return
        vpw = self.scroll_area.viewport().width()
        if vpw < 100:
            # Too narrow, retry later
            self._fit_pending = True
            QTimer.singleShot(200, self._fit_to_width)
            return
        pw = self.doc[0].rect.width
        target_zoom = vpw / pw
        # Clamp and snap
        self._zoom = max(self.ZOOM_MIN, min(
            round(target_zoom / self.ZOOM_STEP) * self.ZOOM_STEP,
            self.ZOOM_MAX,
        ))
        self._render_current()

    def _render_current(self):
        """Render current page at current zoom and display."""
        if self.doc is None:
            return
        page = self.doc[self._page_num]
        matrix = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=matrix)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img)
        self.image_label.setPixmap(self._pixmap)
        self.zoom_changed.emit(self._zoom)

    def close_document(self):
        """Release resources."""
        self.doc = None
        self._pixmap = None
        self.image_label.clear()
        self._page_num = 0
        self._total_pages = 0
        self._fit_pending = False

    # ── Zoom ──

    def wheelEvent(self, event):
        """Ctrl+wheel zoom. Plain wheel page turn."""
        if self.doc is None:
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self._zoom = min(self._zoom + self.ZOOM_STEP, self.ZOOM_MAX)
            else:
                self._zoom = max(self._zoom - self.ZOOM_STEP, self.ZOOM_MIN)
            self._render_current()
            event.accept()
        else:
            delta = event.angleDelta().y()
            if delta > 0:
                self.prev_page()
            else:
                self.next_page()
            event.accept()

    def set_zoom(self, zoom: float):
        self._zoom = max(self.ZOOM_MIN, min(zoom, self.ZOOM_MAX))
        self._render_current()

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
        self._render_current()
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

        lp = self.image_label.pixmap()
        if lp is None:
            return
        x = event.position().x()
        y = event.position().y()

        # Convert label coordinates to page coordinates
        lw = self.image_label.width()
        lh = self.image_label.height()
        pw = lp.width()
        ph = lp.height()
        ox = max(0, (lw - pw) // 2)
        oy = max(0, (lh - ph) // 2)

        if x < ox or x > ox + pw or y < oy or y > oy + ph:
            return

        scale = self._zoom
        px = (x - ox) * (self._pixmap.width() / scale) / pw
        py = (y - oy) * (self._pixmap.height() / scale) / ph

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
