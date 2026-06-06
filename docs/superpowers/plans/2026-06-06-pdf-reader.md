# PDF 阅读器增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Spark ReaderTab from pure text to a three-column layout with PDF image rendering, TOC sidebar, and AI paragraph analysis.

**Architecture:** Single-page PySide6 reader with three-column QSplitter layout. File type routed at open time: PDF → fitz renderer + QPixmap display, txt/md/docx → existing QPlainTextEdit. New components: PdfRenderer (image rendering + zoom + paging + click-text extraction) and TocPanel (TOC tree for PDF or title-extracted list for txt/md). AI analysis reused from existing AiWorker.

**Tech Stack:** PySide6, PyMuPDF (fitz), Ollama (via existing AiWorker)

---

## File Map

| File | Status | Responsibility |
|------|--------|----------------|
| `gui/reader_tab.py` | **Modify** | Main container → three-column layout (TocPanel \| content widget \| explain_browser), file-format routing, top toolbar, bottom status bar with page nav and zoom indicator |
| `gui/pdf_renderer.py` | **Create** | PdfRenderer(QWidget) — display PDF page as QPixmap, handle zoom (Ctrl+wheel, ±0.25 steps, 0.5–3.0), handle page navigation (←/→ keys, goto_page(n)), click-to-extract nearby text via `page.get_text("words", clip=rect)` |
| `gui/toc_panel.py` | **Create** | TocPanel(QWidget) — QTreeWidget for PDF TOC (from `doc.get_toc()`), fallback flat QListWidget for txt/md title extraction. Emit `navigate_requested(page)` signal. |

**No changes needed to:** `gui/ai_worker.py`, `gui/file_parser.py`, `backend/config.py`, `backend/rag_engine.py`

---

### Task 1: Refactor ReaderTab to Three-Column Layout

**Files:**
- Modify: `gui/reader_tab.py` (entire file rewrite — same class, new layout)

**Goal:** Replace the current two-column QSplitter (reader | explain) with a three-column layout: TOC | content | explain. Content area stays as QPlainTextEdit for now. TOC column is a placeholder QWidget. Existing file opening, AI analysis, paragraph detection remain unchanged.

- [ ] **Step 1: Rewrite `_build_ui` to three-column structure**

Replace the current splitter setup (lines 73–115) with:

