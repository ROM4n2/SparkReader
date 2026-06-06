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


_DEBUG_LOG = os.path.join(
    os.environ.get("TEMP", os.environ.get("TMP", "/tmp")),
    "spark_pdf_debug.txt",
)

def _debug(msg: str):
    """Write debug info to a temp file."""
    try:
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


class PdfRenderer(QWidget):
    """Renders PDF pages as images in a scrollable viewport."""

    page_changed = Signal(int)
    text_selected = Signal(str)
    zoom_changed = Signal(float)

    ZOOM_MIN = 0.1
    ZOOM_MAX = 5.0
    ZOOM_STEP = 0.25

    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc: fitz.Document | None = None
        self._page_num = 0
        self._total_pages = 0
        self._zoom = 1.0
        self._pixmap: QPixmap | None = None
        self._started = False

        self.setMinimumSize(300, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

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
        self.image_label.setStyleSheet("background: #181825;")
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport():
            if event.type() == QEvent.Type.Wheel:
                self.wheelEvent(event)
                return True
            if event.type() == QEvent.Type.MouseButtonPress:
                self.mousePressEvent(event)
                return True
        return super().eventFilter(obj, event)

    def load_document(self, doc: fitz.Document):
        self.doc = doc
        self._total_pages = doc.page_count
        self._page_num = 0
        self._zoom = 1.0
        self._started = False
        _debug(f"load_document: pages={doc.page_count}, rect={doc[0].rect}")
        self._render_current()
        # Try fitting immediately in case resizeEvent already fired
        self._try_fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.doc and not self._started:
            self._try_fit()

    def _try_fit(self):
        """Fit to width if we have enough size."""
        if self._started or self.doc is None:
            return
        w = self.width()
        _debug(f"_try_fit: widget_width={w}")
        if w < 100:
            _debug("too narrow, deferring")
            return
        self._started = True
        QTimer.singleShot(0, self._fit_to_width)

    def _fit_to_width(self):
        """Set zoom so page width fills the viewport."""
        if self.doc is None:
            return
        vpw = self.scroll_area.viewport().width()
        pw = self.doc[0].rect.width
        _debug(f"_fit_to_width: vpw={vpw}, page_width={pw}")
        if vpw < 50:
            _debug("vpw too small, retrying in 200ms")
            QTimer.singleShot(200, self._fit_to_width)
            return
        self._zoom = max(self.ZOOM_MIN, min(vpw / pw, self.ZOOM_MAX))
        _debug(f"zoom set to {self._zoom:.3f}")
        self._render_current()

    def _render_current(self):
        """Render page at current zoom."""
        if self.doc is None:
            return
        page = self.doc[self._page_num]
        matrix = fitz.Matrix(self._zoom, self._zoom)
        pix = page.get_pixmap(matrix=matrix)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img)
        self.image_label.setPixmap(self._pixmap)
        _debug(f"_render_current: zoom={self._zoom:.3f}, pixmap={pix.width}x{pix.height}")
        self.zoom_changed.emit(self._zoom)

    def close_document(self):
        self.doc = None
        self._pixmap = None
        self.image_label.clear()
        self._page_num = 0
        self._total_pages = 0

    def wheelEvent(self, event):
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

        lw = self.image_label.width()
        lh = self.image_label.height()
        pw = lp.width()
        ph = lp.height()
        ox = max(0, (lw - pw) // 2)
        oy = max(0, (lh - ph) // 2)
        if x < ox or x > ox + pw or y < oy or y > oy + ph:
            return

        full_w = self._pixmap.width()
        full_h = self._pixmap.height()
        px = (x - ox) * full_w / pw / self._zoom
        py = (y - oy) * full_h / ph / self._zoom

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
