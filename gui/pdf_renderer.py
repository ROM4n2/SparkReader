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

from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
import fitz  # PyMuPDF


class PdfRenderer(QWidget):
    """Renders PDF pages as images. Handles zoom, paging, click detection."""

    page_changed = Signal(int)       # emitted when page changes
    text_selected = Signal(str)      # emitted when user clicks text area
    zoom_changed = Signal(float)     # emitted when zoom level changes

    ZOOM_MIN = 0.5
    ZOOM_MAX = 3.0
    ZOOM_STEP = 0.25

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: fitz.Document | None = None
        self._page_num = 0
        self._total_pages = 0
        self._zoom = 1.0
        self._pixmap: QPixmap | None = None
        self._shown = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet(
            "QScrollArea { background: #181825; border: none; }"
        )
        layout.addWidget(self.scroll_area)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: #181825; padding: 8px;")
        self.scroll_area.setWidget(self.image_label)

        # Intercept scroll area viewport wheel events → route to our handler
        self.scroll_area.viewport().installEventFilter(self)

        self.setMinimumSize(300, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def eventFilter(self, obj, event):
        """Intercept scroll area viewport events → route to our handlers."""
        if obj == self.scroll_area.viewport():
            if event.type() == QEvent.Type.Wheel:
                self.wheelEvent(event)
                return True
            if event.type() == QEvent.Type.MouseButtonPress:
                self.mousePressEvent(event)
                return True
        return super().eventFilter(obj, event)

    def load_document(self, doc: fitz.Document):
        """Load a fitz Document and render page 0."""
        self.doc = doc
        self._total_pages = doc.page_count
        self._page_num = 0
        self._render_current()

    def showEvent(self, event):
        """Auto-fit page to viewport width on first show."""
        super().showEvent(event)
        if self.doc is not None and not self._shown:
            self._shown = True
            self._fit_to_width()

    def _fit_to_width(self):
        """Calculate zoom so page width fills the viewport."""
        vpw = self.scroll_area.viewport().width() - 32  # leave margins
        if vpw <= 0:
            return
        pw = self.doc[0].rect.width  # page width in points
        target = vpw / pw
        # Snap to nearest ZOOM_STEP
        self._zoom = max(self.ZOOM_MIN, min(
            round(target / self.ZOOM_STEP) * self.ZOOM_STEP,
            self.ZOOM_MAX,
        ))
        if self._zoom < 0.5:
            self._zoom = 0.5  # safety floor
        self._render_current()

    def _render_current(self):
        """Render the current page at current zoom and display at full size."""
        if self.doc is None:
            return
        page = self.doc[self._page_num]
        matrix = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=matrix)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img)
        self.image_label.setPixmap(self._pixmap)
        self.zoom_changed.emit(self._zoom)

    # ── Zoom ──

    def wheelEvent(self, event):
        """Ctrl+wheel to zoom in/out. Plain wheel scrolls pages."""
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
        """Navigate to a specific page (0-indexed)."""
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

    # ── Keyboard navigation ──

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Left or event.key() == Qt.Key.Key_Up:
            self.prev_page()
        elif event.key() == Qt.Key.Key_Right or event.key() == Qt.Key.Key_Down:
            self.next_page()
        elif event.key() == Qt.Key.Key_Home:
            self.goto_page(0)
        elif event.key() == Qt.Key.Key_End:
            self.goto_page(self._total_pages - 1)
        else:
            super().keyPressEvent(event)

    # ── Click-to-extract text ──

    def mousePressEvent(self, event):
        """Click on a page → extract nearby text → emit text_selected."""
        if self.doc is None or self._pixmap is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        label_pixmap = self.image_label.pixmap()
        if label_pixmap is None:
            return
        x = event.position().x()
        y = event.position().y()

        # Convert from label coordinates to page coordinates
        label_w = self.image_label.width()
        label_h = self.image_label.height()
        pix_w = label_pixmap.width()
        pix_h = label_pixmap.height()
        offset_x = max(0, (label_w - pix_w) // 2)
        offset_y = max(0, (label_h - pix_h) // 2)

        # Check if click is within the pixmap area
        if x < offset_x or x > offset_x + pix_w or y < offset_y or y > offset_y + pix_h:
            return  # clicked outside image

        # Scale to full-resolution page coordinates
        scale = self._zoom
        page_x = (x - offset_x) * (self._pixmap.width() / scale) / pix_w
        page_y = (y - offset_y) * (self._pixmap.height() / scale) / pix_h

        # Extract words near the click point (within a 200x100pt rectangle)
        page = self.doc[self._page_num]
        clip = fitz.Rect(page_x - 100, page_y - 50, page_x + 100, page_y + 50)
        words = page.get_text("words", clip=clip)
        if not words:
            return

        # Sort by distance to click point, take nearest words
        sorted_words = sorted(
            words,
            key=lambda w: ((w[0] + w[2]) / 2 - page_x) ** 2 + ((w[1] + w[3]) / 2 - page_y) ** 2,
        )
        # Take top words (up to ~200 chars)
        text = " ".join(w[4] for w in sorted_words[:10])
        if len(text) < 5:
            return

        self.text_selected.emit(text.strip())

    def get_current_page_text(self) -> str:
        """Return full text of current page (for 'analyze page' fallback)."""
        if self.doc is None:
            return ""
        page = self.doc[self._page_num]
        return page.get_text()

    def close_document(self):
        """Release document resources."""
        self.doc = None
        self._pixmap = None
        self.image_label.clear()
        self._page_num = 0
        self._total_pages = 0