```python
def _build_ui(self):
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # ── Top toolbar (unchanged) ──
    toolbar = QHBoxLayout()
    toolbar.setContentsMargins(12, 8, 12, 8)
    self.open_btn = QPushButton("📂 打开文件")
    self.open_btn.clicked.connect(self._open_file)
    toolbar.addWidget(self.open_btn)
    self.file_label = QLabel("")
    self.file_label.setStyleSheet("color: #888; font-size: 13px;")
    toolbar.addWidget(self.file_label)

    self.toolbar_zoom_label = QLabel("")
    self.toolbar_zoom_label.setStyleSheet("color: #888; font-size: 13px;")
    toolbar.addWidget(self.toolbar_zoom_label)
    toolbar.addStretch()

    self.clear_btn = QPushButton("✕ 关闭")
    self.clear_btn.setStyleSheet("background: #555; padding: 6px 16px; font-size: 12px;")
    self.clear_btn.clicked.connect(self._close_file)
    self.clear_btn.hide()
    toolbar.addWidget(self.clear_btn)
    layout.addLayout(toolbar)

    # ── Three-column splitter ──
    splitter = QSplitter(Qt.Orientation.Horizontal)

    # Left: TOC placeholder
    self.toc_widget = QWidget()
    toc_layout = QVBoxLayout(self.toc_widget)
    toc_layout.setContentsMargins(0, 0, 0, 0)
    toc_header = QLabel("📖 目录")
    toc_header.setStyleSheet("font-weight: 600; padding: 12px; font-size: 14px; border-bottom: 1px solid #2a2a3e;")
    toc_layout.addWidget(toc_header)
    self.toc_placeholder = QLabel("(打开文件后显示目录)")
    self.toc_placeholder.setStyleSheet("color: #555; padding: 12px;")
    self.toc_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
    toc_layout.addWidget(self.toc_placeholder)
    self.toc_widget.setMinimumWidth(180)
    self.toc_widget.setMaximumWidth(300)
    splitter.addWidget(self.toc_widget)

    # Center: content area (stays QPlainTextEdit for now)
    self.reader = QPlainTextEdit()
    self.reader.setReadOnly(True)
    self.reader.setStyleSheet(
        "QPlainTextEdit {"
        "  background: #181825; color: #e0e0e0;"
        "  font-size: 15px; padding: 20px 24px;"
        "  line-height: 1.9; border: none;"
        "  font-family: 'Microsoft YaHei', 'Noto Sans SC', 'Segoe UI', sans-serif;"
        "}"
    )
    self.reader.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    self.reader.cursorPositionChanged.connect(self._on_cursor_moved)
    splitter.addWidget(self.reader)

    # Right: explanation panel
    right_panel = QWidget()
    right_layout = QVBoxLayout(right_panel)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(0)

    explain_header = QLabel("🧠 概念解释")
    explain_header.setStyleSheet(
        "font-weight: 600; padding: 12px; font-size: 14px;"
        " border-bottom: 1px solid #2a2a3e;"
    )
    right_layout.addWidget(explain_header)

    self.explain_browser = QTextBrowser()
    self.explain_browser.setOpenExternalLinks(False)
    self.explain_browser.setPlaceholderText("点击文本中的段落，AI 会自动识别核心概念并在此显示解释。")
    right_layout.addWidget(self.explain_browser, 1)

    splitter.addWidget(right_panel)
    splitter.setSizes([200, 500, 300])
    layout.addWidget(splitter, 1)

    # ── Bottom status bar (with page nav) ──
    status_layout = QHBoxLayout()
    status_layout.setContentsMargins(12, 4, 12, 4)
    self.status_label = QLabel("📖 点击「打开文件」开始阅读")
    self.status_label.setStyleSheet("color: #666; font-size: 12px;")
    status_layout.addWidget(self.status_label)
    status_layout.addStretch()

    self.page_label = QLabel("")
    self.page_label.setStyleSheet("color: #888; font-size: 12px; margin: 0 8px;")
    status_layout.addWidget(self.page_label)

    self.prev_btn = QPushButton("◀")
    self.prev_btn.setFixedSize(28, 24)
    self.prev_btn.setEnabled(False)
    status_layout.addWidget(self.prev_btn)

    self.next_btn = QPushButton("▶")
    self.next_btn.setFixedSize(28, 24)
    self.next_btn.setEnabled(False)
    status_layout.addWidget(self.next_btn)

    self.status_bar = QWidget()
    self.status_bar.setLayout(status_layout)
    self.status_bar.setStyleSheet("border-top: 1px solid #2a2a3e;")
    self.status_bar.hide()  # hidden until PDF is opened
    layout.addWidget(self.status_bar)
```

- [ ] **Step 2: Add `_toggle_page_nav` helper and class fields**

Add to class `__init__`:

```python
def __init__(self):
    super().__init__()
    self.current_file: str | None = None
    self.current_page = 0
    self.total_pages = 0
    self.current_zoom = 1.0
    self._detect_timer = QTimer()
    self._detect_timer.setSingleShot(True)
    self._detect_timer.setInterval(800)
    self._detect_timer.timeout.connect(self._detect_concept)
    self._thread: QThread | None = None
    self._build_ui()
```

Add a helper method:

```python
def _toggle_page_nav(self, visible: bool):
    """Show/hide PDF page navigation controls."""
    self.status_bar.setVisible(visible)
    self.toolbar_zoom_label.setVisible(visible)
    self.prev_btn.setEnabled(visible and self.current_page > 0)
    self.next_btn.setEnabled(visible and self.current_page < self.total_pages - 1)
```

- [ ] **Step 3: Wire navigation buttons (disabled for now)**

In `_build_ui`, after creating `prev_btn` and `next_btn`:

```python
self.prev_btn.clicked.connect(lambda: self._prev_page())
self.next_btn.clicked.connect(lambda: self._next_page())
```

Add stub methods:

```python
def _prev_page(self):
    """Navigate to previous page (overridden by PdfRenderer)."""
    pass

def _next_page(self):
    """Navigate to next page (overridden by PdfRenderer)."""
    pass
```

- [ ] **Step 4: Remove old `_open_file` text-only logic** — replace with format-routing

Current `_open_file` (lines 128–152) unconditionally calls `parse_file()` and sets plain text. Replace with:

```python
def _open_file(self):
    file_path, _ = QFileDialog.getOpenFileName(
        self, "打开文件", "",
        "支持的文件 (*.txt *.md *.pdf *.docx);;"
        "文本文件 (*.txt *.md);;PDF 文件 (*.pdf);;"
        "Word 文档 (*.docx);;所有文件 (*.*)",
    )
    if not file_path:
        return

    ext = Path(file_path).suffix.lower()
    try:
        if ext == ".pdf":
            self._open_pdf(file_path)
        else:
            self._open_text(file_path)
    except Exception as e:
        QMessageBox.warning(self, "打开失败", f"无法读取文件:\n{e}")
```

- [ ] **Step 5: Extract `_open_text` method** (existing logic, unchanged)

```python
def _open_text(self, file_path: str):
    """Open a .txt/.md/.docx file in QPlainTextEdit."""
    content = parse_file(file_path)
    import re
    content = re.sub(r"\n{3,}", "\n\n", content)
    content = re.sub(r"([^\n])\n([^\n])", r"\1\n\n\2", content)
    self.reader.setPlainText(content)
    self.current_file = file_path
    name = Path(file_path).name
    self.file_label.setText(f"📄 {name}")
    self.clear_btn.show()
    self.status_label.setText(f"📖 正在阅读: {name}")
    self.explain_browser.clear()
    self._toggle_page_nav(False)
    self.reader.show()
```

- [ ] **Step 6: Add `_open_pdf` stub** (populated in Task 2)

```python
def _open_pdf(self, file_path: str):
    """Open a PDF file for image-based rendering."""
    # TODO: Task 2 — replace with PdfRenderer
    QMessageBox.information(self, "提示", "PDF 阅读器正在开发中，暂时以文本模式打开。")
    self._open_text(file_path)  # fallback
```

- [ ] **Step 7: Verify no regressions**

Run: `cd /d/Code/Spark/backend && ../gui/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend'); from gui.reader_tab import ReaderTab; print('ReaderTab imports OK')"`

Run: `cd /d/Code/Spark && backend/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend'); from gui.reader_tab import ReaderTab; from gui.chat_tab import ChatTab; from gui.library_tab import LibraryTab; from gui.settings_tab import SettingsTab; from gui.main_window import MainWindow; print('All gui imports OK')"`

Expected: no ImportError

- [ ] **Step 8: Commit**

```bash
git add gui/reader_tab.py
git commit -m "refactor: three-column layout for ReaderTab

Replace two-column splitter with three-column layout
(TOC | content | explain). Add page navigation bar
(bottom) and zoom label (toolbar). File-format routing
at open time with _open_pdf/_open_text split.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Create PdfRenderer Widget

**Files:**
- Create: `gui/pdf_renderer.py`
- Modify: `gui/reader_tab.py` (wire PdfRenderer into `_open_pdf`)

- [ ] **Step 1: Create `gui/pdf_renderer.py`**

```python
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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: #181825; padding: 8px;")
        layout.addWidget(self.image_label)

        self.setMinimumSize(300, 200)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def load_document(self, doc: fitz.Document):
        """Load a fitz Document and render page 0."""
        self.doc = doc
        self._total_pages = doc.page_count
        self._page_num = 0
        self._render_current()

    def _render_current(self):
        """Render the current page at current zoom."""
        if self.doc is None:
            return
        page = self.doc[self._page_num]
        zoom = self._zoom
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix)
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        self._pixmap = QPixmap.fromImage(img)
        # Scale to fit width while maintaining aspect ratio
        scaled = self._pixmap.scaledToWidth(
            self.image_label.width() - 16,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.zoom_changed.emit(self._zoom)

    def resizeEvent(self, event):
        """Re-render when widget is resized."""
        super().resizeEvent(event)
        if self.doc:
            self._render_current()

    # ── Zoom ──

    def wheelEvent(self, event):
        """Ctrl+wheel to zoom in/out."""
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
            # Scroll/wheel without Ctrl → page up/down
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

        # Calculate click coordinates relative to the pixmap (account for label padding + scaling)
        label_pixmap = self.image_label.pixmap()
        if label_pixmap is None:
            return
        x = event.position().x()
        y = event.position().y()

        # Convert from label coordinates to page coordinates
        # Page coordinates: label might letterbox the image, so compute offset
        label_w = self.image_label.width()
        label_h = self.image_label.height()
        pix_w = label_pixmap.width()
        pix_h = label_pixmap.height()
        offset_x = max(0, (label_w - pix_w) / 2)
        offset_y = max(0, (label_h - pix_h) / 2)

        # Check if click is within the pixmap area
        if x < offset_x or x > offset_x + pix_w or y < offset_y or y > offset_y + pix_h:
            return  # clicked outside image

        # Scale to full-resolution coordinates
        scale = self._zoom
        page_x = (x - offset_x) / pix_w * (self._pixmap.width() / scale)
        page_y = (y - offset_y) / pix_h * (self._pixmap.height() / scale)

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
```

- [ ] **Step 2: Verify PdfRenderer imports OK**

Run: `cd /d/Code/Spark && backend/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend'); from gui.pdf_renderer import PdfRenderer; print('PdfRenderer imports OK')"`

Expected: no ImportError

- [ ] **Step 3: Wire PdfRenderer into ReaderTab's `_open_pdf`**

In `gui/reader_tab.py`, add import at top:

```python
from gui.pdf_renderer import PdfRenderer
```

Replace the stub `_open_pdf` with:

```python
def _open_pdf(self, file_path: str):
    """Open a PDF file for image-based rendering."""
    import fitz
    doc = fitz.open(file_path)
    name = Path(file_path).name
    self.current_file = file_path

    # Replace center widget with PdfRenderer
    splitter = self.findChild(QSplitter)
    if splitter is None:
        # Should not happen — find the splitter
        for child in self.children():
            if isinstance(child, QSplitter):
                splitter = child
                break

    # Remove old reader widget from splitter, insert PdfRenderer
    idx = splitter.indexOf(self.reader)
    self.reader.hide()
    self.pdf_renderer = PdfRenderer()
    self.pdf_renderer.load_document(doc)
    splitter.insertWidget(idx, self.pdf_renderer)

    # Wire signals
    self.pdf_renderer.page_changed.connect(self._on_pdf_page_changed)
    self.pdf_renderer.text_selected.connect(self._on_pdf_text_selected)
    self.pdf_renderer.zoom_changed.connect(self._on_pdf_zoom_changed)

    # UI state
    self.total_pages = doc.page_count
    self.current_page = 0
    self._toggle_page_nav(True)
    self.file_label.setText(f"📄 {name}")
    self.clear_btn.show()
    self.status_label.setText(f"📖 正在阅读: {name}  (←/→ 翻页, Ctrl+滚轮缩放)")
    self.explain_browser.clear()
    self._update_page_label()
    self.pdf_renderer.setFocus()
```

Add the three signal handlers and helper methods:

```python
def _on_pdf_page_changed(self, page_num: int):
    self.current_page = page_num
    self._update_page_label()
    self.prev_btn.setEnabled(page_num > 0)
    self.next_btn.setEnabled(page_num < self.total_pages - 1)

def _on_pdf_text_selected(self, text: str):
    """Trigger AI analysis on clicked PDF text."""
    self._trigger_analysis(text)

def _on_pdf_zoom_changed(self, zoom: float):
    self.current_zoom = zoom
    self.toolbar_zoom_label.setText(f"缩放: {zoom:.0%}")

def _update_page_label(self):
    self.page_label.setText(f"第 {self.current_page + 1}/{self.total_pages} 页")

def _trigger_analysis(self, text: str):
    """Send text to AI analysis (shared by PDF click and text cursor)."""
    if not text or len(text) < 10:
        return
    text = text[:1200]
    prompt = PARAGRAPH_DETECT_PROMPT.format(text=text)
    if self._thread and self._thread.isRunning():
        return
    self.status_label.setText("🧠 后台分析中...")
    self._thread = QThread()
    self._worker = AiWorker(prompt)
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.finished.connect(self._thread.quit)
    self._worker.error.connect(self._thread.quit)
    self._worker.finished.connect(self._on_explain_done)
    self._worker.error.connect(self._on_explain_error)
    self._thread.start()
```

Update `_prev_page` and `_next_page` to delegate:

```python
def _prev_page(self):
    if hasattr(self, 'pdf_renderer'):
        self.pdf_renderer.prev_page()

def _next_page(self):
    if hasattr(self, 'pdf_renderer'):
        self.pdf_renderer.next_page()
```

Update `_close_file` to also clean up pdf_renderer:

```python
def _close_file(self):
    self.reader.clear()
    if hasattr(self, 'pdf_renderer'):
        self.pdf_renderer.close_document()
        self.pdf_renderer.deleteLater()
        del self.pdf_renderer
    self.reader.show()  # restore text reader
    self.current_file = None
    self.file_label.setText("")
    self.clear_btn.hide()
    self.explain_browser.clear()
    self.status_label.setText("📖 点击「打开文件」开始阅读")
    self._toggle_page_nav(False)
```

- [ ] **Step 4: Update `_on_cursor_moved`** to skip when PDF is active

```python
def _on_cursor_moved(self):
    """Called when the cursor position changes. Debounce the AI call."""
    if not self.current_file:
        return
    if hasattr(self, 'pdf_renderer'):
        return  # PDF uses click, not cursor
    ...  # rest unchanged
```

- [ ] **Step 5: Verify import chain**

Run:
```bash
cd /d/Code/Spark && backend/.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend')
from gui.pdf_renderer import PdfRenderer
from gui.reader_tab import ReaderTab
from gui.chat_tab import ChatTab  # runtime dependency
print('All reader imports OK')"
```

Expected: no ImportError

- [ ] **Step 6: Commit**

```bash
git add gui/pdf_renderer.py gui/reader_tab.py
git commit -m "feat: add PdfRenderer widget with zoom, paging, click-text extraction

PdfRenderer renders PDF pages as QPixmap via PyMuPDF.
Supports Ctrl+wheel zoom (0.5-3.0, 0.25 steps),
keyboard page navigation (←/→), click-to-extract
text for AI analysis. Wired into ReaderTab._open_pdf.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Create TocPanel Widget

**Files:**
- Create: `gui/toc_panel.py`
- Modify: `gui/reader_tab.py` (replace TOC placeholder with TocPanel)

- [ ] **Step 1: Create `gui/toc_panel.py`**

```python
"""
TocPanel — table of contents sidebar.
PDF: tree from doc.get_toc()
TXT/MD: flat list from heading regex
"""
import sys
import os
_RDR_DIR = os.path.abspath(os.path.dirname(__file__))
_PROJ_ROOT = os.path.abspath(os.path.join(_RDR_DIR, ".."))
sys.path.insert(0, _PROJ_ROOT)
sys.path.insert(0, os.path.join(_PROJ_ROOT, "backend"))

import re
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLabel, QListWidget, QListWidgetItem, QStackedWidget,
)


class TocPanel(QWidget):
    """Table of contents panel. Tree for PDF, flat list for text files."""

    navigate_requested = Signal(int)  # page number (1-indexed for PDF, 0 for non-PDF)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("📖 目录")
        header.setStyleSheet("font-weight: 600; padding: 12px; font-size: 14px; border-bottom: 1px solid #2a2a3e;")
        layout.addWidget(header)

        self.stack = QStackedWidget()
        self.empty_label = QLabel("(本文件无目录)")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #555; padding: 12px;")
        self.stack.addWidget(self.empty_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setStyleSheet("background: transparent; border: none; font-size: 13px;")
        self.tree.itemClicked.connect(self._on_tree_clicked)
        self.stack.addWidget(self.tree)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("background: transparent; border: none; font-size: 13px;")
        self.list_widget.itemClicked.connect(self._on_list_clicked)
        self.stack.addWidget(self.list_widget)

        layout.addWidget(self.stack, 1)

    def set_pdf_toc(self, toc: list):
        """Populate tree from fitz doc.get_toc() — [(level, title, page), ...]."""
        self.tree.clear()
        if not toc:
            self.stack.setCurrentWidget(self.empty_label)
            return

        stack = [self.tree]
        for level, title, page in toc:
            level = max(1, level)
            # Ensure enough parents in stack
            while len(stack) > level:
                stack.pop()
            item = QTreeWidgetItem(stack[-1])
            item.setText(0, title)
            item.setData(0, Qt.ItemDataRole.UserRole, page)
            item.setToolTip(0, f"第 {page} 页")
            # Ensure stack has this item as potential parent
            while len(stack) <= level:
                stack.append(item)

        self.tree.expandAll()
        self.stack.setCurrentWidget(self.tree)

    def set_text_toc(self, lines: list[str]):
        """Populate flat list from text headings (## / 第X章 / 一、...)."""
        self.list_widget.clear()

        headings = []
        for line in lines:
            stripped = line.strip()
            # .md headings
            if stripped.startswith("#"):
                headings.append((stripped.lstrip("#").strip(), 0))  # non-PDF, page=0
            # Chinese chapter markers
            if re.match(r'^第[一二三四五六七八九十百千]+[章节篇部]', stripped):
                headings.append((stripped, 0))

        if not headings:
            self.stack.setCurrentWidget(self.empty_label)
            return

        for title, _ in headings:
            item = QListWidgetItem(title)
            self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
        self.stack.setCurrentWidget(self.list_widget)

    def clear(self):
        self.tree.clear()
        self.list_widget.clear()
        self.stack.setCurrentWidget(self.empty_label)

    # ── Internal ──

    def _on_tree_clicked(self, item: QTreeWidgetItem, _column: int):
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page:
            self.navigate_requested.emit(int(page))

    def _on_list_clicked(self, item: QListWidgetItem):
        # Text TOC: can't jump to exact page, emit position (intended for future use)
        pass
```

- [ ] **Step 2: Verify TocPanel imports OK**

Run: `cd /d/Code/Spark && backend/.venv/Scripts/python.exe -c "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend'); from gui.toc_panel import TocPanel; print('TocPanel imports OK')"`

Expected: no ImportError

- [ ] **Step 3: Wire TocPanel into ReaderTab**

In `gui/reader_tab.py`, add import:

```python
from gui.toc_panel import TocPanel
```

In `_build_ui`, replace the TOC placeholder section (the block starting `# Left: TOC placeholder`) with:

```python
    # Left: TOC panel
    self.toc_panel = TocPanel()
    self.toc_panel.setMinimumWidth(180)
    self.toc_panel.setMaximumWidth(300)
    self.toc_panel.navigate_requested.connect(self._on_toc_navigate)
    splitter.addWidget(self.toc_panel)
```

Add handler:

```python
def _on_toc_navigate(self, page: int):
    """Jump to PDF page from TOC click (fitz pages are 1-indexed in TOC)."""
    if hasattr(self, 'pdf_renderer') and self.pdf_renderer.doc:
        self.pdf_renderer.goto_page(page - 1)  # TOC is 1-indexed, PdfRenderer is 0-indexed
```

Update `_open_pdf` to set TOC after loading:

```python
def _open_pdf(self, file_path: str):
    ...
    doc = fitz.open(file_path)
    ...
    # Set TOC
    toc = doc.get_toc()  # [(level, title, page), ...]
    self.toc_panel.set_pdf_toc(toc)
    ...
```

Update `_open_text` to set text TOC:

```python
def _open_text(self, file_path: str):
    ...
    self.reader.show()
    # Set text TOC
    lines = content.split("\n")
    self.toc_panel.set_text_toc(lines)
```

Update `_close_file` to clear TOC:

```python
    ...
    self.toc_panel.clear()
    self._toggle_page_nav(False)
```

- [ ] **Step 4: Verify complete import chain**

Run:
```bash
cd /d/Code/Spark && backend/.venv/Scripts/python.exe -c "
import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'backend')
from gui.pdf_renderer import PdfRenderer
from gui.toc_panel import TocPanel
from gui.reader_tab import ReaderTab
from gui.main_window import MainWindow
from gui.chat_tab import ChatTab
from gui.library_tab import LibraryTab
from gui.settings_tab import SettingsTab
print('ALL imports OK')"
```

Expected: no ImportError

- [ ] **Step 5: Commit**

```bash
git add gui/toc_panel.py gui/reader_tab.py
git commit -m "feat: add TocPanel with PDF TOC tree and text heading extraction

TocPanel displays PDF get_toc() as QTreeWidget,
or extracted headings from txt/md as QListWidget.
Emits navigate_requested(page) on click. Wired
into ReaderTab three-column layout.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Smoke Test PDF Reader End-to-End

**Files:** None (manual test)

- [ ] **Step 1: Launch GUI**

Run:
```bash
cd /d/Code/Spark && start backend/.venv/Scripts/pythonw.exe gui/app.py
```

- [ ] **Step 2: Open a PDF**

Navigate to 📖 阅读 tab. Click [打开文件] and select a .pdf file (e.g. `documents/` — note: 马克思主义哲学概要.txt is not PDF; find or convert a sample).

Verify:
- [ ] Three-column layout shows (TOC left, content center, analysis right)
- [ ] Left column shows TOC tree with clickable entries
- [ ] Center shows rendered PDF page image (not raw text)
- [ ] ←/→ keys flip pages
- [ ] Status bar shows "第 X/Y 页 [◀] [▶]"
- [ ] Bottom [◀][▶] buttons navigate pages
- [ ] Ctrl+wheel zooms in/out, zoom percentage updates in toolbar

- [ ] **Step 3: Click-to-analyze on PDF**

Click on a text area in the PDF image. Verify:
- [ ] Right panel shows AI concept analysis
- [ ] Status bar shows "🧠 后台分析中..." then "✅ 分析完成"

- [ ] **Step 4: Open a .txt file**

Reopen a .txt file. Verify:
- [ ] Three-column layout remains, center shows QPlainTextEdit text
- [ ] TOC panel shows extracted headings (or "(本文件无目录)")
- [ ] Cursor-based AI analysis still works

- [ ] **Step 5: Close and reopen**

Click [✕ 关闭], verify UI resets to initial state. Reopen file, verify everything works again.

- [ ] **Step 6: Commit nothing** (no code changes in test)

---

## Self-Review Checklist

- **Spec coverage:** 
  - [x] PDF image rendering via PyMuPDF → Task 2
  - [x] Three-column layout → Task 1
  - [x] TOC sidebar (left) → Task 3
  - [x] Analysis panel (right) → Task 1 (existing explain_browser, reused)
  - [x] Click-to-extract text from PDF → Task 2 (mousePressEvent → text_selected)
  - [x] Zoom (Ctrl+wheel, ±0.25, 0.5–3.0) → Task 2
  - [x] Page navigation (←/→, status bar buttons) → Task 2
  - [x] txt/md TOC extraction → Task 3 (`set_text_toc`)
  - [x] Multi-file split (pdf_renderer.py, toc_panel.py) → Tasks 2, 3
  - [x] Fallback for PDF no-TOC → Task 3 (empty_label)
  - [x] Click outside image ignored → Task 2 (bounds check)
- **Placeholder scan:** No TBD/TODO/FIXME without concrete code.
- **Type consistency:** `goto_page` in PdfRenderer is 0-indexed; TOC emits 1-indexed → `_on_toc_navigate` decrements by 1. All signals match handler signatures.
